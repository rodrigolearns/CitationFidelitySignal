#!/usr/bin/env python3
"""
Workflow 3: PARALLEL Deep Verification

Uses ThreadPoolExecutor to process multiple suspicious citations and contexts concurrently,
reducing processing time from hours to minutes.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from elife_graph_builder.classifiers.second_round_classifier import SecondRoundClassifier
from elife_graph_builder.retrievers.enhanced_retriever import EnhancedEvidenceRetriever
from elife_graph_builder.retrievers.type_aware_retriever import TypeAwareEnhancedRetriever
from elife_graph_builder.graph.neo4j_importer import StreamingNeo4jImporter
from elife_graph_builder.utils.logging_config import setup_logging

logger = setup_logging('deep_verification_parallel')

# Categories that trigger second-round review
SUSPICIOUS_CATEGORIES = [
    'CONTRADICT',
    'NOT_SUBSTANTIATE',
    'OVERSIMPLIFY',
    'IRRELEVANT',
    'MISQUOTE'
]


class ParallelDeepVerificationPipeline:
    """Parallel pipeline for deep verification of suspicious citations."""
    
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
        self.neo4j = StreamingNeo4jImporter(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password
        )
        self.evidence_retriever = EnhancedEvidenceRetriever()
        self.type_aware_retriever = TypeAwareEnhancedRetriever()
        self.classifier = SecondRoundClassifier()
        
        self.max_citation_workers = max_citation_workers
        self.max_context_workers = max_context_workers
        
        # Thread-safe counters
        self.lock = Lock()
        self.stats = {
            'processed': 0,
            'failed': 0,
            'confirmed': 0,
            'corrected': 0,
            'contexts_processed': 0
        }
        
        logger.info(f"✅ Parallel deep verification pipeline initialized")
        logger.info(f"   Citation workers: {max_citation_workers}")
        logger.info(f"   Context workers per citation: {max_context_workers}")
        logger.info(f"   Total concurrent API calls: {max_citation_workers * max_context_workers}")
    
    def _get_suspicious_citations(self, limit: Optional[int] = None) -> List[Dict]:
        """Fetch citations that need second-round review from Neo4j."""
        query = """
            MATCH (source:Article)-[c:CITES]->(target:Article)
            WHERE c.qualified = true
              AND c.citation_contexts_json IS NOT NULL
              AND c.classified = true
            RETURN source.article_id as source_id,
                   target.article_id as target_id,
                   source.title as source_title,
                   target.title as target_title,
                   c.reference_id as reference_id,
                   c.citation_contexts_json as contexts_json
            ORDER BY source.pub_year DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        with self.neo4j.driver.session() as session:
            result = session.run(query)
            all_citations = [dict(record) for record in result]
        
        # Filter for suspicious categories only
        suspicious = []
        for citation in all_citations:
            try:
                contexts = json.loads(citation['contexts_json'])
                if contexts and len(contexts) > 0:
                    first_ctx = contexts[0]
                    
                    # Check if already has second_round
                    if first_ctx.get('second_round'):
                        continue
                    
                    # Check if classified as suspicious
                    if 'classification' in first_ctx and first_ctx['classification']:
                        category = first_ctx['classification'].get('category')
                        if category in SUSPICIOUS_CATEGORIES:
                            suspicious.append(citation)
            except Exception as e:
                logger.error(f"Error parsing contexts for {citation.get('source_id')}: {e}")
        
        logger.info(f"Found {len(suspicious)} suspicious citations for second-round review")
        return suspicious
    
    def _get_article_xml(self, article_id: str) -> Optional[str]:
        """Load XML content for an article."""
        search_dirs = [
            Path("data/samples"),
            Path("data/raw_xml")
        ]
        
        for base_dir in search_dirs:
            if not base_dir.exists():
                continue
            
            # Try different version patterns
            for version in range(1, 10):
                xml_file = base_dir / f"elife-{article_id}-v{version}.xml"
                if xml_file.exists():
                    return xml_file.read_text(encoding='utf-8')
            
            # Try without version
            xml_file = base_dir / f"elife-{article_id}.xml"
            if xml_file.exists():
                return xml_file.read_text(encoding='utf-8')
        
        return None
    
    def _process_single_context(
        self,
        context: Dict,
        target_xml: str,
        target_id: str
    ) -> Optional[Dict]:
        """
        Process a single context (PARALLELIZABLE).
        
        Returns:
            Dict with second_round data or None if skipped
        """
        try:
            # Check if already processed
            if context.get('second_round'):
                return None
            
            # Check if suspicious
            if 'classification' not in context or not context['classification']:
                return None
            
            first_round = context['classification']
            first_category = first_round.get('category')
            
            if first_category not in SUSPICIOUS_CATEGORIES:
                return None
            
            first_confidence = first_round.get('confidence', 0.0)
            first_justification = first_round.get('justification', '')
            citation_type = first_round.get('citation_type', 'UNKNOWN')
            
            # Retrieve enhanced evidence with type awareness
            if citation_type != 'UNKNOWN':
                abstract, evidence_segments = self.type_aware_retriever.retrieve_with_abstract(
                    citation_context=context['context_text'],
                    reference_xml=target_xml,
                    citation_type=citation_type,
                    top_n=15,
                    min_similarity=0.5
                )
            else:
                abstract, evidence_segments = self.evidence_retriever.retrieve_with_abstract(
                    citation_context=context['context_text'],
                    reference_xml=target_xml,
                    top_n=15,
                    min_similarity=0.5
                )
            
            if not evidence_segments:
                return None
            
            # Assess evidence quality
            evidence_quality = self.evidence_retriever.assess_evidence_quality(
                evidence_segments=evidence_segments,
                citation_context=context['context_text']
            )
            
            # Format reference citation
            reference_citation = f"Article {target_id}"
            
            # Perform second-round classification
            second_round = self.classifier.classify_with_context(
                citation_context=context['context_text'],
                section=context.get('section', 'Unknown'),
                reference_citation=reference_citation,
                abstract=abstract,
                evidence_segments=evidence_segments,
                first_round_category=first_category,
                first_round_confidence=first_confidence,
                first_round_justification=first_justification
            )
            
            # Add evidence quality
            second_round.evidence_quality = evidence_quality
            
            return {
                'success': True,
                'instance_id': context['instance_id'],
                'second_round': second_round.model_dump(),
                'determination': second_round.determination
            }
        
        except Exception as e:
            logger.error(f"Failed to process context {context.get('instance_id')}: {e}")
            return {
                'success': False,
                'instance_id': context.get('instance_id'),
                'error': str(e)
            }
    
    def _process_citation_parallel(self, citation_data: Dict) -> Dict:
        """
        Process all contexts for a citation IN PARALLEL.
        """
        source_id = citation_data['source_id']
        target_id = citation_data['target_id']
        reference_id = citation_data['reference_id']
        
        logger.info(f"🔄 Processing: {source_id} → {target_id}")
        
        # Load XMLs
        target_xml = self._get_article_xml(target_id)
        if not target_xml:
            logger.error(f"   ❌ Target XML not found: {target_id}")
            return {'processed': 0, 'failed': 1, 'confirmed': 0, 'corrected': 0}
        
        # Parse contexts
        try:
            contexts = json.loads(citation_data['contexts_json'])
        except Exception as e:
            logger.error(f"   ❌ Failed to parse contexts: {e}")
            return {'processed': 0, 'failed': 1, 'confirmed': 0, 'corrected': 0}
        
        logger.info(f"   Verifying {len(contexts)} contexts IN PARALLEL...")
        
        # PARALLEL CONTEXT PROCESSING
        contexts_processed = 0
        confirmed_count = 0
        corrected_count = 0
        
        with ThreadPoolExecutor(max_workers=self.max_context_workers) as executor:
            # Submit all contexts
            future_to_idx = {
                executor.submit(
                    self._process_single_context,
                    context,
                    target_xml,
                    target_id
                ): idx
                for idx, context in enumerate(contexts)
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                result = future.result()
                
                if result and result.get('success'):
                    # Update context with second_round data
                    contexts[idx]['second_round'] = result['second_round']
                    contexts_processed += 1
                    
                    # Count confirmations vs corrections
                    if result['determination'] == 'CONFIRMED':
                        confirmed_count += 1
                    else:
                        corrected_count += 1
        
        if contexts_processed == 0:
            logger.info("   → No contexts needed processing")
            return {'processed': 0, 'failed': 0, 'confirmed': 0, 'corrected': 0}
        
        # Update Neo4j
        try:
            contexts_json = json.dumps(contexts)
            
            with self.neo4j.driver.session() as session:
                session.run("""
                    MATCH (s:Article {article_id: $source_id})-[c:CITES]->(t:Article {article_id: $target_id})
                    WHERE c.reference_id = $ref_id
                    SET c.citation_contexts_json = $contexts_json,
                        c.second_round_classified = true
                """, source_id=source_id, target_id=target_id, ref_id=reference_id, contexts_json=contexts_json)
            
            logger.info(
                f"   ✅ Verified {contexts_processed} contexts "
                f"(Confirmed: {confirmed_count}, Corrected: {corrected_count})"
            )
            return {
                'processed': 1,
                'failed': 0,
                'confirmed': confirmed_count,
                'corrected': corrected_count,
                'contexts': contexts_processed
            }
        
        except Exception as e:
            logger.error(f"   ❌ Failed to update Neo4j: {e}")
            return {'processed': 0, 'failed': 1, 'confirmed': 0, 'corrected': 0}
    
    def run_parallel(self, batch_size: int = 100) -> Dict:
        """
        Run deep verification pipeline with PARALLEL processing.
        
        Args:
            batch_size: Number of citations to process
        """
        start_time = time.time()
        
        logger.info(f"🚀 Starting PARALLEL deep verification (batch size: {batch_size})")
        logger.info(f"   Max concurrent citations: {self.max_citation_workers}")
        logger.info(f"   Max concurrent contexts per citation: {self.max_context_workers}")
        
        # Get suspicious citations
        citations = self._get_suspicious_citations(limit=batch_size)
        
        if not citations:
            logger.info("✅ No suspicious citations found")
            return {'total': 0, 'processed': 0, 'failed': 0, 'confirmed': 0, 'corrected': 0}
        
        logger.info(f"\n🔄 Processing {len(citations)} suspicious citations in parallel...")
        
        # Reset stats
        self.stats = {
            'processed': 0,
            'failed': 0,
            'confirmed': 0,
            'corrected': 0,
            'contexts_processed': 0
        }
        
        # PARALLEL CITATION PROCESSING
        with ThreadPoolExecutor(max_workers=self.max_citation_workers) as executor:
            # Submit all citations
            future_to_citation = {
                executor.submit(self._process_citation_parallel, citation): citation
                for citation in citations
            }
            
            # Collect results with progress tracking
            completed = 0
            for future in as_completed(future_to_citation):
                result = future.result()
                
                with self.lock:
                    self.stats['processed'] += result['processed']
                    self.stats['failed'] += result['failed']
                    self.stats['confirmed'] += result['confirmed']
                    self.stats['corrected'] += result['corrected']
                    self.stats['contexts_processed'] += result.get('contexts', 0)
                    completed += 1
                
                if completed % 10 == 0 or completed == len(citations):
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
            'confirmed': self.stats['confirmed'],
            'corrected': self.stats['corrected'],
            'contexts_processed': self.stats['contexts_processed'],
            'elapsed_seconds': elapsed
        }
    
    def close(self):
        """Close connections."""
        self.neo4j.close()


