#!/usr/bin/env python3
"""
Continue citation qualification pipeline.

Processes unqualified eLife→eLife citations in chronological order (newest first).
Automatically skips already-qualified citations.
Can be run repeatedly to process more papers incrementally.

Usage:
    python scripts/continue_qualification.py --batch-size 100
    python scripts/continue_qualification.py --batch-size 50 --threshold 0.75
"""

import argparse
import logging
from pathlib import Path
from elife_graph_builder.qualification_pipeline import CitationQualificationPipeline
from elife_graph_builder.graph.neo4j_importer import StreamingNeo4jImporter


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def get_stats(importer: StreamingNeo4jImporter) -> dict:
    """Get qualification statistics from Neo4j."""
    with importer.driver.session() as session:
        result = session.run("""
            MATCH ()-[c:CITES]->()
            WHERE c.qualified = true
            RETURN count(c) as qualified_count,
                   sum(c.context_count) as total_contexts
        """)
        record = result.single()
        
        # Get total possible citations
        total_result = session.run("""
            MATCH (a:Article)-[c:CITES]->(b:Article)
            WHERE a.doi STARTS WITH '10.7554/eLife.'
              AND b.doi STARTS WITH '10.7554/eLife.'
            RETURN count(c) as total_citations
        """)
        total_record = total_result.single()
        
        return {
            'qualified': record['qualified_count'] or 0,
            'total_contexts': record['total_contexts'] or 0,
            'total_possible': total_record['total_citations'] or 0
        }


def main():
    parser = argparse.ArgumentParser(
        description='Continue citation qualification pipeline'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Number of citations to process in this batch (default: 100)'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=0.7,
        help='Similarity threshold for evidence retrieval (default: 0.7)'
    )
    parser.add_argument(
        '--neo4j-uri',
        type=str,
        default='bolt://localhost:7687',
        help='Neo4j connection URI'
    )
    parser.add_argument(
        '--neo4j-user',
        type=str,
        default='neo4j',
        help='Neo4j username'
    )
    parser.add_argument(
        '--neo4j-password',
        type=str,
        default='elifecitations2024',
        help='Neo4j password'
    )
    
    args = parser.parse_args()
    setup_logging()
    logger = logging.getLogger(__name__)
    
    print("=" * 70)
    print("🔄 CONTINUE CITATION QUALIFICATION PIPELINE")
    print("=" * 70)
    print()
    
    # Get current stats
    logger.info("Checking current qualification status...")
    importer = StreamingNeo4jImporter(
        uri=args.neo4j_uri,
        user=args.neo4j_user,
        password=args.neo4j_password
    )
    
    stats = get_stats(importer)
    importer.close()
    
    print(f"📊 Current Status:")
    print(f"   Qualified citations: {stats['qualified']}")
    print(f"   Total contexts extracted: {stats['total_contexts']}")
    print(f"   Total eLife→eLife citations: {stats['total_possible']}")
    print(f"   Remaining: {stats['total_possible'] - stats['qualified']}")
    print()
    
    if stats['qualified'] >= stats['total_possible']:
        print("✅ All citations already qualified!")
        print("   Nothing to do.")
        return
    
    # Initialize pipeline
    logger.info("Initializing qualification pipeline...")
    pipeline = CitationQualificationPipeline(
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        similarity_threshold=args.threshold
    )
    
    print(f"🚀 Processing next {args.batch_size} unqualified citations...")
    print(f"   Similarity threshold: {args.threshold}")
    print()
    
    # Run pipeline
    try:
        results = pipeline.process_citations(limit=args.batch_size)
        
        print()
        print("=" * 70)
        print("✅ BATCH COMPLETE!")
        print("=" * 70)
        print(f"   Processed: {results['processed']}/{results['total']}")
        print(f"   Failed: {results['failed']}")
        print(f"   Contexts extracted: {results['contexts_extracted']}")
        print(f"   Evidence segments: {results['evidence_retrieved']}")
        print()
        
        # Get updated stats
        importer = StreamingNeo4jImporter(
            uri=args.neo4j_uri,
            user=args.neo4j_user,
            password=args.neo4j_password
        )
        new_stats = get_stats(importer)
        importer.close()
        
        print(f"📊 Updated Status:")
        print(f"   Total qualified: {new_stats['qualified']}")
        print(f"   Total contexts: {new_stats['total_contexts']}")
        print(f"   Remaining: {new_stats['total_possible'] - new_stats['qualified']}")
        print()
        
        if new_stats['qualified'] < new_stats['total_possible']:
            print(f"💡 To continue, run:")
            print(f"   python scripts/continue_qualification.py --batch-size {args.batch_size}")
        else:
            print("🎉 All citations qualified!")
            print("   Ready for Phase 2: LLM Classification")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        print()
        print(f"❌ Error: {e}")
        print("   Check logs for details")
        return 1
    
    finally:
        pipeline.close()
    
    return 0


if __name__ == "__main__":
    exit(main())
