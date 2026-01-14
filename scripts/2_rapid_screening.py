#!/usr/bin/env python3
"""
Classify qualified citations using LLM.

Processes qualified eLife→eLife citations and adds LLM-based
classification to assess citation fidelity.

Usage:
    python scripts/classify_citations.py --batch-size 10
    python scripts/classify_citations.py --batch-size 100 --force-reclassify
"""

import argparse
import json
import logging
from pathlib import Path
from typing import List, Dict
from datetime import datetime

from elife_graph_builder.classifiers import LLMClassifier
from elife_graph_builder.graph.neo4j_importer import StreamingNeo4jImporter
from elife_graph_builder.models import CitationContext, EvidenceSegment
from elife_graph_builder.utils.logging_config import setup_logging

# Setup logging to both console and file (logs/evaluate_fidelity_YYYYMMDD.log)
logger = setup_logging('evaluate_fidelity')


class CitationClassificationPipeline:
    """Pipeline for classifying citations with LLM."""
    
    def __init__(
        self,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "elifecitations2024"
    ):
        """Initialize pipeline."""
        self.classifier = LLMClassifier()
        self.neo4j = StreamingNeo4jImporter(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password
        )
        logger.info("✅ Classification pipeline initialized")
    
    def get_unclassified_citations(self, limit: int = None) -> List[Dict]:
        """
        Get qualified but unclassified citations from Neo4j.
        Only returns citations that have evidence segments (skips INCOMPLETE_REFERENCE_DATA).
        
        Args:
            limit: Maximum number to fetch
            
        Returns:
            List of citation dictionaries with evidence
        """
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
            ORDER BY source.pub_date DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        with self.neo4j.driver.session() as session:
            result = session.run(query)
            all_citations = [dict(record) for record in result]
        
        # Filter out citations with no evidence (INCOMPLETE_REFERENCE_DATA)
        citations_with_evidence = []
        skipped_count = 0
        
        for citation in all_citations:
            contexts = json.loads(citation['contexts_json'])
            has_evidence = any(
                ctx.get('evidence_segments') and len(ctx.get('evidence_segments', [])) > 0 
                for ctx in contexts
            )
            
            if has_evidence:
                citations_with_evidence.append(citation)
            else:
                skipped_count += 1
                logger.debug(
                    f"Skipping {citation['source_id']}→{citation['target_id']} "
                    f"(INCOMPLETE_REFERENCE_DATA - no evidence)"
                )
        
        logger.info(f"Found {len(citations_with_evidence)} unclassified citations with evidence")
        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} citations with INCOMPLETE_REFERENCE_DATA")
        
        return citations_with_evidence
    
    def format_citation_string(
        self,
        authors: List[str],
        year: int
    ) -> str:
        """
        Format citation as it appears in text.
        
        Args:
            authors: List of author names
            year: Publication year
            
        Returns:
            Formatted citation string (e.g., "Smith J et al. (2023)")
        """
        if not authors:
            return f"Unknown ({year})"
        
        first_author = authors[0] if isinstance(authors, list) else str(authors)
        
        if len(authors) == 1:
            return f"{first_author} ({year})"
        elif len(authors) == 2:
            return f"{authors[0]} and {authors[1]} ({year})"
        else:
            return f"{first_author} et al. ({year})"
    
    def parse_contexts_json(self, contexts_json: str) -> List[CitationContext]:
        """
        Parse citation contexts from JSON string.
        
        Args:
            contexts_json: JSON string from Neo4j
            
        Returns:
            List of CitationContext objects
        """
        try:
            data = json.loads(contexts_json)
            contexts = []
            
            for ctx_data in data:
                # Parse evidence segments
                evidence = []
                for ev_data in ctx_data.get('evidence_segments', []):
                    evidence.append(EvidenceSegment(
                        section=ev_data.get('section', 'Unknown'),
                        text=ev_data['text'],
                        similarity_score=ev_data['similarity_score'],
                        retrieval_method=ev_data.get('retrieval_method', 'hybrid'),
                        paragraph_index=ev_data.get('paragraph_index')
                    ))
                
                # Create context object
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
                    evidence_segments=evidence
                )
                contexts.append(context)
            
            return contexts
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse contexts JSON: {e}")
            return []
    
    def update_context_classification(
        self,
        source_id: str,
        target_id: str,
        contexts_with_classifications: List[Dict]
    ):
        """
        Update Neo4j with classifications for each context.
        
        Args:
            source_id: Source article ID
            target_id: Target article ID
            contexts_with_classifications: List of context dicts with classifications
        """
        # Convert back to JSON string
        contexts_json = json.dumps(contexts_with_classifications)
        
        query = """
            MATCH (source:Article {article_id: $source_id})
                  -[c:CITES]->
                  (target:Article {article_id: $target_id})
            SET c.citation_contexts_json = $contexts_json,
                c.classified = true,
                c.classified_at = datetime()
        """
        
        with self.neo4j.driver.session() as session:
            session.run(
                query,
                source_id=source_id,
                target_id=target_id,
                contexts_json=contexts_json
            )
    
    def classify_citation(
        self,
        citation_data: Dict
    ) -> Dict:
        """
        Classify all contexts for a single citation.
        
        Args:
            citation_data: Citation dictionary from Neo4j
            
        Returns:
            Statistics dictionary
        """
        source_id = citation_data['source_id']
        target_id = citation_data['target_id']
        
        logger.info(f"📦 Classifying: {source_id} → {target_id}")
        
        source_title = citation_data.get('source_title') or 'Untitled'
        target_title = citation_data.get('target_title') or 'Untitled'
        logger.info(f"   Source: {source_title[:60]}...")
        logger.info(f"   Target: {target_title[:60]}...")
        
        # Parse contexts
        contexts = self.parse_contexts_json(citation_data['contexts_json'])
        
        if not contexts:
            logger.warning("   No contexts to classify")
            return {'processed': 0, 'failed': 1, 'tokens': 0}
        
        logger.info(f"   Contexts: {len(contexts)}")
        
        # Format citation string
        citation_format = self.format_citation_string(
            authors=citation_data.get('target_authors', []),
            year=citation_data.get('target_year', 2020)
        )
        logger.info(f"   Cited as: {citation_format}")
        
        # Classify each context
        total_tokens = 0
        contexts_data = []
        
        for i, context in enumerate(contexts, 1):
            try:
                logger.info(f"   Classifying context {i}/{len(contexts)}...")
                
                classification = self.classifier.classify_context(
                    citation_format=citation_format,
                    context=context,
                    reference_article_id=target_id
                )
                
                # Convert context to dict and add classification
                context_dict = {
                    'instance_id': context.instance_id,
                    'source_article_id': context.source_article_id,
                    'target_article_id': context.target_article_id,
                    'ref_id': context.ref_id,
                    'section': context.section,
                    'context_text': context.context_text,
                    'sentence_before_2': context.sentence_before_2,
                    'sentence_before_1': context.sentence_before_1,
                    'citation_sentence': context.citation_sentence,
                    'sentence_after_1': context.sentence_after_1,
                    'evidence_segments': [
                        {
                            'section': ev.section,
                            'text': ev.text,
                            'similarity_score': ev.similarity_score,
                            'retrieval_method': ev.retrieval_method,
                            'paragraph_index': ev.paragraph_index
                        }
                        for ev in context.evidence_segments
                    ],
                    'classification': {
                        'citation_type': classification.citation_type,
                        'category': classification.category,
                        'confidence': classification.confidence,
                        'justification': classification.justification,
                        'classified_at': classification.classified_at,
                        'model_used': classification.model_used,
                        'tokens_used': classification.tokens_used,
                        'manually_reviewed': False,
                        'user_classification': None,
                        'user_comment': None
                    }
                }
                contexts_data.append(context_dict)
                
                if classification.tokens_used:
                    total_tokens += classification.tokens_used
                
                logger.info(f"      → {classification.category} "
                          f"(type: {classification.citation_type}, confidence: {classification.confidence:.2f})")
                
            except Exception as e:
                logger.error(f"   Failed to classify context {i}: {e}")
                # Add context without classification
                contexts_data.append({
                    'instance_id': context.instance_id,
                    'context_text': context.context_text,
                    'section': context.section,
                    'evidence_segments': [],
                    'classification': {
                        'category': 'ERROR',
                        'confidence': 0.0,
                        'justification': f"Classification failed: {str(e)}",
                        'classified_at': datetime.now().isoformat()
                    }
                })
        
        # Update Neo4j
        try:
            self.update_context_classification(
                source_id=source_id,
                target_id=target_id,
                contexts_with_classifications=contexts_data
            )
            logger.info(f"   ✅ Updated Neo4j (tokens: {total_tokens})")
            return {'processed': 1, 'failed': 0, 'tokens': total_tokens}
            
        except Exception as e:
            logger.error(f"   Failed to update Neo4j: {e}")
            return {'processed': 0, 'failed': 1, 'tokens': total_tokens}
    
    def run(self, batch_size: int = 10) -> Dict:
        """
        Run classification pipeline.
        
        Args:
            batch_size: Number of citations to process
            
        Returns:
            Statistics dictionary
        """
        logger.info(f"🚀 Starting classification pipeline (batch size: {batch_size})")
        
        # Get unclassified citations
        citations = self.get_unclassified_citations(limit=batch_size)
        
        if not citations:
            logger.info("✅ No unclassified citations found")
            return {'total': 0, 'processed': 0, 'failed': 0, 'tokens': 0}
        
        # Process each citation
        stats = {
            'total': len(citations),
            'processed': 0,
            'failed': 0,
            'total_tokens': 0,
            'total_contexts': 0
        }
        
        for i, citation in enumerate(citations, 1):
            logger.info(f"\n{'='*70}")
            logger.info(f"Citation {i}/{len(citations)}")
            logger.info(f"{'='*70}")
            
            result = self.classify_citation(citation)
            stats['processed'] += result['processed']
            stats['failed'] += result['failed']
            stats['total_tokens'] += result['tokens']
            stats['total_contexts'] += citation.get('context_count', 0)
        
        return stats
    
    def close(self):
        """Close connections."""
        self.neo4j.close()


