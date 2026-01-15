#!/usr/bin/env python3
"""
Phase 1: Scan target papers via API to identify which cite eLife.

This is a lightweight scan that only queries the API for reference metadata,
WITHOUT downloading XMLs. Papers with eLife citations are saved for Phase 2.
"""

import json
import time
import requests
from pathlib import Path
from typing import List, Dict, Set
from collections import defaultdict
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


class TargetPaperScanner:
    """Scan papers via API to find eLife citations."""
    
    def __init__(self, target_file: Path, output_dir: Path):
        self.target_file = target_file
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Rate limiting
        self.requests_count = 0
        self.start_time = time.time()
        self.max_requests_per_second = 10  # Be conservative
        
    def _rate_limit(self):
        """Respect rate limits."""
        self.requests_count += 1
        
        # Every 10 requests, check if we need to slow down
        if self.requests_count % 10 == 0:
            elapsed = time.time() - self.start_time
            expected_time = self.requests_count / self.max_requests_per_second
            if elapsed < expected_time:
                sleep_time = expected_time - elapsed
                time.sleep(sleep_time)
    
    def _extract_elife_id_from_doi(self, doi: str) -> str:
        """
        Extract eLife article ID from DOI.
        
        Format: 10.7554/eLife.12345 or 10.7554/eLife.12345.001
        """
        doi_lower = doi.lower()
        if 'elife' not in doi_lower:
            return None
        
        # Split by 'elife.'
        parts = doi_lower.split('elife.')
        if len(parts) < 2:
            return None
        
        # Get ID (might have version suffix like .001)
        article_id = parts[1].split('.')[0].split('/')[0]
        
        # Remove any non-numeric characters
        article_id = ''.join(c for c in article_id if c.isdigit())
        
        return article_id if article_id else None
    
    def scan_paper(self, article_id: str, retry_count: int = 3) -> Dict:
        """
        Scan a single paper for eLife citations.
        
        Returns:
            {
                'article_id': str,
                'success': bool,
                'error': str or None,
                'total_references': int,
                'elife_citations': List[str],  # List of cited eLife article IDs
                'elife_dois': List[str]  # List of DOIs for verification
            }
        """
        url = f"https://api.elifesciences.org/articles/{article_id}"
        
        for attempt in range(retry_count):
            try:
                self._rate_limit()
                
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    references = data.get('references', [])
                    
                    # Find eLife references
                    elife_citations = []
                    elife_dois = []
                    
                    for ref in references:
                        doi = ref.get('doi', '').lower()
                        
                        # Check if it's an eLife reference
                        if 'elife' in doi:
                            elife_dois.append(doi)
                            
                            # Extract article ID
                            ref_id = self._extract_elife_id_from_doi(doi)
                            if ref_id:
                                elife_citations.append(ref_id)
                    
                    return {
                        'article_id': article_id,
                        'success': True,
                        'error': None,
                        'total_references': len(references),
                        'elife_citations': elife_citations,
                        'elife_dois': elife_dois
                    }
                
                elif response.status_code == 404:
                    return {
                        'article_id': article_id,
                        'success': False,
                        'error': 'NOT_FOUND',
                        'total_references': 0,
                        'elife_citations': [],
                        'elife_dois': []
                    }
                
                elif response.status_code == 429:
                    # Rate limited - wait and retry
                    wait_time = (attempt + 1) * 2
                    print(f"  ⚠️  Rate limited on {article_id}, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                else:
                    # Other error - retry
                    if attempt < retry_count - 1:
                        time.sleep(1)
                        continue
                    
                    return {
                        'article_id': article_id,
                        'success': False,
                        'error': f'HTTP_{response.status_code}',
                        'total_references': 0,
                        'elife_citations': [],
                        'elife_dois': []
                    }
            
            except requests.exceptions.Timeout:
                if attempt < retry_count - 1:
                    time.sleep(1)
                    continue
                return {
                    'article_id': article_id,
                    'success': False,
                    'error': 'TIMEOUT',
                    'total_references': 0,
                    'elife_citations': [],
                    'elife_dois': []
                }
            
            except Exception as e:
                if attempt < retry_count - 1:
                    time.sleep(1)
                    continue
                return {
                    'article_id': article_id,
                    'success': False,
                    'error': str(e),
                    'total_references': 0,
                    'elife_citations': [],
                    'elife_dois': []
                }
        
        # Should not reach here
        return {
            'article_id': article_id,
            'success': False,
            'error': 'MAX_RETRIES',
            'total_references': 0,
            'elife_citations': [],
            'elife_dois': []
        }
    
    def scan_batch(self, batch_num: int, batch_size: int = 250) -> Dict:
        """
        Scan a batch of papers.
        
        Args:
            batch_num: Batch number (1-4)
            batch_size: Papers per batch (default 250)
        
        Returns:
            Summary statistics and results
        """
        # Load target papers
        with open(self.target_file, 'r') as f:
            target_data = json.load(f)
            all_papers = target_data['papers']
        
        # Calculate batch range
        start_idx = (batch_num - 1) * batch_size
        end_idx = min(start_idx + batch_size, len(all_papers))
        batch_papers = all_papers[start_idx:end_idx]
        
        print("=" * 70)
        print(f"📡 PHASE 1: API SCAN - BATCH {batch_num}")
        print("=" * 70)
        print(f"Papers in batch: {len(batch_papers)} (#{start_idx+1} to #{end_idx})")
        print(f"Rate limit: {self.max_requests_per_second} req/sec")
        print()
        
        results = []
        citing_papers = []
        errors = defaultdict(int)
        
        for i, paper in enumerate(batch_papers, 1):
            article_id = paper['article_id']
            
            if i % 25 == 0:
                print(f"  Progress: {i}/{len(batch_papers)} papers scanned...")
            
            result = self.scan_paper(article_id)
            results.append(result)
            
            if result['success']:
                if result['elife_citations']:
                    citing_papers.append(result)
            else:
                errors[result['error']] += 1
        
        # Summary
        successful = sum(1 for r in results if r['success'])
        total_citing = len(citing_papers)
        total_elife_citations = sum(len(r['elife_citations']) for r in citing_papers)
        
        print()
        print("=" * 70)
        print("📊 BATCH SUMMARY")
        print("=" * 70)
        print(f"Papers scanned: {len(results)}")
        print(f"Successful: {successful}")
        print(f"Errors: {len(results) - successful}")
        if errors:
            for error_type, count in errors.items():
                print(f"  - {error_type}: {count}")
        print()
        print(f"✅ Papers citing eLife: {total_citing}")
        print(f"✅ Total eLife citations found: {total_elife_citations}")
        
        if citing_papers:
            print(f"\nTop citing papers:")
            sorted_citing = sorted(citing_papers, key=lambda x: len(x['elife_citations']), reverse=True)
            for cp in sorted_citing[:5]:
                print(f"  - {cp['article_id']}: {len(cp['elife_citations'])} eLife citations")
        
        # Save results
        output_file = self.output_dir / f"scan_results_batch{batch_num}.json"
        with open(output_file, 'w') as f:
            json.dump({
                'batch_num': batch_num,
                'batch_size': len(batch_papers),
                'start_index': start_idx,
                'end_index': end_idx,
                'scanned_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'summary': {
                    'total_scanned': len(results),
                    'successful': successful,
                    'errors': dict(errors),
                    'papers_citing_elife': total_citing,
                    'total_elife_citations': total_elife_citations
                },
                'results': results,
                'citing_papers': citing_papers
            }, f, indent=2)
        
        print(f"\n💾 Results saved to: {output_file}")
        print("=" * 70)
        
        return {
            'citing_papers': citing_papers,
            'total_citing': total_citing,
            'total_citations': total_elife_citations
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Scan target papers for eLife citations')
    parser.add_argument('--batch', type=int, required=True, choices=[1, 2, 3, 4],
                        help='Batch number (1=papers 1-250, 2=251-500, 3=501-750, 4=751-1000)')
    parser.add_argument('--batch-size', type=int, default=250,
                        help='Papers per batch (default: 250)')
    args = parser.parse_args()
    
    # Paths
    project_root = Path(__file__).parent.parent
    target_file = project_root / "data" / "target_papers_1000.json"
    output_dir = project_root / "data" / "scan_results"
    
    if not target_file.exists():
        print(f"❌ Target file not found: {target_file}")
        sys.exit(1)
    
    # Run scan
    scanner = TargetPaperScanner(target_file, output_dir)
    
    try:
        scanner.scan_batch(args.batch, args.batch_size)
    except KeyboardInterrupt:
        print("\n\n⚠️  Scan interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
