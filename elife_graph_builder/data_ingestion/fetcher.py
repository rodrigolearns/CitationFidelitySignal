"""Fetch eLife articles efficiently without cloning the full repository."""

import requests
from pathlib import Path
from typing import List, Optional, Dict
import logging
from tqdm import tqdm
import time

logger = logging.getLogger(__name__)


class ELifeFetcher:
    """
    Efficiently fetch eLife articles using:
    1. eLife API to get article metadata and IDs
    2. Direct GitHub raw URLs to download specific XML files
    
    This avoids cloning the entire repository (~90k articles).
    """
    
    ELIFE_API_URL = "https://api.elifesciences.org/articles"
    GITHUB_RAW_URL = "https://raw.githubusercontent.com/elifesciences/elife-article-xml/master/articles"
    
    def __init__(self, output_dir: Path):
        """Initialize fetcher with output directory."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'eLife-Citation-Graph-Builder/0.1'
        })
    
    def get_recent_articles(self, count: int = 20, article_type: str = "research-article") -> List[Dict]:
        """
        Get recent article IDs from eLife API.
        
        Args:
            count: Number of articles to fetch
            article_type: Type of article (research-article, short-report, etc.)
        
        Returns:
            List of article metadata dicts
        """
        articles = []
        page = 1
        per_page = min(count, 100)  # API max is usually 100
        
        logger.info(f"Fetching article list from eLife API...")
        
        while len(articles) < count:
            try:
                response = self.session.get(
                    self.ELIFE_API_URL,
                    params={
                        'per-page': per_page,
                        'page': page,
                        'order': 'desc'  # Most recent first
                    },
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                
                items = data.get('items', [])
                if not items:
                    break
                
                # Filter by article type if specified
                if article_type:
                    items = [a for a in items if a.get('type') == article_type]
                
                articles.extend(items)
                
                if len(articles) >= count:
                    break
                
                page += 1
                time.sleep(0.5)  # Be nice to the API
                
            except Exception as e:
                logger.error(f"Failed to fetch articles from API: {e}")
                break
        
        return articles[:count]
    
    def download_article_xml(self, article_id: str, version: int = 1) -> Optional[Path]:
        """
        Download a single article XML file directly from GitHub.
        
        Args:
            article_id: eLife article ID (e.g., "12345")
            version: Article version number (default: 1)
        
        Returns:
            Path to downloaded file, or None if failed
        """
        # Construct filename: elife-{id}-v{version}.xml
        filename = f"elife-{article_id}-v{version}.xml"
        output_path = self.output_dir / filename
        
        # Skip if already downloaded
        if output_path.exists():
            logger.debug(f"Skipping {filename} (already exists)")
            return output_path
        
        # Construct raw GitHub URL
        url = f"{self.GITHUB_RAW_URL}/{filename}"
        
        try:
            logger.debug(f"Downloading {filename}...")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Save to file
            output_path.write_bytes(response.content)
            logger.info(f"✓ Downloaded {filename}")
            return output_path
            
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"XML not found for article {article_id} (might be PDF-only or different version)")
            else:
                logger.error(f"HTTP error downloading {filename}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to download {filename}: {e}")
            return None
    
    def download_sample_articles(self, count: int = 10) -> List[Path]:
        """
        Download sample research articles for testing.
        
        This method:
        1. Fetches article IDs from eLife API
        2. Downloads XML files directly from GitHub
        3. Skips articles without XML (some are PDF-only)
        
        Args:
            count: Target number of articles to download
        
        Returns:
            List of paths to successfully downloaded XML files
        """
        logger.info(f"Fetching {count} sample articles...")
        
        # Get article metadata from API (fetch more to account for missing XMLs)
        articles = self.get_recent_articles(count=count * 2, article_type="research-article")
        
        if not articles:
            logger.error("No articles found from API")
            return []
        
        logger.info(f"Found {len(articles)} articles from API, attempting to download XML files...")
        
        downloaded_paths = []
        
        for article in tqdm(articles, desc="Downloading XMLs"):
            if len(downloaded_paths) >= count:
                break
            
            article_id = article.get('id')
            version = article.get('version', 1)
            
            if not article_id:
                continue
            
            path = self.download_article_xml(article_id, version)
            if path:
                downloaded_paths.append(path)
            
            # Be nice to GitHub
            time.sleep(0.3)
        
        logger.info(f"\n✅ Successfully downloaded {len(downloaded_paths)}/{count} articles to {self.output_dir}")
        return downloaded_paths
