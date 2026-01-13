#!/usr/bin/env python3
"""Find citations where both source and target XMLs exist in cache."""

import sys
import logging
from pathlib import Path
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_cached_article_ids():
    """Get set of article IDs that have cached XMLs."""
    samples_dir = Path("data/samples")
    
    if not samples_dir.exists():
        return set()
    
    article_ids = set()
    for xml_file in samples_dir.glob("elife-*.xml"):
        # Extract article ID (handle version numbers)
        name = xml_file.stem  # e.g., "elife-12345-v1"
        parts = name.split('-')
        if len(parts) >= 2:
            article_id = parts[1]  # The number after "elife-"
            article_ids.add(article_id)
    
    return article_ids


def find_citations_with_cache(limit=10):
    """Find citations where both source and target have cached XMLs."""
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'elifecitations2024')
    
    cached_ids = get_cached_article_ids()
    logger.info(f"Found {len(cached_ids)} cached article XMLs")
    
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    query = """
        MATCH (source:Article)-[c:CITES]->(target:Article)
        WHERE source.doi STARTS WITH '10.7554/eLife'
          AND target.doi STARTS WITH '10.7554/eLife'
          AND (c.qualified IS NULL OR c.qualified = false)
          AND source.article_id IN $cached_ids
          AND target.article_id IN $cached_ids
        RETURN source.article_id as source_id,
               target.article_id as target_id,
               source.doi as source_doi,
               target.doi as target_doi,
               c.reference_id as ref_id,
               c.citation_count as count
        LIMIT $limit
    """
    
    with driver.session() as session:
        result = session.run(query, cached_ids=list(cached_ids), limit=limit)
        citations = [dict(record) for record in result]
    
    driver.close()
    
    return citations


def main():
    citations = find_citations_with_cache(limit=10)
    
    print(f"\n✅ Found {len(citations)} citations with both XMLs cached:\n")
    
    for i, cit in enumerate(citations, 1):
        print(f"{i}. {cit['source_id']} → {cit['target_id']} (ref: {cit['ref_id']})")
    
    if citations:
        print(f"\n🎯 Ready to test with these {len(citations)} citations!")
    else:
        print("\n⚠️  No citations found with both XMLs cached.")
        print("   You may need to download more articles first.")


if __name__ == "__main__":
    main()
