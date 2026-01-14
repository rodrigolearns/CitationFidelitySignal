#!/usr/bin/env python3
"""
Workflow 5: Impact Assessment & Reporting

Performs comprehensive impact analysis on problematic papers:
- Phase A: Citation Analysis - Deep reading of full paper texts
- Phase B: Synthesis & Reporting - Pattern detection and report generation

Usage:
    python scripts/5_impact_assessment.py <article_id>
    python scripts/5_impact_assessment.py 84538
"""

import sys
import json
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from elife_graph_builder.impact_assessment import ImpactAssessmentWorkflow
from elife_graph_builder.config import Config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run impact analysis on a single paper."""
    
    if len(sys.argv) < 2:
        print("Usage: python scripts/5_impact_assessment.py <article_id>")
        print("Example: python scripts/5_impact_assessment.py 84538")
        sys.exit(1)
    
    article_id = sys.argv[1]
    
    print("=" * 80)
    print(f"🎯 Workflow 5: Impact Assessment & Reporting")
    print(f"📄 Paper: eLife.{article_id}")
    print("=" * 80)
    print()
    
    # Initialize workflow
    workflow = ImpactAssessmentWorkflow()
    
    try:
        # Run analysis
        print("▶️  Starting analysis...")
        print()
        
        result = workflow.analyze_paper(article_id)
        
        if result:
            print()
            print("=" * 80)
            print("✅ ANALYSIS COMPLETE!")
            print("=" * 80)
            print()
            
            # Display key results
            print(f"📊 Overall Classification: {result.overall_classification}")
            print()
            print(f"📝 Executive Summary:")
            print(f"   {result.stage2_combined_analysis.executive_summary}")
            print()
            print(f"📄 Detailed Report:")
            print(f"   {result.stage2_combined_analysis.detailed_report[:500]}...")
            print()
            
            # Pattern analysis
            pattern = result.stage2_combined_analysis.pattern_analysis
            severity = pattern.get('severity_assessment', {})
            
            print(f"🎯 Citation Impact Breakdown:")
            print(f"   - HIGH impact: {len(severity.get('high_impact_citations', []))} citations")
            print(f"   - MODERATE impact: {len(severity.get('moderate_impact_citations', []))} citations")
            print(f"   - LOW impact: {len(severity.get('low_impact_citations', []))} citations")
            print()
            
            # Recommendations
            recs = result.stage2_combined_analysis.recommendations
            print(f"💡 Recommendations:")
            print(f"   For Reviewers: {recs['for_reviewers'][:150]}...")
            print(f"   For Readers: {recs['for_readers'][:150]}...")
            print()
            
            print("=" * 80)
            print("✅ Results stored in Neo4j!")
            print("=" * 80)
            
        else:
            print("❌ Analysis failed - no result returned")
            
    except Exception as e:
        logger.error(f"Error during analysis: {e}", exc_info=True)
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)
    
    finally:
        workflow.close()
    
    print("\n✅ Workflow 5 complete!")


if __name__ == "__main__":
    main()
