#!/usr/bin/env python3
"""
Clear all data from Neo4j database.

WARNING: This deletes ALL nodes and relationships.
Use only in development when you want to start fresh.
"""

import logging
import argparse
from neo4j import GraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def clear_neo4j(
    neo4j_uri: str = "bolt://localhost:7687",
    neo4j_user: str = "neo4j",
    neo4j_password: str = "elifecitations2024"
):
    """
    Delete all nodes and relationships from Neo4j.
    
    Args:
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
    """
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    
    try:
        with driver.session() as session:
            # Count current data
            count_result = session.run("""
                MATCH (n)
                RETURN count(n) as node_count
            """)
            node_count = count_result.single()['node_count']
            
            rel_result = session.run("""
                MATCH ()-[r]->()
                RETURN count(r) as rel_count
            """)
            rel_count = rel_result.single()['rel_count']
            
            logger.info(f"Current database state:")
            logger.info(f"  - Nodes: {node_count}")
            logger.info(f"  - Relationships: {rel_count}")
            
            if node_count == 0:
                logger.info("✅ Database is already empty")
                return
            
            # Prompt for confirmation
            print("\n" + "=" * 70)
            print("⚠️  WARNING: About to DELETE ALL DATA from Neo4j")
            print("=" * 70)
            print(f"\nThis will delete:")
            print(f"  - {node_count} nodes")
            print(f"  - {rel_count} relationships")
            print("\nThis action cannot be undone!")
            print("\nYou will need to re-run:")
            print("  1. scripts/run_streaming_pipeline.py")
            print("  2. scripts/continue_qualification.py")
            print("  3. scripts/classify_citations.py")
            
            response = input("\nType 'DELETE ALL' to confirm: ")
            
            if response != 'DELETE ALL':
                logger.info("❌ Aborted by user")
                return
            
            # Delete all data
            logger.info("Deleting all data...")
            session.run("""
                MATCH (n)
                DETACH DELETE n
            """)
            
            logger.info("\n" + "=" * 70)
            logger.info("✅ All data deleted from Neo4j")
            logger.info("=" * 70)
            logger.info("\nDatabase is now empty and ready for fresh data.")
            print("\nNext steps:")
            print("  1. Run streaming pipeline to import articles")
            print("  2. Run qualification pipeline to add contexts/evidence")
            print("  3. Run classification pipeline to add LLM evaluations")
            print()
    
    finally:
        driver.close()


def main():
    parser = argparse.ArgumentParser(
        description="Clear all data from Neo4j (use with caution!)"
    )
    parser.add_argument(
        '--neo4j-uri',
        default="bolt://localhost:7687",
        help='Neo4j connection URI'
    )
    parser.add_argument(
        '--neo4j-user',
        default="neo4j",
        help='Neo4j username'
    )
    parser.add_argument(
        '--neo4j-password',
        default="elifecitations2024",
        help='Neo4j password'
    )
    
    args = parser.parse_args()
    
    clear_neo4j(
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password
    )


if __name__ == "__main__":
    main()
