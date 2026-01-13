#!/usr/bin/env python3
"""Simple test: Process 100 articles into Neo4j."""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from elife_graph_builder.streaming_pipeline import StreamingCitationPipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)


def main():
    print("\n" + "="*70)
    print("🧪 SIMPLE TEST: 100 Articles → Neo4j")
    print("="*70)
    
    pipeline = StreamingCitationPipeline()
    
    try:
        pipeline.run_continuous(
            total_articles=100,
            batch_size=50
        )
        
        # Show final stats
        stats = pipeline.neo4j.get_stats()
        print("\n" + "="*70)
        print("✅ COMPLETE!")
        print("="*70)
        print(f"Articles in graph: {stats['articles']}")
        print(f"Citations in graph: {stats['citations']}")
        print("\n🌐 View at: http://localhost:7474")
        print("   Login: neo4j / elifecitations2024")
        print("\n📊 Try this query:")
        print("   MATCH (a:Article)-[c:CITES]->(b:Article)")
        print("   RETURN a, c, b LIMIT 50")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        pipeline.close()


if __name__ == '__main__':
    main()
