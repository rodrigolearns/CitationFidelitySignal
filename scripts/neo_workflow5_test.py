#!/usr/bin/env python3
"""
NeoWorkflow 5 Test Script

Run NeoWorkflow 5 on a single paper: Article 89106
"Evidence for deliberate burial of the dead by Homo naledi"

This is a test run to verify the reference-centric analysis works before
running on more papers.
"""

import sys
import json
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from elife_graph_builder.analyzers.neo_impact_analyzer import NeoImpactAnalyzer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_citation_contexts(article_id: str) -> list:
    """
    Fetch all citation contexts for a paper from Neo4j.
    
    Returns list of CitationContext objects (suspicious + supporting).
    """
    # Import after sys.path is set up
    sys.path.insert(0, str(Path(__file__).parent.parent / 'web_interface' / 'backend'))
    from neo4j_client import Neo4jClient
    
    client = Neo4jClient()
    contexts = []
    
    with client.driver.session() as session:
        # Fetch all citations (qualified=true means suspicious, qualified=false means supporting)
        result = session.run("""
            MATCH (source:Article {article_id: $article_id})-[c:CITES]->(target:Article)
            WHERE c.citation_contexts_json IS NOT NULL
            RETURN target.article_id as target_id,
                   target.title as target_title,
                   target.authors as target_authors,
                   target.pub_year as target_year,
                   c.citation_contexts_json as contexts_json,
                   c.qualified as is_suspicious
        """, article_id=article_id)
        
        for record in result:
            contexts_data = json.loads(record['contexts_json']) if record['contexts_json'] else []
            is_suspicious = record['is_suspicious']
            
            for ctx_data in contexts_data:
                # Extract classification info
                classification_info = ctx_data.get('classification', {})
                if isinstance(classification_info, dict):
                    classification_category = classification_info.get('category', 'UNKNOWN')
                    classification_reasoning = classification_info.get('justification', '')
                else:
                    classification_category = 'UNKNOWN'
                    classification_reasoning = ''
                
                # Map category to HIGH/MODERATE/MINOR_CONCERN
                if classification_category in ['CONTRADICT', 'MISQUOTE']:
                    mapped_classification = 'HIGH_CONCERN'
                elif classification_category in ['NOT_SUBSTANTIATE', 'OVERSIMPLIFY']:
                    mapped_classification = 'MODERATE_CONCERN'
                elif classification_category == 'LEGITIMATE':
                    mapped_classification = 'FALSE_ALARM'
                else:
                    mapped_classification = 'MINOR_CONCERN'
                
                # Create context dict (simpler than full Pydantic model)
                context = {
                    'citing_article_id': article_id,
                    'target_article_id': record['target_id'],
                    'section_name': ctx_data.get('section_name', 'Unknown'),
                    'context_text': ctx_data.get('context_text', ''),
                    'in_text_citation': ctx_data.get('in_text_citation', ''),
                    'target_authors': record['target_authors'] or [],
                    'target_year': record['target_year'],
                    # Classification from Workflow 2/3
                    'classification': mapped_classification,
                    'reasoning': classification_reasoning,
                    'evidence_passages': ctx_data.get('evidence_passages', [])
                }
                
                contexts.append(context)
    
    return contexts


def main():
    """Run NeoWorkflow 5 on Article 89106."""
    
    article_id = "89106"
    
    logger.info("=" * 80)
    logger.info("NeoWorkflow 5 Test: Article 89106")
    logger.info("=" * 80)
    
    # Step 1: Fetch all citation contexts
    logger.info(f"Fetching citation contexts for Article {article_id}...")
    contexts = fetch_citation_contexts(article_id)
    logger.info(f"Found {len(contexts)} citation contexts")
    
    if not contexts:
        logger.error("No contexts found - cannot proceed")
        return
    
    # Count suspicious vs supporting
    suspicious = [c for c in contexts if c['classification'] in ['HIGH_CONCERN', 'MODERATE_CONCERN', 'MINOR_CONCERN']]
    supporting = [c for c in contexts if c not in suspicious]
    
    logger.info(f"Suspicious: {len(suspicious)}, Supporting: {len(supporting)}")
    
    # Step 2: Find citing paper XML
    xml_path = Path(f"data/samples/elife-{article_id}.xml")
    if not xml_path.exists():
        # Try versioned
        versioned = list(Path("data/samples").glob(f"elife-{article_id}-v*.xml"))
        if versioned:
            xml_path = versioned[0]
        else:
            logger.error(f"Could not find XML for Article {article_id}")
            logger.error(f"Tried: data/samples/elife-{article_id}.xml and elife-{article_id}-v*.xml")
            return
    
    logger.info(f"Using citing paper XML: {xml_path}")
    
    # Step 3: Run NeoWorkflow 5
    logger.info("Initializing NeoImpactAnalyzer...")
    analyzer = NeoImpactAnalyzer(provider='deepseek', model='deepseek-reasoner')
    
    logger.info("Running NEO analysis...")
    result = analyzer.run_neo_analysis(
        citing_paper_id=article_id,
        citing_paper_path=xml_path,
        all_contexts=contexts
    )
    
    # Step 4: Save to Neo4j
    logger.info("Saving NEO results to Neo4j...")
    sys.path.insert(0, str(Path(__file__).parent.parent / 'web_interface' / 'backend'))
    from neo4j_client import Neo4jClient
    client = Neo4jClient()
    success = client.save_neo_impact_analysis(article_id, result)
    
    if success:
        logger.info("✓ NEO analysis saved successfully")
    else:
        logger.error("✗ Failed to save NEO analysis")
    
    # Step 5: Print summary
    logger.info("=" * 80)
    logger.info("NEO ANALYSIS SUMMARY")
    logger.info("=" * 80)
    logger.info(f"References analyzed: {result['metadata']['total_references_analyzed']}")
    logger.info(f"Suspicious citations: {result['metadata']['total_suspicious_citations']}")
    logger.info(f"Supporting citations: {result['metadata']['total_supporting_citations']}")
    logger.info(f"Overall classification: {result['synthesis'].get('overall_classification', 'UNKNOWN')}")
    logger.info("")
    logger.info("Executive Summary:")
    logger.info(result['synthesis']['executive_summary'])
    logger.info("")
    logger.info("✓ NeoWorkflow 5 test complete!")
    
    # Save to file for inspection
    output_file = Path(f"data/analysis/neo_analysis_{article_id}.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    logger.info(f"Full results saved to: {output_file}")


if __name__ == "__main__":
    main()
