#!/usr/bin/env python3
"""Sprint 2: Process articles and build citation relations."""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from elife_graph_builder.pipeline import CitationGraphBuilder

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def main():
    print("\n" + "="*70)
    print("🚀 SPRINT 2: Citation Graph Building")
    print("="*70)
    
    builder = CitationGraphBuilder()
    
    # Process 200 articles
    stats = builder.process_articles(count=200)
    
    # Show results
    print("\n" + "="*70)
    print("📊 RESULTS")
    print("="*70)
    print(f"Articles downloaded: {stats['articles_downloaded']}")
    print(f"Articles parsed: {stats['articles_parsed']}")
    print(f"Total references: {stats['total_references']}")
    print(f"eLife references: {stats['elife_references']}")
    print(f"Citation edges: {stats['citation_edges']}")
    
    # Load and show sample edges
    edges = builder.get_edges()
    if edges:
        print(f"\n📈 Sample citation edges:")
        for edge in edges[:5]:
            print(f"   {edge['source']} → {edge['target']} ({edge['citation_count']} mentions)")
    
    print("\n✅ Sprint 2 complete! Ready for Neo4j (Sprint 3)")


if __name__ == '__main__':
    main()
