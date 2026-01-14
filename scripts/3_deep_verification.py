#!/usr/bin/env python3
"""
Final Fidelity Determination - Second-Round Classification

Performs in-depth verification of citations flagged as suspicious in the first round.
Uses expanded evidence (abstract + 15 segments) with GPT-4o for higher confidence.

Usage:
    python3 scripts/final_determination.py --batch-size 5
    python3 scripts/final_determination.py --batch-size 10
    python3 scripts/final_determination.py --all  # Process all suspicious citations
"""

import argparse
import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from elife_graph_builder.final_determination_pipeline import FinalDeterminationPipeline
from elife_graph_builder.utils.xml_cleanup import cleanup_all_xmls
from elife_graph_builder.config import Config

logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Second-round classification for suspicious citations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process 5 suspicious citations
  python3 scripts/final_determination.py --batch-size 5
  
  # Process 10 suspicious citations
  python3 scripts/final_determination.py --batch-size 10
  
  # Process all suspicious citations
  python3 scripts/final_determination.py --all
  
Categories processed (from first round):
  - CONTRADICT
  - NOT_SUBSTANTIATE
  - OVERSIMPLIFY
  - IRRELEVANT
  - MISQUOTE

Note: Citations classified as SUPPORT, INCOMPLETE_REFERENCE_DATA, 
      or EVAL_FAILED are automatically skipped.
        """
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=5,
        help='Number of citations to process (default: 5)'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='Process all suspicious citations (ignores --batch-size)'
    )
    
    parser.add_argument(
        '--neo4j-uri',
        default='bolt://localhost:7687',
        help='Neo4j connection URI'
    )
    
    parser.add_argument(
        '--neo4j-user',
        default='neo4j',
        help='Neo4j username'
    )
    
    parser.add_argument(
        '--neo4j-password',
        default='elifecitations2024',
        help='Neo4j password'
    )
    
    parser.add_argument(
        '--skip-cleanup',
        action='store_true',
        help='Skip XML cleanup after processing (keep all files)'
    )
    
    args = parser.parse_args()
    
    # Create pipeline
    pipeline = FinalDeterminationPipeline(
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password
    )
    
    # Run pipeline
    batch_size = None if args.all else args.batch_size
    pipeline.run(batch_size=batch_size)
    
    # Phase 3 Cleanup: Remove all XML files after final determination
    if not args.skip_cleanup:
        try:
            logger.info("\n" + "="*70)
            deleted = cleanup_all_xmls(Config.SAMPLES_DIR)
            if deleted > 0:
                logger.info(f"✅ Phase 3 Cleanup: Deleted {deleted} XML files")
                logger.info("   All XMLs removed - processing complete!")
            logger.info("="*70)
        except Exception as e:
            logger.warning(f"⚠️  Phase 3 Cleanup failed: {e}")
    
    # Workflow 4: Data Analysis & Quality Assessment
    try:
        logger.info("\n" + "="*70)
        logger.info("🚀 Starting Workflow 4: Data Analysis...")
        logger.info("="*70)
        
        # Run analysis script
        import subprocess
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / 'analyze_results.py')],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(result.stdout)
            logger.info("✅ Workflow 4 Analysis Complete!")
        else:
            logger.warning(f"⚠️  Workflow 4 Analysis had warnings:\n{result.stderr}")
            
    except Exception as e:
        logger.warning(f"⚠️  Workflow 4 Analysis failed: {e}")
        logger.info("   You can run it manually with: python scripts/analyze_results.py")


if __name__ == '__main__':
    main()
