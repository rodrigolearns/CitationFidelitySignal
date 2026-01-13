"""Async fetcher for high-performance article downloads."""

import asyncio
import aiohttp
from pathlib import Path
from typing import List, Optional, Dict, Tuple
import logging
from tqdm import tqdm
import time
import random

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when rate limited by server."""
    pass


class AsyncELifeFetcher:
    """
    High-performance async fetcher for eLife articles.
    
    Uses aiohttp with controlled concurrency to download
    many articles simultaneously without overwhelming servers.
    """
    
    ELIFE_API_URL = "https://api.elifesciences.org/articles"
    GITHUB_RAW_URL = "https://raw.githubusercontent.com/elifesciences/elife-article-xml/master/articles"
    
    def __init__(self, output_dir: Path, max_concurrent: int = 50):
        """
        Initialize async fetcher.
        
        Args:
            output_dir: Directory to save downloaded files
            max_concurrent: Maximum concurrent downloads (default: 50)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.stats = {
            'downloaded': 0,
            'cached': 0,
            'failed': 0,
            'rate_limited': 0,
            'start_time': None
        }
        self.backoff_delay = 1.0  # Start with 1 second
        self.max_backoff = 300.0  # Max 5 minutes
    
    async def get_recent_articles_async(
        self, 
        session: aiohttp.ClientSession,
        count: int = 100,
        page: int = 1,
        start_date: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch article metadata from eLife API (newest first).
        
        Args:
            session: aiohttp session
            count: Number of articles to fetch
            page: Starting page number
            start_date: Resume from this date (ISO format)
        
        Returns:
            List of article metadata, ordered by publication date DESC
        """
        articles = []
        per_page = min(count, 100)
        
        while len(articles) < count:
            try:
                async with session.get(
                    self.ELIFE_API_URL,
                    params={
                        'per-page': per_page, 
                        'page': page, 
                        'order': 'desc'  # Most recent first
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        break
                    
                    data = await response.json()
                    items = data.get('items', [])
                    
                    if not items:
                        break
                    
                    # Filter research articles
                    items = [a for a in items if a.get('type') == 'research-article']
                    articles.extend(items)
                    
                    if len(articles) >= count:
                        break
                    
                    page += 1
                    await asyncio.sleep(0.2)  # Rate limiting
                    
            except Exception as e:
                logger.error(f"Failed to fetch from API: {e}")
                break
        
        return articles[:count]
    
    async def download_article_xml_async(
        self,
        session: aiohttp.ClientSession,
        article_id: str,
        version: int = 1,
        progress_bar: Optional[tqdm] = None
    ) -> Optional[Path]:
        """
        Download a single article XML asynchronously with semaphore control.
        
        Args:
            session: aiohttp session
            article_id: eLife article ID
            version: Article version
            progress_bar: Optional tqdm progress bar
        
        Returns:
            Path to downloaded file or None if failed
        """
        filename = f"elife-{article_id}-v{version}.xml"
        output_path = self.output_dir / filename
        
        # Check cache first
        if output_path.exists():
            self.stats['cached'] += 1
            if progress_bar:
                progress_bar.update(1)
            return output_path
        
        # Use semaphore to limit concurrency
        async with self.semaphore:
            url = f"{self.GITHUB_RAW_URL}/{filename}"
            
            try:
                async with session.get(
                    url, 
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        content = await response.read()
                        output_path.write_bytes(content)
                        self.stats['downloaded'] += 1
                        self.backoff_delay = 1.0  # Reset backoff on success
                        if progress_bar:
                            progress_bar.update(1)
                        return output_path
                    elif response.status == 404:
                        self.stats['failed'] += 1
                        if progress_bar:
                            progress_bar.update(1)
                        return None
                    elif response.status == 429 or response.status == 403:
                        # Rate limited - trigger backoff
                        self.stats['rate_limited'] += 1
                        raise RateLimitError(f"Rate limited: HTTP {response.status}")
                    else:
                        logger.warning(f"HTTP {response.status} for {filename}")
                        self.stats['failed'] += 1
                        if progress_bar:
                            progress_bar.update(1)
                        return None
                        
            except RateLimitError as e:
                # Exponential backoff with jitter
                self.backoff_delay = min(self.backoff_delay * 2, self.max_backoff)
                jitter = random.uniform(0, 0.1 * self.backoff_delay)
                wait_time = self.backoff_delay + jitter
                logger.warning(f"Rate limited! Backing off {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                if progress_bar:
                    progress_bar.update(1)
                return None
            except asyncio.TimeoutError:
                logger.error(f"Timeout downloading {filename}")
                self.stats['failed'] += 1
                if progress_bar:
                    progress_bar.update(1)
                return None
            except Exception as e:
                logger.error(f"Failed to download {filename}: {e}")
                self.stats['failed'] += 1
                if progress_bar:
                    progress_bar.update(1)
                return None
    
    async def download_batch_async(
        self,
        articles: List[Dict],
        show_progress: bool = True
    ) -> List[Path]:
        """
        Download multiple articles concurrently.
        
        Args:
            articles: List of article metadata dicts
            show_progress: Show progress bar
        
        Returns:
            List of paths to successfully downloaded files
        """
        self.stats['start_time'] = time.time()
        
        # Create custom connector with connection pooling
        connector = aiohttp.TCPConnector(
            limit=self.max_concurrent,
            limit_per_host=self.max_concurrent,
            ttl_dns_cache=300
        )
        
        async with aiohttp.ClientSession(
            connector=connector,
            headers={'User-Agent': 'eLife-Citation-Graph-Builder/0.1'}
        ) as session:
            
            # Create progress bar
            progress_bar = None
            if show_progress:
                progress_bar = tqdm(
                    total=len(articles),
                    desc="Downloading",
                    unit="articles"
                )
            
            # Create download tasks
            tasks = [
                self.download_article_xml_async(
                    session,
                    article.get('id'),
                    article.get('version', 1),
                    progress_bar
                )
                for article in articles
            ]
            
            # Execute all downloads concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            if progress_bar:
                progress_bar.close()
        
        # Filter out None and exceptions
        downloaded_paths = [
            r for r in results 
            if r is not None and isinstance(r, Path)
        ]
        
        elapsed = time.time() - self.stats['start_time']
        rate = len(articles) / elapsed if elapsed > 0 else 0
        
        logger.info(
            f"\n✅ Download complete: {len(downloaded_paths)}/{len(articles)} articles"
        )
        logger.info(f"   Downloaded: {self.stats['downloaded']}")
        logger.info(f"   Cached: {self.stats['cached']}")
        logger.info(f"   Failed: {self.stats['failed']}")
        logger.info(f"   Time: {elapsed:.1f}s")
        logger.info(f"   Rate: {rate:.1f} articles/sec")
        
        return downloaded_paths
    
    def download_sample_articles(
        self,
        count: int = 50,
        page: int = 1,
        max_concurrent: int = None
    ) -> List[Path]:
        """
        Sync wrapper for async download.
        
        Args:
            count: Number of articles to download
            page: Starting API page
            max_concurrent: Override default concurrency
        
        Returns:
            List of paths to downloaded files
        """
        if max_concurrent:
            self.max_concurrent = max_concurrent
            self.semaphore = asyncio.Semaphore(max_concurrent)
        
        async def _download():
            async with aiohttp.ClientSession() as session:
                # Get article list starting from page
                logger.info(f"Fetching {count} articles from eLife API (page {page})...")
                articles = await self.get_recent_articles_async(session, count * 2, page=page)
                
                if not articles:
                    logger.error("No articles found")
                    return []
                
                logger.info(f"Found {len(articles)} articles, downloading XMLs...")
                
            # Download XMLs
            return await self.download_batch_async(articles[:count])
        
        # Run async code
        return asyncio.run(_download())