def main():
    parser = argparse.ArgumentParser(
        description='Deep verification using PARALLEL processing'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Number of citations to verify (default: 100)'
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
    parser.add_argument(
        '--all',
        action='store_true',
        help='Process all suspicious citations (ignores --batch-size)'
    )
    
    args = parser.parse_args()
    
    batch_size = None if args.all else args.batch_size
    
    print("=" * 70)
    print("⚡ PARALLEL DEEP VERIFICATION PIPELINE")
    print("=" * 70)
    print(f"\nConfiguration:")
    if args.all:
        print(f"   Batch size: ALL suspicious citations")
    else:
        print(f"   Batch size: {args.batch_size} citations")
    print(f"   Citation workers: {args.citation_workers}")
    print(f"   Context workers: {args.context_workers}")
    print(f"   Max concurrent API calls: {args.citation_workers * args.context_workers}")
    print()
    
    pipeline = ParallelDeepVerificationPipeline(
        max_citation_workers=args.citation_workers,
        max_context_workers=args.context_workers
    )
    
    try:
        stats = pipeline.run_parallel(batch_size=batch_size or 999999)
        
        print("\n" + "=" * 70)
        print("✅ DEEP VERIFICATION COMPLETE")
        print("=" * 70)
        print(f"Total citations: {stats['total']}")
        print(f"Processed: {stats['processed']}")
        print(f"Failed: {stats['failed']}")
        print(f"Contexts verified: {stats['contexts_processed']}")
        print(f"Time elapsed: {stats['elapsed_seconds']/60:.1f} minutes")
        print(f"Rate: {stats['total']/stats['elapsed_seconds']*60:.1f} citations/minute")
        print()
        print(f"Results:")
        print(f"   ✅ Confirmed suspicious: {stats['confirmed']}")
        print(f"   ⚠️  Corrected to support: {stats['corrected']}")
        
        if stats['processed'] > 0:
            confirmation_rate = (stats['confirmed'] / (stats['confirmed'] + stats['corrected'])) * 100
            print(f"\n📊 Confirmation Rate: {confirmation_rate:.1f}%")
            print(f"   (Percentage of suspicious citations confirmed as problematic)")
        
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
