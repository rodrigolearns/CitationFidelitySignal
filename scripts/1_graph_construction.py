#!/usr/bin/env python3
"""Run streaming pipeline to continuously build Neo4j graph."""

import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from elife_graph_builder.streaming_pipeline import StreamingCitationPipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def main():
    parser = argparse.ArgumentParser(description='Build citation graph from eLife articles')
    parser.add_argument('--limit', type=int, default=100, help='Number of articles to process (default: 100)')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size (default: 50)')
    parser.add_argument('--enable-cleanup', action='store_true', help='Enable XML cleanup (delete non-citing papers)')
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("🌊 STREAMING CITATION GRAPH PIPELINE")
    print("="*70)
    print("\nThis will:")
    print("  1. Download articles in batches (50 at a time)")
    print("  2. Parse and extract citations")
    print("  3. Stream results to Neo4j incrementally")
    print("  4. Handle rate limiting automatically")
    if args.enable_cleanup:
        print("  5. Clean up XMLs for articles without eLife citations")
    print("\nNeo4j UI: http://localhost:7474")
    print("  Username: neo4j")
    print("  Password: elifecitations2024")
    print("\nPress Ctrl+C to stop gracefully")
    print("="*70)
    
    pipeline = StreamingCitationPipeline()
    
    try:
        pipeline.run_continuous(
            total_articles=args.limit,
            batch_size=args.batch_size,
            start_page=None,  # Let progress tracker determine where to resume
            skip_cleanup=(not args.enable_cleanup)  # Invert: skip_cleanup=True by default
        )
    except KeyboardInterrupt:
        print("\n\n⚠️  Stopping pipeline...")
    finally:
        pipeline.close()
        print("\n✅ Pipeline closed. Graph is saved in Neo4j.")


if __name__ == '__main__':
    main()
