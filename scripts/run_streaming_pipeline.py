#!/usr/bin/env python3
"""Run streaming pipeline to continuously build Neo4j graph."""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from elife_graph_builder.streaming_pipeline import StreamingCitationPipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def main():
    print("\n" + "="*70)
    print("🌊 STREAMING CITATION GRAPH PIPELINE")
    print("="*70)
    print("\nThis will:")
    print("  1. Download articles in batches (50 at a time)")
    print("  2. Parse and extract citations")
    print("  3. Stream results to Neo4j incrementally")
    print("  4. Handle rate limiting automatically")
    print("\nNeo4j UI: http://localhost:7474")
    print("  Username: neo4j")
    print("  Password: elifecitations2024")
    print("\nPress Ctrl+C to stop gracefully")
    print("="*70)
    
    pipeline = StreamingCitationPipeline()
    
    try:
        # Process 100 articles in 2 batches
        pipeline.run_continuous(
            total_articles=100,  # Process 100 for testing
            batch_size=50,
            start_page=1
        )
    except KeyboardInterrupt:
        print("\n\n⚠️  Stopping pipeline...")
    finally:
        pipeline.close()
        print("\n✅ Pipeline closed. Graph is saved in Neo4j.")


if __name__ == '__main__':
    main()
