#!/usr/bin/env python3
"""
Workflow 2: PARALLEL Citation Classification

Uses ThreadPoolExecutor to process multiple citations and contexts concurrently,
reducing processing time from hours to minutes.
"""

import argparse
import json
import logging
import time
from pathlib import Path
from typing import List, Dict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from elife_graph_builder.classifiers import LLMClassifier
from elife_graph_builder.graph.neo4j_importer import StreamingNeo4jImporter
from elife_graph_builder.models import CitationContext, EvidenceSegment
from elife_graph_builder.utils.logging_config import setup_logging

logger = setup_logging('evaluate_fidelity_parallel')


class ParallelClassificationPipeline:
    """Parallel pipeline for classifying citations with LLM."""
    
    def __init__(
        self,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "elifecitations2024",
        max_citation_workers: int = 50,
        max_context_workers: int = 3
    ):
        """
        Initialize pipeline.
        
        Args:
            max_citation_workers: Max citations to process in parallel
            max_context_workers: Max contexts per citation to process in parallel
        """
        self.classifier = LLMClassifier()
        self.neo4j = StreamingNeo4jImporter(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password
        )
        self.max_citation_workers = max_citation_workers
        self.max_context_workers = max_context_workers
        
        # Thread-safe counters
        self.lock = Lock()
        self.stats = {
            'processed': 0,
            'failed': 0,
            'total_tokens': 0,
            'total_contexts': 0
        }
        
        logger.info(f"✅ Parallel classification pipeline initialized")
        logger.info(f"   Citation workers: {max_citation_workers}")
        logger.info(f"   Context workers per citation: {max_context_workers}")
        logger.info(f"   Total concurrent API calls: {max_citation_workers * max_context_workers}")
    
    def get_unclassified_citations(self, limit: int = None) -> List[Dict]:
        """Get qualified but unclassified citations from Neo4j."""
        query = """
            MATCH (source:Article)-[c:CITES]->(target:Article)
            WHERE c.qualified = true
              AND c.citation_contexts_json IS NOT NULL
              AND c.classified IS NULL
            RETURN source.article_id as source_id,
                   target.article_id as target_id,
                   source.title as source_title,
                   target.title as target_title,
                   target.authors as target_authors,
                   target.pub_year as target_year,
                   c.citation_contexts_json as contexts_json,
                   c.context_count as context_count
            ORDER BY source.pub_year DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        with self.neo4j.driver.session() as session:
            result = session.run(query)
            all_citations = [dict(record) for record in result]
        
        # Filter out citations with no evidence
        citations_with_evidence = []
        skipped = 0
        
        for citation in all_citations:
            contexts = json.loads(citation['contexts_json'])
            has_evidence = any(
                ctx.get('evidence_segments') and len(ctx.get('evidence_segments', [])) > 0 
                for ctx in contexts
            )
            
            if has_evidence:
                citations_with_evidence.append(citation)
            else:
                skipped += 1
        
        logger.info(f"Found {len(citations_with_evidence)} unclassified citations with evidence")
        if skipped > 0:
            logger.info(f"Skipped {skipped} citations with no evidence")
        
        return citations_with_evidence
    
    def parse_contexts_json(self, contexts_json: str) -> List[CitationContext]:
        """Parse contexts JSON with evidence segments."""
        try:
            contexts_data = json.loads(contexts_json)
            contexts = []
            
            for ctx_data in contexts_data:
                # Parse evidence segments
                evidence_segments = []
                for ev_data in ctx_data.get('evidence_segments', []):
                    evidence_segments.append(EvidenceSegment(
                        section=ev_data.get('section', 'Unknown'),
                        text=ev_data['text'],
                        similarity_score=ev_data['similarity_score'],
                        retrieval_method=ev_data.get('retrieval_method', 'hybrid'),
                        paragraph_index=ev_data.get('paragraph_index')
                    ))
                
                # Create context object with safe defaults
                context = CitationContext(
                    instance_id=ctx_data['instance_id'],
                    source_article_id=ctx_data.get('source_article_id', ''),
                    target_article_id=ctx_data.get('target_article_id', ''),
                    ref_id=ctx_data.get('ref_id', ''),
                    section=ctx_data.get('section', 'Unknown'),
                    sentence_before_2=ctx_data.get('sentence_before_2', ''),
                    sentence_before_1=ctx_data.get('sentence_before_1', ''),
                    citation_sentence=ctx_data.get('citation_sentence', ''),
                    sentence_after_1=ctx_data.get('sentence_after_1', ''),
                    context_text=ctx_data.get('context_text', ''),
                    evidence_segments=evidence_segments
                )
                contexts.append(context)
            
            return contexts
        except Exception as e:
            logger.error(f"Failed to parse contexts: {e}")
            return []
    
    def format_citation_string(self, authors: List[str], year: int) -> str:
        """Format citation as it appears in text."""
        if not authors or len(authors) == 0:
            return f"Unknown et al. ({year})"
        
        first_author = authors[0].split()[-1] if authors else "Unknown"
        
        if len(authors) == 1:
            return f"{first_author} ({year})"
        elif len(authors) == 2:
            second_author = authors[1].split()[-1]
            return f"{first_author} and {second_author} ({year})"
        else:
            return f"{first_author} et al. ({year})"
    
    def classify_single_context(
        self,
        citation_format: str,
        context: CitationContext,
        target_id: str
    ) -> Dict:
        """
        Classify a single context (PARALLELIZABLE).
        
        Returns:
            Dict with classification data or error
        """
        try:
            classification = self.classifier.classify_context(
                citation_format=citation_format,
                context=context,
                reference_article_id=target_id
            )
            
            return {
                'success': True,
                'instance_id': context.instance_id,
                'context_text': context.context_text,
                'section': context.section,
                'evidence_segments': [
                    {
                        'text': seg.text,
                        'section': seg.section,
                        'similarity_score': seg.similarity_score
                    }
                    for seg in context.evidence_segments
                ],
                'classification': {
                    'citation_type': classification.citation_type,
                    'category': classification.category,
                    'confidence': classification.confidence,
                    'justification': classification.justification,
                    'classified_at': classification.classified_at,
                    'model_used': classification.model_used
                },
                'tokens': classification.tokens_used or 0
            }
        
        except Exception as e:
            logger.error(f"Failed to classify context {context.instance_id}: {e}")
            return {
                'success': False,
                'instance_id': context.instance_id,
                'error': str(e),
                'tokens': 0
            }
    
    def classify_citation_parallel(self, citation_data: Dict) -> Dict:
        """
        Classify all contexts for a citation IN PARALLEL.
        
        This is the key optimization - instead of processing contexts
        sequentially, we process them all at once!
        """
        source_id = citation_data['source_id']
        target_id = citation_data['target_id']
        
        logger.info(f"🔄 Processing: {source_id} → {target_id}")
        
        # Parse contexts
        contexts = self.parse_contexts_json(citation_data['contexts_json'])
        if not contexts:
            logger.warning(f"   No contexts to classify")
            return {'processed': 0, 'failed': 1, 'tokens': 0}
        
        # Format citation
        citation_format = self.format_citation_string(
            authors=citation_data.get('target_authors', []),
            year=citation_data.get('target_year', 2020)
        )
        
        logger.info(f"   Classifying {len(contexts)} contexts IN PARALLEL...")
        
        # PARALLEL CONTEXT CLASSIFICATION
        contexts_data = []
        total_tokens = 0
        
        with ThreadPoolExecutor(max_workers=self.max_context_workers) as executor:
            # Submit all contexts
            future_to_context = {
                executor.submit(
                    self.classify_single_context,
                    citation_format,
                    context,
                    target_id
                ): context
                for context in contexts
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_context):
                result = future.result()
                
                if result['success']:
                    contexts_data.append({
                        'instance_id': result['instance_id'],
                        'context_text': result['context_text'],
                        'section': result['section'],
                        'evidence_segments': result['evidence_segments'],
                        'classification': result['classification'],
                        'human_review': {
                            'needs_review': False,
                            'reviewed': False,
                            'user_classification': None,
                            'user_comment': None
                        }
                    })
                    total_tokens += result['tokens']
                else:
                    # Add error entry
                    contexts_data.append({
                        'instance_id': result['instance_id'],
                        'context_text': '',
                        'section': '',
                        'evidence_segments': [],
                        'classification': {
                            'category': 'ERROR',
                            'confidence': 0.0,
                            'justification': f"Classification failed: {result['error']}",
                            'classified_at': datetime.now().isoformat()
                        }
                    })
        
        # Update Neo4j
        try:
            contexts_json = json.dumps(contexts_data)
            
            query = """
                MATCH (source:Article {article_id: $source_id})
                      -[c:CITES]->
                      (target:Article {article_id: $target_id})
                SET c.citation_contexts_json = $contexts_json,
                    c.classified = true,
                    c.classified_at = datetime()
            """
            
            with self.neo4j.driver.session() as session:
                session.run(query, source_id=source_id, target_id=target_id, contexts_json=contexts_json)
            
            logger.info(f"   ✅ Classified {len(contexts)} contexts (tokens: {total_tokens})")
            return {'processed': 1, 'failed': 0, 'tokens': total_tokens}
        
        except Exception as e:
            logger.error(f"   ❌ Failed to update Neo4j: {e}")
            return {'processed': 0, 'failed': 1, 'tokens': total_tokens}
    
    def run_parallel(self, batch_size: int = 25) -> Dict:
        """
        Run classification pipeline with PARALLEL processing.
        
        Args:
            batch_size: Number of citations to process
        """
        start_time = time.time()
        
        logger.info(f"🚀 Starting PARALLEL classification (batch size: {batch_size})")
        logger.info(f"   Max concurrent citations: {self.max_citation_workers}")
        logger.info(f"   Max concurrent contexts per citation: {self.max_context_workers}")
        
        # Get unclassified citations
        citations = self.get_unclassified_citations(limit=batch_size)
        
        if not citations:
            logger.info("✅ No unclassified citations found")
            return {'total': 0, 'processed': 0, 'failed': 0, 'total_tokens': 0}
        
        logger.info(f"\n🔄 Processing {len(citations)} citations in parallel...")
        
        # Reset stats
        self.stats = {
            'processed': 0,
            'failed': 0,
            'total_tokens': 0,
            'total_contexts': 0
        }
        
        # PARALLEL CITATION PROCESSING
        with ThreadPoolExecutor(max_workers=self.max_citation_workers) as executor:
            # Submit all citations
            future_to_citation = {
                executor.submit(self.classify_citation_parallel, citation): citation
                for citation in citations
            }
            
            # Collect results with progress tracking
            completed = 0
            for future in as_completed(future_to_citation):
                result = future.result()
                
                with self.lock:
                    self.stats['processed'] += result['processed']
                    self.stats['failed'] += result['failed']
                    self.stats['total_tokens'] += result['tokens']
                    completed += 1
                
                if completed % 5 == 0 or completed == len(citations):
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    eta = (len(citations) - completed) / rate if rate > 0 else 0
                    
                    logger.info(
                        f"   Progress: {completed}/{len(citations)} citations "
                        f"({rate:.1f}/sec, ETA: {eta/60:.1f} min)"
                    )
        
        elapsed = time.time() - start_time
        
        return {
            'total': len(citations),
            'processed': self.stats['processed'],
            'failed': self.stats['failed'],
            'total_tokens': self.stats['total_tokens'],
            'elapsed_seconds': elapsed
        }
    
    def close(self):
        """Close connections."""
        self.neo4j.close()


def main():
    parser = argparse.ArgumentParser(
        description='Classify citations using PARALLEL processing'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=25,
        help='Number of citations to classify (default: 25)'
    )
    parser.add_argument(
        '--citation-workers',
        type=int,
        default=50,
        help='Max concurrent citations (default: 50)'
    )
    parser.add_argument(
        '--context-workers',
        type=int,
        default=3,
        help='Max concurrent contexts per citation (default: 3)'
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("⚡ PARALLEL CITATION CLASSIFICATION PIPELINE")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"   Batch size: {args.batch_size} citations")
    print(f"   Citation workers: {args.citation_workers}")
    print(f"   Context workers: {args.context_workers}")
    print(f"   Max concurrent API calls: {args.citation_workers * args.context_workers}")
    print()
    
    pipeline = ParallelClassificationPipeline(
        max_citation_workers=args.citation_workers,
        max_context_workers=args.context_workers
    )
    
    try:
        stats = pipeline.run_parallel(batch_size=args.batch_size)
        
        print("\n" + "=" * 70)
        print("✅ CLASSIFICATION COMPLETE")
        print("=" * 70)
        print(f"Total citations: {stats['total']}")
        print(f"Processed: {stats['processed']}")
        print(f"Failed: {stats['failed']}")
        print(f"Total tokens: {stats['total_tokens']:,}")
        print(f"Time elapsed: {stats['elapsed_seconds']/60:.1f} minutes")
        print(f"Rate: {stats['total']/stats['elapsed_seconds']*60:.1f} citations/minute")
        
        if stats['total_tokens'] > 0:
            cost_per_1k = 0.14  # DeepSeek input cost
            estimated_cost = (stats['total_tokens'] / 1_000_000) * cost_per_1k
            print(f"Estimated cost: ${estimated_cost:.4f}")
        
        print(f"\nView results: http://localhost:3000")
        
    except KeyboardInterrupt:
        logger.info("\n⚠️  Pipeline interrupted by user")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        pipeline.close()


if __name__ == '__main__':
    main()
