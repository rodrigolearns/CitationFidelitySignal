#!/usr/bin/env python3
"""Show current processing status and graph statistics."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from elife_graph_builder.progress_tracker import ProgressTracker
from elife_graph_builder.graph.neo4j_importer import StreamingNeo4jImporter


def main():
    # Load progress tracker
    tracker = ProgressTracker()
    status = tracker.get_status()
    
    # Connect to Neo4j
    try:
        neo4j = StreamingNeo4jImporter()
        stats = neo4j.get_stats()
        
        # Get eLife-specific stats
        with neo4j.driver.session() as session:
            result = session.run('''
                MATCH (a:Article WHERE a.doi STARTS WITH "10.7554/eLife")
                RETURN count(a) as elife_count
            ''')
            elife_count = result.single()['elife_count']
            
            result = session.run('''
                MATCH (a WHERE a.doi STARTS WITH "10.7554/eLife")-[c:CITES]->(b WHERE b.doi STARTS WITH "10.7554/eLife")
                RETURN count(c) as elife_cites
            ''')
            elife_cites = result.single()['elife_cites']
        
        neo4j.close()
        
    except Exception as e:
        print(f"❌ Could not connect to Neo4j: {e}")
        return
    
    # Display status
    print("\n" + "="*70)
    print("📊 CITATION GRAPH STATUS")
    print("="*70)
    
    print("\n📥 Processing Progress:")
    print(f"   Articles processed: {status['total_processed']}")
    print(f"   Date range: {status['oldest_date']} → {status['newest_date']}")
    print(f"   Next API page: {tracker.last_api_page}")
    
    print("\n🗄️  Neo4j Database:")
    print(f"   Total articles: {stats['articles']:,}")
    print(f"   Total citations: {stats['citations']:,}")
    print(f"   eLife source articles: {elife_count:,}")
    print(f"   eLife→eLife citations: {elife_cites:,}")
    
    print("\n🌐 View graph:")
    print("   http://localhost:7474")
    print("   Login: neo4j / elifecitations2024")
    
    print("\n💡 Next steps:")
    print(f"   Continue processing: python3 scripts/continue_processing.py 1000")
    print(f"   Reset and restart:   python3 scripts/continue_processing.py 100 --reset")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()
