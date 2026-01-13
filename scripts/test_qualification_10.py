#!/usr/bin/env python3
"""Test citation qualification pipeline on 10 citations."""

import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from elife_graph_builder.qualification_pipeline import run_qualification_pipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Run qualification pipeline on 10 citations."""
    
    print("\n" + "=" * 70)
    print("🧪 CITATION QUALIFICATION TEST: 10 Citations")
    print("=" * 70 + "\n")
    
    # Run pipeline
    stats = run_qualification_pipeline(
        limit=10,
        bm25_top_n=20,
        final_top_k=5,
        min_similarity=0.7
    )
    
    # Display results
    print("\n" + "=" * 70)
    print("📊 RESULTS")
    print("=" * 70)
    print(f"Citations processed: {stats['processed']}/{stats['total']}")
    print(f"Contexts extracted: {stats['contexts_extracted']}")
    print(f"Evidence segments retrieved: {stats['evidence_retrieved']}")
    print(f"Failed: {stats['failed']}")
    print("=" * 70 + "\n")
    
    print("✅ Test complete!")
    print("\nNext: View results in Neo4j Browser:")
    print("   http://localhost:7474")
    print("\nSample queries:")
    print("""
    // View qualified citations with context count
    MATCH (a:Article)-[c:CITES]->(b:Article)
    WHERE c.qualified = true
    RETURN a.article_id, b.article_id, c.context_count, 
           SIZE(c.citation_contexts_json) as data_size
    LIMIT 5
    
    // View full JSON data (parse to see contexts and evidence)
    MATCH (a:Article)-[c:CITES]->(b:Article)
    WHERE c.qualified = true AND c.context_count > 0
    RETURN a.article_id, b.article_id, c.citation_contexts_json
    LIMIT 1
    """)


if __name__ == "__main__":
    main()
