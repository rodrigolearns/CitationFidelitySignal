#!/usr/bin/env python3
"""
Phase 2: Download XMLs for all papers in our citation network.

Downloads from GitHub with version fallback (v6 → v1).
Saves both versioned and unversioned copies for compatibility.
"""

import json
import asyncio
import aiohttp
from pathlib import Path
from typing import List, Set, Dict
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))


class XMLDownloader:
    """Download XMLs from GitHub with version fallback."""
    
    def __init__(self, scan_results_file: Path, samples_dir: Path):
        self.scan_results_file = scan_results_file
        self.samples_dir = Path(samples_dir)
        self.samples_dir.mkdir(exist_ok=True, parents=True)
        
        # Statistics
        self.stats = {
            'already_cached': 0,
            'downloaded': 0,
            'failed': 0,
            'errors': []
        }
    
    def _is_cached(self, article_id: str) -> bool:
        """Check if we already have the XML (any version)."""
        # Check for unversioned file
        unversioned = self.samples_dir / f"elife-{article_id}.xml"
        if unversioned.exists() and unversioned.stat().st_size > 1000:
            return True
        
        # Check for versioned files
        for version in range(1, 7):
            versioned = self.samples_dir / f"elife-{article_id}-v{version}.xml"
            if versioned.exists() and versioned.stat().st_size > 1000:
                return True
        
        return False
    
    async def _download_with_fallback(self, session: aiohttp.ClientSession, 
                                      article_id: str, known_version: int = None) -> Dict:
        """
        Download XML with version fallback.
        
        Args:
            article_id: eLife article ID
            known_version: If known, try this version first
        
        Returns:
            {'success': bool, 'version': int or None, 'error': str or None}
        """
        # If already cached, skip
        if self._is_cached(article_id):
            self.stats['already_cached'] += 1
            return {'success': True, 'version': 'cached', 'error': None}
        
        base_url = "https://raw.githubusercontent.com/elifesciences/elife-article-xml/master/articles"
        
        # Try versions in order: known_version first, then v6 down to v1
        versions_to_try = []
        if known_version:
            versions_to_try.append(known_version)
        
        # Add v6 down to v1
        for v in range(6, 0, -1):
            if v != known_version:
                versions_to_try.append(v)
        
        for version in versions_to_try:
            filename = f"elife-{article_id}-v{version}.xml"
            url = f"{base_url}/{filename}"
            
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        content = await response.read()
                        
                        # Validate content
                        if len(content) < 1000:
                            continue
                        
                        # Check if it's actually XML
                        try:
                            content_str = content.decode('utf-8')
                            if '<article' not in content_str[:500]:
                                continue
                        except:
                            continue
                        
                        # Save versioned copy
                        versioned_path = self.samples_dir / filename
                        with open(versioned_path, 'wb') as f:
                            f.write(content)
                        
                        # Save unversioned copy for compatibility
                        unversioned_path = self.samples_dir / f"elife-{article_id}.xml"
                        with open(unversioned_path, 'wb') as f:
                            f.write(content)
                        
                        self.stats['downloaded'] += 1
                        return {'success': True, 'version': version, 'error': None}
            
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                continue
        
        # All versions failed
        self.stats['failed'] += 1
        self.stats['errors'].append({'article_id': article_id, 'error': 'All versions failed'})
        return {'success': False, 'version': None, 'error': 'All versions failed'}
    
    async def download_batch(self, article_ids: List[str], 
                            known_versions: Dict[str, int] = None,
                            batch_name: str = "batch",
                            concurrent: int = 5):
        """
        Download a batch of XMLs concurrently.
        
        Args:
            article_ids: List of article IDs to download
            known_versions: Dict mapping article_id -> version (if known)
            batch_name: Name for progress display
            concurrent: Number of concurrent downloads
        """
        known_versions = known_versions or {}
        
        print(f"\n📥 Downloading {batch_name}: {len(article_ids)} papers")
        print(f"   Concurrency: {concurrent} downloads at a time")
        
        async with aiohttp.ClientSession() as session:
            # Create semaphore to limit concurrency
            semaphore = asyncio.Semaphore(concurrent)
            
            async def download_with_semaphore(article_id: str):
                async with semaphore:
                    known_ver = known_versions.get(article_id)
                    result = await self._download_with_fallback(session, article_id, known_ver)
                    return article_id, result
            
            # Download all
            tasks = [download_with_semaphore(aid) for aid in article_ids]
            
            # Process with progress updates
            results = []
            completed = 0
            
            for coro in asyncio.as_completed(tasks):
                article_id, result = await coro
                results.append((article_id, result))
                completed += 1
                
                if completed % 50 == 0 or completed == len(article_ids):
                    print(f"   [{completed:4d}/{len(article_ids)}] "
                          f"Cached: {self.stats['already_cached']}, "
                          f"Downloaded: {self.stats['downloaded']}, "
                          f"Failed: {self.stats['failed']}")
        
        return results
    
    async def download_all(self):
        """Download all papers from scan results."""
        # Load scan results
        with open(self.scan_results_file, 'r') as f:
            scan_data = json.load(f)
        
        print("=" * 70)
        print("📥 PHASE 2: DOWNLOADING XMLs FROM GITHUB")
        print("=" * 70)
        
        # Get citing papers (we know their versions)
        citing_papers = scan_data['citing_papers']
        citing_ids = [p['article_id'] for p in citing_papers]
        citing_versions = {p['article_id']: p['version'] for p in citing_papers}
        
        print(f"\n📊 Papers to download:")
        print(f"  Citing papers (our 1,000): {len(citing_ids)}")
        
        # Get cited papers (we don't know versions, will try fallback)
        cited_ids = scan_data['cited_paper_ids']
        
        # Find overlap (dual-role papers)
        overlap = set(citing_ids).intersection(set(cited_ids))
        
        # Remove overlap from cited_ids (already in citing_ids)
        cited_only_ids = [cid for cid in cited_ids if cid not in overlap]
        
        print(f"  Cited papers (additional): {len(cited_only_ids)}")
        print(f"  Dual-role papers: {len(overlap)} (counted in citing papers)")
        print(f"  ────────────────────────────")
        print(f"  TOTAL UNIQUE: {len(citing_ids) + len(cited_only_ids)}")
        
        # Download citing papers first (we have versions)
        await self.download_batch(
            citing_ids,
            known_versions=citing_versions,
            batch_name="CITING PAPERS",
            concurrent=5
        )
        
        # Download cited papers (no version info, use fallback)
        await self.download_batch(
            cited_only_ids,
            known_versions={},
            batch_name="CITED PAPERS",
            concurrent=5
        )
        
        # Final statistics
        print("\n" + "=" * 70)
        print("📊 DOWNLOAD SUMMARY")
        print("=" * 70)
        print(f"Already cached: {self.stats['already_cached']}")
        print(f"Newly downloaded: {self.stats['downloaded']}")
        print(f"Failed: {self.stats['failed']}")
        print(f"Total papers needed: {len(citing_ids) + len(cited_only_ids)}")
        
        success_rate = (self.stats['already_cached'] + self.stats['downloaded']) / (len(citing_ids) + len(cited_only_ids)) * 100
        print(f"\n✅ Success rate: {success_rate:.1f}%")
        
        if self.stats['failed'] > 0:
            print(f"\n⚠️  {self.stats['failed']} papers failed to download")
            print(f"   (These may be retracted, unpublished, or have restricted access)")
            
            # Save failed IDs
            failed_file = self.samples_dir.parent / "failed_downloads.json"
            with open(failed_file, 'w') as f:
                json.dump({
                    'failed_at': datetime.now().isoformat(),
                    'count': self.stats['failed'],
                    'errors': self.stats['errors']
                }, f, indent=2)
            print(f"   Failed IDs saved to: {failed_file}")
        
        print("=" * 70)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Download XMLs for target papers')
    parser.add_argument('--scan-results', type=str, 
                        default='data/scan_results_1000.json',
                        help='Path to scan results JSON')
    parser.add_argument('--samples-dir', type=str,
                        default='data/samples',
                        help='Directory to save XMLs')
    args = parser.parse_args()
    
    # Paths
    project_root = Path(__file__).parent.parent
    scan_results_file = project_root / args.scan_results
    samples_dir = project_root / args.samples_dir
    
    if not scan_results_file.exists():
        print(f"❌ Scan results not found: {scan_results_file}")
        print(f"   Run: python3 scripts/scan_all_target_papers.py")
        sys.exit(1)
    
    # Run download
    downloader = XMLDownloader(scan_results_file, samples_dir)
    
    try:
        asyncio.run(downloader.download_all())
    except KeyboardInterrupt:
        print("\n\n⚠️  Download interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
