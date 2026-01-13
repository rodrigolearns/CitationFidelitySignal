#!/usr/bin/env python3
"""
Clear qualification and classification data from Neo4j.

This script removes qualification data (contexts, evidence, classifications)
from CITES relationships, allowing them to be re-processed with updated code.
"""

import logging
import argparse
from neo4j import GraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def clear_qualifications(
    neo4j_uri: str = "bolt://localhost:7687",
    neo4j_user: str = "neo4j",
    neo4j_password: str = "elifecitations2024",
    clear_classifications: bool = True
):
    """
    Clear qualification data from Neo4j CITES relationships.
    
    Args:
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        clear_classifications: If True, also clear classification data
    """
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    
    try:
        with driver.session() as session:
            # First, count how many will be affected
            count_result = session.run("""
                MATCH ()-[c:CITES]->()
                WHERE c.qualified = true
                RETURN count(c) as total
            """)
            total = count_result.single()['total']
            
            logger.info(f"Found {total} qualified citations to clear")
            
            if total == 0:
                logger.info("No qualified citations found. Nothing to clear.")
                return
            
            # Prompt for confirmation
            print("\n" + "=" * 70)
            print(f"⚠️  WARNING: About to clear qualification data for {total} citations")
            print("=" * 70)
            print("\nThis will remove:")
            print("  - citation_contexts_json")
            print("  - qualified flag")
            print("  - qualified_at timestamp")
            print("  - context_count")
            
            if clear_classifications:
                print("  - classified flag")
                print("  - All classification data")
            
            print("\nYou will need to re-run:")
            print("  1. scripts/continue_qualification.py --batch-size 10")
            if clear_classifications:
                print("  2. scripts/classify_citations.py --batch-size 10")
            
            response = input("\nProceed? (yes/no): ")
            
            if response.lower() != 'yes':
                logger.info("Aborted by user")
                return
            
            # Clear the data
            if clear_classifications:
                query = """
                    MATCH ()-[c:CITES]->()
                    WHERE c.qualified = true
                    SET c.qualified = null,
                        c.citation_contexts_json = null,
                        c.qualified_at = null,
                        c.context_count = null,
                        c.classified = null
                    RETURN count(c) as cleared
                """
            else:
                query = """
                    MATCH ()-[c:CITES]->()
                    WHERE c.qualified = true
                    SET c.qualified = null,
                        c.citation_contexts_json = null,
                        c.qualified_at = null,
                        c.context_count = null
                    RETURN count(c) as cleared
                """
            
            result = session.run(query)
            cleared = result.single()['cleared']
            
            logger.info(f"✅ Cleared {cleared} citations")
            print("\n" + "=" * 70)
            print(f"✅ Successfully cleared {cleared} qualified citations")
            print("=" * 70)
            print("\nNext steps:")
            print("  1. python3 scripts/continue_qualification.py --batch-size 10")
            if clear_classifications:
                print("  2. python3 scripts/classify_citations.py --batch-size 10")
            print()
    
    finally:
        driver.close()


def main():
    parser = argparse.ArgumentParser(
        description="Clear qualification data from Neo4j"
    )
    parser.add_argument(
        '--keep-classifications',
        action='store_true',
        help='Keep classification data, only clear qualification data'
    )
    
    args = parser.parse_args()
    
    clear_qualifications(
        clear_classifications=not args.keep_classifications
    )


if __name__ == "__main__":
    main()
