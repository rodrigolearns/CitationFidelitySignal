#!/usr/bin/env python3
"""
Phase 1: Comprehensive scan of all 1,000 target papers.

Collects:
- Which papers cite eLife
- Full citation details (DOI, title, authors)
- Version info for citing papers
- Optionally: latest version for cited papers
"""

import json
import time
import requests
from pathlib import Path
from typing import List, Dict, Set
from collections import defaultdict
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))


class ComprehensiveScanner:
    """Scan all target papers and collect comprehensive citation data."""
    
    def __init__(self, target_file: Path, output_file: Path):
        self.target_file = target_file
        self.output_file = output_file
        
        # Rate limiting
        self.requests_count = 0
        self.start_time = time.time()
        self.max_requests_per_second = 10
        
        # Cache for version lookups
        self.version_cache = {}
        
    def _rate_limit(self):
        """Respect rate limits."""
        self.requests_count += 1
        if self.requests_count % 10 == 0:
            elapsed = time.time() - self.start_time
            expected_time = self.requests_count / self.max_requests_per_second
            if elapsed < expected_time:
                time.sleep(expected_time - elapsed)
    
    def _extract_elife_id_from_doi(self, doi: str) -> str:
        """Extract eLife article ID from DOI."""
        doi_lower = doi.lower()
        if 'elife' not in doi_lower:
            return None
        
        parts = doi_lower.split('elife.')
        if len(parts) < 2:
            return None
        
        article_id = parts[1].split('.')[0].split('/')[0]
        article_id = ''.join(c for c in article_id if c.isdigit())
        
        return article_id if article_id else None
    
    def get_latest_version(self, article_id: str) -> int:
        """
        Query the versions endpoint to get latest version.
        Uses cache to avoid duplicate queries.
        """
        if article_id in self.version_cache:
            return self.version_cache[article_id]
        
        url = f"https://api.elifesciences.org/articles/{article_id}/versions"
        
        try:
            self._rate_limit()
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                versions = data.get('versions', [])
                if versions:
                    # Versions are usually sorted, latest first
                    # But let's find the max version number to be safe
                    latest = max(v.get('version', 1) for v in versions)
                    self.version_cache[article_id] = latest
                    return latest
        except:
            pass
        
        # Default to version 1 if we can't determine
        self.version_cache[article_id] = 1
        return 1
    
    def scan_paper(self, article_id: str, paper_metadata: Dict, 
                   check_versions: bool = False) -> Dict:
        """
        Scan a single paper comprehensively.
        
        Returns detailed info about the paper and its eLife citations.
        """
        url = f"https://api.elifesciences.org/articles/{article_id}"
        
        try:
            self._rate_limit()
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract citing paper metadata
                citing_paper_info = {
                    'article_id': article_id,
                    'title': data.get('title', paper_metadata.get('title', '')),
                    'doi': data.get('doi', paper_metadata.get('doi', '')),
                    'version': data.get('version', 1),
                    'published': data.get('published', paper_metadata.get('published', '')),
                    'volume': data.get('volume', paper_metadata.get('volume', '')),
                    'status': data.get('status', 'unknown'),
                    'total_references': 0,
                    'elife_citations': []
                }
                
                # Process references
                references = data.get('references', [])
                citing_paper_info['total_references'] = len(references)
                
                for ref in references:
                    doi = ref.get('doi', '')
                    
                    if 'elife' in doi.lower():
                        # Extract cited article ID
                        cited_id = self._extract_elife_id_from_doi(doi)
                        if not cited_id:
                            continue
                        
                        # Build citation record
                        citation_info = {
                            'cited_article_id': cited_id,
                            'doi': doi,
                            'title': ref.get('articleTitle', ref.get('title', '')),
                            'journal': ref.get('journal', ''),
                            'year': ref.get('date', ref.get('year', '')),
                            'volume': ref.get('volume', ''),
                            'pages': ref.get('pages', ''),
                            'pmid': ref.get('pmid', '')
                        }
                        
                        # Extract authors if available
                        if 'authors' in ref:
                            authors = ref['authors']
                            if authors:
                                # Format: "Surname GivenNames"
                                author_strings = []
                                for author in authors[:3]:  # First 3 authors
                                    if isinstance(author, dict):
                                        surname = author.get('surname', '')
                                        given = author.get('givenNames', '')
                                        if surname:
                                            author_strings.append(f"{surname} {given}".strip())
                                
                                if author_strings:
                                    citation_info['authors'] = author_strings
                                    if len(authors) > 3:
                                        citation_info['authors_count'] = len(authors)
                        
                        # Optionally get latest version
                        if check_versions:
                            citation_info['latest_version'] = self.get_latest_version(cited_id)
                        
                        citing_paper_info['elife_citations'].append(citation_info)
                
                return {
                    'success': True,
                    'error': None,
                    'data': citing_paper_info
                }
            
            elif response.status_code == 404:
                return {'success': False, 'error': 'NOT_FOUND', 'data': None}
            else:
                return {'success': False, 'error': f'HTTP_{response.status_code}', 'data': None}
        
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'TIMEOUT', 'data': None}
        except Exception as e:
            return {'success': False, 'error': str(e), 'data': None}
    
    def scan_all(self, check_versions: bool = False):
        """
        Scan all 1,000 papers.
        
        Args:
            check_versions: If True, query for latest version of each cited paper
                           (adds ~1 API call per unique cited paper, slower but more complete)
        """
        # Load target papers
        with open(self.target_file, 'r') as f:
            target_data = json.load(f)
            all_papers = target_data['papers']
        
        print("=" * 70)
        print("📡 PHASE 1: COMPREHENSIVE SCAN OF 1,000 PAPERS")
        print("=" * 70)
        print(f"Total papers: {len(all_papers)}")
        print(f"Check versions: {'Yes' if check_versions else 'No (faster)'}")
        print(f"Rate limit: {self.max_requests_per_second} req/sec")
        print(f"Estimated time: ~{len(all_papers) / self.max_requests_per_second / 60:.1f} minutes")
        print()
        
        citing_papers = []
        non_citing_papers = []
        errors = []
        
        start = time.time()
        
        for i, paper in enumerate(all_papers, 1):
            article_id = paper['article_id']
            
            # Progress updates
            if i % 50 == 0:
                elapsed = time.time() - start
                rate = i / elapsed
                remaining = (len(all_papers) - i) / rate if rate > 0 else 0
                print(f"  [{i:4d}/{len(all_papers)}] {rate:.1f} papers/sec | "
                      f"ETA: {remaining/60:.1f} min | "
                      f"Citing so far: {len(citing_papers)}")
            
            result = self.scan_paper(article_id, paper, check_versions=check_versions)
            
            if result['success']:
                if result['data']['elife_citations']:
                    citing_papers.append(result['data'])
                else:
                    non_citing_papers.append({
                        'article_id': article_id,
                        'title': result['data']['title'],
                        'total_references': result['data']['total_references']
                    })
            else:
                errors.append({
                    'article_id': article_id,
                    'error': result['error']
                })
        
        elapsed = time.time() - start
        
        # Calculate statistics
        total_scanned = len(all_papers)
        total_citing = len(citing_papers)
        total_citations = sum(len(p['elife_citations']) for p in citing_papers)
        
        # Get unique cited papers
        all_cited_ids = set()
        for paper in citing_papers:
            for citation in paper['elife_citations']:
                all_cited_ids.add(citation['cited_article_id'])
        
        print()
        print("=" * 70)
        print("📊 FINAL RESULTS")
        print("=" * 70)
        print(f"⏱️  Time elapsed: {elapsed/60:.1f} minutes ({elapsed/total_scanned:.2f} sec/paper)")
        print(f"📄 Papers scanned: {total_scanned}")
        print(f"✅ Papers citing eLife: {total_citing} ({total_citing/total_scanned*100:.1f}%)")
        print(f"❌ Papers NOT citing eLife: {len(non_citing_papers)}")
        print(f"⚠️  Errors: {len(errors)}")
        print()
        print(f"📚 Total eLife citations found: {total_citations}")
        print(f"📚 Unique eLife papers cited: {len(all_cited_ids)}")
        print(f"📊 Average citations per citing paper: {total_citations/total_citing:.1f}")
        
        if check_versions:
            print(f"🔢 Version cache size: {len(self.version_cache)}")
        
        # Show top citers
        if citing_papers:
            print(f"\n🏆 Top 10 papers by eLife citations:")
            sorted_citing = sorted(citing_papers, 
                                   key=lambda x: len(x['elife_citations']), 
                                   reverse=True)
            for i, cp in enumerate(sorted_citing[:10], 1):
                print(f"  {i:2d}. {cp['article_id']}: {len(cp['elife_citations'])} citations")
        
        # Save comprehensive results
        output_data = {
            'scan_metadata': {
                'scanned_at': datetime.now().isoformat(),
                'total_papers_scanned': total_scanned,
                'papers_citing_elife': total_citing,
                'papers_not_citing_elife': len(non_citing_papers),
                'total_elife_citations': total_citations,
                'unique_papers_cited': len(all_cited_ids),
                'errors': len(errors),
                'time_elapsed_seconds': elapsed,
                'versions_checked': check_versions
            },
            'citing_papers': citing_papers,
            'cited_paper_ids': sorted(list(all_cited_ids)),
            'non_citing_papers': non_citing_papers,
            'errors': errors
        }
        
        self.output_file.parent.mkdir(exist_ok=True, parents=True)
        with open(self.output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\n💾 Complete results saved to:")
        print(f"   {self.output_file}")
        print("=" * 70)
        
        return output_data


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Scan all 1,000 target papers')
    parser.add_argument('--check-versions', action='store_true',
                        help='Query for latest version of each cited paper (slower but more complete)')
    args = parser.parse_args()
    
    # Paths
    project_root = Path(__file__).parent.parent
    target_file = project_root / "data" / "target_papers_1000.json"
    output_file = project_root / "data" / "scan_results_1000.json"
    
    if not target_file.exists():
        print(f"❌ Target file not found: {target_file}")
        sys.exit(1)
    
    # Run scan
    scanner = ComprehensiveScanner(target_file, output_file)
    
    try:
        scanner.scan_all(check_versions=args.check_versions)
    except KeyboardInterrupt:
        print("\n\n⚠️  Scan interrupted by user")
        print("   Partial results may be incomplete")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
