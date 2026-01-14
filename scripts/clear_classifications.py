#!/usr/bin/env python3
"""
Clear ONLY classification data (Workflow 2 & 3) while preserving Workflow 1 data.

This allows re-running Workflow 2 and Workflow 3 with updated code while keeping:
- Graph structure (articles and CITES edges)
- Citation contexts
- Evidence segments

What gets cleared:
- First-round classifications (Workflow 2)
- Second-round classifications (Workflow 3)
- classified and second_round_classified flags
"""

import logging
import json
import argparse
from neo4j import GraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def clear_classifications(
    neo4j_uri: str = "bolt://localhost:7687",
    neo4j_user: str = "neo4j",
    neo4j_password: str = "elifecitations2024",
    dry_run: bool = False,
    force: bool = False
):
    """
    Clear classification data while preserving qualification data.
    
    Args:
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        dry_run: If True, only show what would be cleared
    """
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    
    try:
        with driver.session() as session:
            # Count citations with classifications
            count_result = session.run("""
                MATCH ()-[c:CITES]->()
                WHERE c.classified = true OR c.second_round_classified = true
                RETURN count(c) as total
            """)
            total = count_result.single()['total']
            
            logger.info(f"Found {total} citations with classification data")
            
            if total == 0:
                logger.info("No classifications found. Nothing to clear.")
                return
            
            # Show what will be affected
            print("\n" + "=" * 70)
            print(f"{'[DRY RUN] ' if dry_run else ''}About to clear classification data for {total} citations")
            print("=" * 70)
            print("\n✅ WILL KEEP:")
            print("  - Graph structure (articles and CITES edges)")
            print("  - Citation contexts (4-sentence windows)")
            print("  - Evidence segments (from Workflow 1)")
            print("  - qualified flag and qualification data")
            print("\n❌ WILL CLEAR:")
            print("  - First-round classifications (Workflow 2 results)")
            print("  - Second-round classifications (Workflow 3 results)")
            print("  - classified flag")
            print("  - second_round_classified flag")
            print("\n📝 NEXT STEPS AFTER CLEARING:")
            print("  1. python3 scripts/evaluate_fidelity.py --batch-size 10")
            print("  2. python3 scripts/final_determination.py --batch-size 5")
            print()
            
            if dry_run:
                print("🔍 DRY RUN - No changes will be made")
                return
            
            if not force:
                response = input("Proceed with clearing classifications? (yes/no): ")
                if response.lower() != 'yes':
                    logger.info("Aborted by user")
                    return
            else:
                logger.info("Force mode - proceeding without confirmation")
            
            # Clear classification data by removing classification fields from JSON
            logger.info("Clearing classification data from citation_contexts_json...")
            
            # Get all citations with contexts
            result = session.run("""
                MATCH (source:Article)-[c:CITES]->(target:Article)
                WHERE c.citation_contexts_json IS NOT NULL
                RETURN source.article_id as source_id,
                       target.article_id as target_id,
                       c.reference_id as ref_id,
                       c.citation_contexts_json as contexts_json
            """)
            
            citations_updated = 0
            for record in result:
                contexts = json.loads(record['contexts_json'])
                
                # Remove classification and second_round from each context
                for ctx in contexts:
                    if 'classification' in ctx:
                        del ctx['classification']
                    if 'second_round' in ctx:
                        del ctx['second_round']
                
                # Update the citation with cleaned contexts
                updated_json = json.dumps(contexts)
                session.run("""
                    MATCH (source:Article {article_id: $source_id})
                          -[c:CITES {reference_id: $ref_id}]->
                          (target:Article {article_id: $target_id})
                    SET c.citation_contexts_json = $contexts_json,
                        c.classified = null,
                        c.second_round_classified = null
                """, 
                    source_id=record['source_id'],
                    target_id=record['target_id'],
                    ref_id=record['ref_id'],
                    contexts_json=updated_json
                )
                
                citations_updated += 1
                if citations_updated % 10 == 0:
                    logger.info(f"  Processed {citations_updated} citations...")
            
            logger.info(f"✅ Cleared classifications from {citations_updated} citations")
            print("\n" + "=" * 70)
            print(f"✅ Successfully cleared {citations_updated} citations")
            print("=" * 70)
            print("\nYou can now re-run Workflow 2 and Workflow 3 with the new code:")
            print("  1. python3 scripts/evaluate_fidelity.py --batch-size 10")
            print("  2. python3 scripts/final_determination.py --batch-size 5")
            print()
    
    finally:
        driver.close()


def main():
    parser = argparse.ArgumentParser(
        description="Clear classification data while preserving qualification data"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be cleared without actually clearing'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    args = parser.parse_args()
    
    clear_classifications(dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    main()
