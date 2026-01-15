#!/usr/bin/env python3
"""
Run Workflow 5 (Deep Impact Analysis) on multiple problematic papers in parallel.
"""

import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import logging
import asyncio
import aiohttp

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from elife_graph_builder.impact_assessment import ImpactAssessmentWorkflow
from elife_graph_builder.graph.neo4j_importer import StreamingNeo4jImporter
from elife_graph_builder.config import Config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def download_xml_if_needed(article_id: str) -> bool:
    """
    Download XML from GitHub if not already cached.
    
    Args:
        article_id: Article ID
        
    Returns:
        True if XML is available (cached or downloaded), False otherwise
    """
    samples_dir = Config.SAMPLES_DIR
    
    # Check if unversioned file exists (created by this script or backend)
    xml_path_unversioned = samples_dir / f"elife-{article_id}.xml"
    if xml_path_unversioned.exists():
        logger.info(f"✅ XML already cached: {xml_path_unversioned.name}")
        return True
    
    # Check if any versioned file exists
    for version in range(6, 0, -1):
        xml_path = samples_dir / f"elife-{article_id}-v{version}.xml"
        if xml_path.exists():
            logger.info(f"✅ XML already cached: {xml_path.name}")
            # Create unversioned copy for workflow compatibility
            xml_path_unversioned.write_bytes(xml_path.read_bytes())
            return True
    
    # Try to download
    logger.info(f"📥 Downloading XML for article {article_id}...")
    
    async with aiohttp.ClientSession() as session:
        for version in range(6, 0, -1):
            url = f"https://github.com/elifesciences/elife-article-xml/raw/master/articles/elife-{article_id}-v{version}.xml"
            
            try:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        content = await response.read()
                        
                        # Validate content
                        if len(content) < 100 or not content.strip():
                            logger.warning(f"  v{version} has no body content, skipping...")
                            continue
                        
                        # Save to disk with version
                        xml_path_versioned = samples_dir / f"elife-{article_id}-v{version}.xml"
                        xml_path_versioned.write_bytes(content)
                        
                        # Also save without version suffix (for workflow compatibility)
                        xml_path_unversioned = samples_dir / f"elife-{article_id}.xml"
                        xml_path_unversioned.write_bytes(content)
                        
                        logger.info(f"✅ Downloaded v{version} successfully")
                        return True
                    elif response.status == 404:
                        logger.debug(f"  v{version} not found (404)")
                    else:
                        logger.warning(f"  v{version} returned status {response.status}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"  v{version} download timeout")
            except Exception as e:
                logger.warning(f"  v{version} download error: {e}")
    
    logger.error(f"❌ Could not download XML for article {article_id}")
    return False


def analyze_single_paper(article_id: str) -> dict:
    """
    Analyze a single paper in a separate process.
    
    Args:
        article_id: Article ID to analyze
        
    Returns:
        Dict with article_id, success, and error (if any)
    """
    try:
        logger.info(f"🎯 Starting Workflow 5 for article {article_id}...")
        
        # Download XML if needed (sync wrapper for async function)
        xml_available = asyncio.run(download_xml_if_needed(article_id))
        if not xml_available:
            raise ValueError(f"Could not download XML for article {article_id}")
        
        # Create workflow instance
        workflow = ImpactAssessmentWorkflow()
        
        # Run analysis
        result = workflow.analyze_paper(article_id)
        
        logger.info(f"✅ Completed article {article_id} - Classification: {result.overall_classification}")
        
        return {
            'article_id': article_id,
            'success': True,
            'classification': result.overall_classification,
            'error': None
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to analyze article {article_id}: {e}")
        return {
            'article_id': article_id,
            'success': False,
            'classification': None,
            'error': str(e)
        }


def get_problematic_papers():
    """Fetch list of problematic papers from Neo4j with their analysis status."""
    import json
    from collections import Counter
    
    logger.info("📊 Fetching problematic papers from Neo4j...")
    
    importer = StreamingNeo4jImporter()
    
    with importer.driver.session() as session:
        result = session.run("""
            MATCH (source:Article)-[c:CITES]->(target:Article)
            WHERE c.qualified = true AND c.citation_contexts_json IS NOT NULL
            RETURN source.article_id as article_id,
                   source.impact_classification as impact_classification,
                   c.citation_contexts_json as contexts_json
        """)
        
        # Count problematic citations per paper and track analysis status
        problematic_counts = Counter()
        paper_status = {}  # Track impact_classification for each paper
        
        for record in result:
            article_id = record['article_id']
            contexts = json.loads(record['contexts_json'])
            impact_classification = record.get('impact_classification')
            
            # Count NOT_SUBSTANTIATE, CONTRADICT, MISQUOTE
            problematic = 0
            for context in contexts:
                if context.get('classification'):
                    category = context['classification'].get('category', '')
                    if category in ['NOT_SUBSTANTIATE', 'CONTRADICT', 'MISQUOTE']:
                        problematic += 1
            
            if problematic > 0:
                problematic_counts[article_id] += problematic
                paper_status[article_id] = impact_classification or 'NOT_PERFORMED'
        
        # Convert to list with status and sort
        papers = [
            (article_id, count, paper_status[article_id]) 
            for article_id, count in problematic_counts.most_common()
        ]
        papers = [p for p in papers if p[1] >= 5]  # Filter to papers with 5+ problematic citations
    
    importer.close()
    logger.info(f"Found {len(papers)} papers with 5+ problematic citations")
    return papers


def main():
    """Run Workflow 5 analysis on 2 NOT_PERFORMED papers in parallel."""
    
    # Get all problematic papers
    papers = get_problematic_papers()
    
    if not papers:
        logger.error("❌ No problematic papers found in database")
        return 1
    
    logger.info(f"📋 Found {len(papers)} problematic papers total")
    
    # Filter for NOT_PERFORMED papers
    not_performed = [p for p in papers if p[2] == 'NOT_PERFORMED']
    
    if not not_performed:
        logger.warning("⚠️  All papers have been analyzed!")
        logger.info("Papers status:")
        for article_id, count, status in papers[:10]:
            logger.info(f"  • Article {article_id} ({count} citations): {status}")
        return 0
    
    logger.info(f"📋 Found {len(not_performed)} NOT_PERFORMED papers")
    
    # Select first 2 NOT_PERFORMED papers
    target_papers = not_performed[:2]
    
    logger.info(f"\n{'='*80}")
    logger.info("🚀 Starting Parallel Workflow 5 Analysis (Test Run)")
    logger.info(f"{'='*80}")
    logger.info(f"Target papers (2 NOT_PERFORMED):")
    for idx, (article_id, count, status) in enumerate(target_papers, start=1):
        logger.info(f"  #{idx}: Article {article_id} ({count} problematic citations) - Status: {status}")
    logger.info(f"{'='*80}\n")
    
    # Run analyses in parallel using ProcessPoolExecutor
    article_ids = [paper[0] for paper in target_papers]
    results = []
    
    # Use 2 workers (one per paper)
    with ProcessPoolExecutor(max_workers=2) as executor:
        # Submit all jobs
        future_to_article = {
            executor.submit(analyze_single_paper, article_id): article_id 
            for article_id in article_ids
        }
        
        # Process results as they complete
        for future in as_completed(future_to_article):
            article_id = future_to_article[future]
            try:
                result = future.result()
                results.append(result)
                
                if result['success']:
                    logger.info(f"✅ [{len(results)}/{len(article_ids)}] Article {result['article_id']}: {result['classification']}")
                else:
                    logger.error(f"❌ [{len(results)}/{len(article_ids)}] Article {result['article_id']}: {result['error']}")
                    
            except Exception as e:
                logger.error(f"❌ Exception processing article {article_id}: {e}")
                results.append({
                    'article_id': article_id,
                    'success': False,
                    'error': str(e)
                })
    
    # Print summary
    logger.info(f"\n{'='*80}")
    logger.info("📊 WORKFLOW 5 PARALLEL ANALYSIS - SUMMARY")
    logger.info(f"{'='*80}")
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    logger.info(f"✅ Successful: {len(successful)}/{len(results)}")
    logger.info(f"❌ Failed: {len(failed)}/{len(results)}")
    
    if successful:
        logger.info("\n✅ Successful Analyses:")
        for r in successful:
            logger.info(f"  • Article {r['article_id']}: {r['classification']}")
    
    if failed:
        logger.info("\n❌ Failed Analyses:")
        for r in failed:
            logger.info(f"  • Article {r['article_id']}: {r['error'][:100]}...")
    
    logger.info(f"{'='*80}\n")
    
    return 0 if len(failed) == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
