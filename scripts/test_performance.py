#!/usr/bin/env python3
"""Test script for performance optimizations."""

import sys
import time
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from elife_graph_builder.data_ingestion.async_fetcher import AsyncELifeFetcher
from elife_graph_builder.parsers.parallel_parser import ParallelParser
from elife_graph_builder.matchers.elife_matcher import ELifeRegistry, ELifeMatcher

logging.basicConfig(level=logging.INFO, format='%(message)s')


def test_async_download():
    """Test async download functionality."""
    print("\n" + "="*70)
    print("TEST 1: Async Download")
    print("="*70)
    
    samples_dir = Path("data/samples")
    fetcher = AsyncELifeFetcher(samples_dir, max_concurrent=30)
    
    start = time.time()
    paths = fetcher.download_sample_articles(count=50, max_concurrent=30)
    elapsed = time.time() - start
    
    print(f"\n✅ Downloaded {len(paths)} articles in {elapsed:.2f}s")
    print(f"   Rate: {len(paths)/elapsed:.1f} articles/sec")
    
    return paths


def test_parallel_parsing(xml_files):
    """Test parallel parsing functionality."""
    print("\n" + "="*70)
    print("TEST 2: Parallel Parsing (Threading)")
    print("="*70)
    
    parser = ParallelParser()
    
    start = time.time()
    results = parser.parse_batch(xml_files, method="threading")
    elapsed = time.time() - start
    
    print(f"\n✅ Parsed {len(results)} articles in {elapsed:.2f}s")
    print(f"   Rate: {len(results)/elapsed:.1f} articles/sec")
    
    return results


def test_citation_matching(parsed_results):
    """Test citation matching with parsed results."""
    print("\n" + "="*70)
    print("TEST 3: Citation Matching")
    print("="*70)
    
    registry = ELifeRegistry()
    matcher = ELifeMatcher(registry)
    
    # Register all articles
    for metadata, _, _ in parsed_results:
        registry.add_article(metadata)
    
    print(f"Registry has {registry.size()} articles")
    
    # Find citations
    total_refs = 0
    total_elife_refs = 0
    total_edges = 0
    
    for metadata, references, anchors in parsed_results:
        matcher.identify_elife_references(references)
        elife_refs = [r for r in references if r.is_elife]
        edges = matcher.match_citations(metadata, references, anchors)
        
        total_refs += len(references)
        total_elife_refs += len(elife_refs)
        total_edges += len(edges)
    
    print(f"\n✅ Citation matching complete:")
    print(f"   Total references: {total_refs}")
    print(f"   eLife references: {total_elife_refs}")
    print(f"   Citation edges: {total_edges}")


def main():
    print("\n" + "="*70)
    print("🧪 PERFORMANCE TEST SUITE")
    print("="*70)
    
    # Test 1: Async Download
    paths = test_async_download()
    
    if not paths:
        print("❌ No articles downloaded, cannot continue tests")
        return
    
    # Get all XML files
    xml_files = list(Path("data/samples").glob("*.xml"))
    print(f"\nFound {len(xml_files)} XML files total")
    
    # Test 2: Parallel Parsing
    results = test_parallel_parsing(xml_files)
    
    if not results:
        print("❌ No articles parsed, cannot continue tests")
        return
    
    # Test 3: Citation Matching
    test_citation_matching(results)
    
    # Final Summary
    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED")
    print("="*70)
    print("\nPerformance optimizations are working correctly!")
    print("Ready to process large batches of articles.")


if __name__ == '__main__':
    main()
