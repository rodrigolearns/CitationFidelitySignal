#!/usr/bin/env python3
"""Download sample eLife XML articles for testing."""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from elife_graph_builder.config import Config
from elife_graph_builder.data_ingestion.fetcher import ELifeFetcher


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Download sample eLife XML articles'
    )
    parser.add_argument(
        '--count',
        type=int,
        default=10,
        help='Number of articles to download (default: 10)'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Config.SAMPLES_DIR,
        help='Output directory for samples'
    )
    
    args = parser.parse_args()
    setup_logging()
    
    # Ensure directories exist
    Config.ensure_directories()
    
    # Download samples
    fetcher = ELifeFetcher(args.output_dir)
    paths = fetcher.download_sample_articles(count=args.count)
    
    print(f"\n✅ Successfully downloaded {len(paths)} articles to {args.output_dir}")
    print("\nSample files:")
    for path in paths[:5]:  # Show first 5
        print(f"  - {path.name}")
    if len(paths) > 5:
        print(f"  ... and {len(paths) - 5} more")


if __name__ == '__main__':
    main()