def main():
    parser = argparse.ArgumentParser(
        description='Classify qualified citations using LLM'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Number of citations to classify (default: 10)'
    )
    
    args = parser.parse_args()
    
    print("="*70)
    print("🤖 CITATION CLASSIFICATION PIPELINE")
    print("="*70)
    print()
    
    try:
        pipeline = CitationClassificationPipeline()
        stats = pipeline.run(batch_size=args.batch_size)
        
        print()
        print("="*70)
        print("✅ CLASSIFICATION COMPLETE")
        print("="*70)
        print(f"Total citations: {stats['total']}")
        print(f"Processed: {stats['processed']}")
        print(f"Failed: {stats['failed']}")
        if 'total_contexts' in stats:
            print(f"Total contexts: {stats['total_contexts']}")
        print(f"Total tokens: {stats['total_tokens']:,}")
        
        if stats['total_tokens'] > 0:
            # Estimate cost (GPT-5 Mini: $0.25 input, $2.00 output per M tokens)
            # Rough: 80% input, 20% output
            input_tokens = int(stats['total_tokens'] * 0.8)
            output_tokens = int(stats['total_tokens'] * 0.2)
            cost = (input_tokens * 0.25 / 1_000_000) + (output_tokens * 2.00 / 1_000_000)
            print(f"Estimated cost: ${cost:.4f}")
        
        print()
        print("View results: http://localhost:3000")
        
        pipeline.close()
        return 0
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
