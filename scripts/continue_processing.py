#!/usr/bin/env python3
"""Continue processing more articles into Neo4j."""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from elife_graph_builder.streaming_pipeline import StreamingCitationPipeline
from elife_graph_builder.progress_tracker import ProgressTracker

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Continue processing eLife articles')
    parser.add_argument(
        'count',
        type=int,
        help='Number of additional articles to process'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Articles per batch (default: 50)'
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Reset progress and start from beginning'
    )
    
    args = parser.parse_args()
    
    # Load progress tracker
    tracker = ProgressTracker()
    
    if args.reset:
        print("⚠️  Resetting progress...")
        tracker.reset()
        tracker.save()
    
    # Show current status
    status = tracker.get_status()
    print("\n" + "="*70)
    print("📊 CURRENT PROGRESS")
    print("="*70)
    print(f"Already processed: {status['total_processed']} articles")
    print(f"Date range: {status['oldest_date']} → {status['newest_date']}")
    print(f"\n🎯 Will process {args.count} MORE articles")
    print("   Ordering: Most recent → Oldest")
    print("="*70 + "\n")
    
    # Create pipeline with progress tracking
    pipeline = StreamingCitationPipeline()
    pipeline.tracker = tracker  # Attach tracker
    
    try:
        # Process more articles
        pipeline.run_continuous(
            total_articles=args.count,
            batch_size=args.batch_size
        )
        
        # Save final progress
        tracker.save()
        
        # Show results
        final_status = tracker.get_status()
        stats = pipeline.neo4j.get_stats()
        
        print("\n" + "="*70)
        print("✅ PROCESSING COMPLETE")
        print("="*70)
        print(f"Session processed: {args.count} articles")
        print(f"Total processed ever: {final_status['total_processed']} articles")
        print(f"Date range: {final_status['oldest_date']} → {final_status['newest_date']}")
        print(f"\n📊 Neo4j Graph:")
        print(f"   Articles: {stats['articles']}")
        print(f"   Citations: {stats['citations']}")
        print("\n🌐 View at: http://localhost:7474")
        
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted - saving progress...")
        tracker.save()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        tracker.save()
    finally:
        pipeline.close()


if __name__ == '__main__':
    main()
