#!/usr/bin/env python3
"""
Part 4: Data Analysis & Quality Assessment

Run comprehensive analysis after final determination to identify:
- Overall pipeline statistics
- Problematic papers (repeat offenders)
- Citation patterns and trends

This is the final step in the pipeline and generates insights for researchers.
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the existing analysis scripts
from analyze_pipeline_stats import main as run_pipeline_stats

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run all Part 4 analyses."""
    print("\n" + "="*70)
    print("📊 PART 4: DATA ANALYSIS & QUALITY ASSESSMENT")
    print("="*70)
    print("\nAnalyzing citation fidelity patterns across all processed papers...")
    print()
    
    try:
        # Run pipeline statistics analysis
        logger.info("Running pipeline statistics analysis...")
        run_pipeline_stats()
        
        logger.info("\n✅ Part 4 Analysis Complete!")
        logger.info("\nGenerated Files:")
        logger.info("  - data/analysis/pipeline_stats.json")
        logger.info("\nView Results:")
        logger.info("  - Web Interface: http://localhost:3000")
        logger.info("  - Problematic Papers table visible on main page")
        
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}")
        raise


if __name__ == '__main__':
    main()
