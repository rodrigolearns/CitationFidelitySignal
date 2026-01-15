#!/usr/bin/env python3
"""
Run Workflow 5 (Impact Assessment) on top 10 most problematic papers.
Uses ThreadPoolExecutor instead of ProcessPoolExecutor to avoid pickling issues.
"""
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import asyncio
import aiohttp
import time

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from elife_graph_builder.impact_assessment import ImpactAssessmentWorkflow
from elife_graph_builder.config import Config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Top 10 problematic papers (based on confirmed suspicious citations)
TARGET_PAPERS = [
    ('89106', 52),  # (article_id, suspicious_count)
    ('88824', 36),
    ('97964', 19),
    ('106042', 18),
    ('98563', 17),
    ('99473', 15),
    ('101992', 15),
    ('102226', 12),
    ('93906', 11),
    ('102230', 10)
]


async def download_xml_if_needed(article_id: str) -> bool:
    """Download XML from GitHub if not already cached."""
    samples_dir = Config.SAMPLES_DIR
    
    # Check if unversioned file exists
    xml_path_unversioned = samples_dir / f"elife-{article_id}.xml"
    if xml_path_unversioned.exists():
        return True
    
    # Check versioned files
    for version in range(6, 0, -1):
        xml_path = samples_dir / f"elife-{article_id}-v{version}.xml"
        if xml_path.exists():
            # Create unversioned copy
            xml_path_unversioned.write_bytes(xml_path.read_bytes())
            return True
    
    # Download from GitHub
    logger.info(f"📥 Downloading XML for article {article_id}...")
    base_url = "https://raw.githubusercontent.com/elifesciences/elife-article-xml/master/articles"
    
    async with aiohttp.ClientSession() as session:
        for version in range(6, 0, -1):
            url = f"{base_url}/elife-{article_id}-v{version}.xml"
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        body = await response.read()
                        if body and len(body) > 1000:
                            # Save versioned
                            xml_path_versioned = samples_dir / f"elife-{article_id}-v{version}.xml"
                            xml_path_versioned.write_bytes(body)
                            # Save unversioned copy
                            xml_path_unversioned.write_bytes(body)
                            logger.info(f"✅ Downloaded: elife-{article_id}-v{version}.xml")
                            return True
            except Exception as e:
                continue
    
    logger.error(f"❌ Could not download XML for article {article_id}")
    return False


def analyze_single_paper(article_id: str, suspicious_count: int) -> dict:
    """Analyze a single paper (thread-safe)."""
    try:
        logger.info(f"🔄 Starting analysis: Article {article_id} ({suspicious_count} suspicious citations)")
        
        # Download XML if needed
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        xml_available = loop.run_until_complete(download_xml_if_needed(article_id))
        loop.close()
        
        if not xml_available:
            return {
                'article_id': article_id,
                'success': False,
                'error': 'XML not available'
            }
        
        # Run analysis
        pipeline = ImpactAssessmentWorkflow()
        result = pipeline.analyze_paper(article_id)
        
        if result:
            logger.info(f"✅ Completed: Article {article_id} → {result.overall_classification}")
            return {
                'article_id': article_id,
                'success': True,
                'classification': result.overall_classification,
                'suspicious_count': suspicious_count
            }
        else:
            return {
                'article_id': article_id,
                'success': False,
                'error': 'Analysis returned None'
            }
            
    except Exception as e:
        logger.error(f"❌ Error analyzing {article_id}: {e}")
        return {
            'article_id': article_id,
            'success': False,
            'error': str(e)
        }


def main():
    start_time = time.time()
    
    print("\n" + "="*80)
    print("🎯 WORKFLOW 5: IMPACT ASSESSMENT - TOP 10 PROBLEMATIC PAPERS")
    print("="*80)
    print(f"\nTarget papers: {len(TARGET_PAPERS)}")
    for idx, (article_id, count) in enumerate(TARGET_PAPERS, 1):
        print(f"  #{idx}: Article {article_id} ({count} suspicious citations)")
    print("="*80)
    print()
    
    results = []
    
    # Use ThreadPoolExecutor with 5 workers (analyze 5 papers concurrently)
    print("Starting parallel analysis with 5 concurrent workers...\n")
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_article = {
            executor.submit(analyze_single_paper, article_id, count): (article_id, count)
            for article_id, count in TARGET_PAPERS
        }
        
        for future in as_completed(future_to_article):
            article_id, count = future_to_article[future]
            try:
                result = future.result()
                results.append(result)
                
                progress = f"[{len(results)}/{len(TARGET_PAPERS)}]"
                if result['success']:
                    print(f"{progress} ✅ Article {result['article_id']}: {result['classification']}")
                else:
                    print(f"{progress} ❌ Article {result['article_id']}: {result['error']}")
                    
            except Exception as e:
                print(f"❌ Exception: {e}")
                results.append({
                    'article_id': article_id,
                    'success': False,
                    'error': str(e)
                })
    
    elapsed = time.time() - start_time
    
    # Summary
    print("\n" + "="*80)
    print("📊 WORKFLOW 5 - SUMMARY")
    print("="*80)
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"\nTime: {elapsed/60:.1f} minutes")
    print(f"Rate: {len(TARGET_PAPERS)/elapsed*60:.1f} papers/hour")
    print(f"\n✅ Successful: {len(successful)}/{len(results)}")
    print(f"❌ Failed: {len(failed)}/{len(results)}")
    
    if successful:
        print("\n✅ Impact Classifications:")
        classification_counts = {}
        for r in successful:
            classification = r['classification']
            classification_counts[classification] = classification_counts.get(classification, 0) + 1
            print(f"  • Article {r['article_id']} ({r['suspicious_count']} issues): {classification}")
        
        print("\n📊 Classification Distribution:")
        for classification, count in sorted(classification_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {classification}: {count} papers")
    
    if failed:
        print("\n❌ Failed Papers:")
        for r in failed:
            print(f"  • Article {r['article_id']}: {r['error'][:80]}")
    
    print("="*80)
    print()
    
    return 0 if len(failed) == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
