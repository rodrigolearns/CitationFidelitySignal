"""Async fetcher for high-performance article downloads."""

import asyncio
import aiohttp
import ssl
import certifi
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
    
    def __init__(self, output_dir: Path, max_concurrent: int = 5):
        """
        Initialize async fetcher.
        
        Args:
            output_dir: Directory to save downloaded files
            max_concurrent: Maximum concurrent downloads (default: 5)
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
        
        # Headers to identify ourselves
        self.headers = {
            'User-Agent': 'eLife Citation Research Tool/1.0 (Academic Research)',
            'Accept': 'application/vnd.elife.article-list+json;version=1'
        }
        
        # Separate headers for XML downloads
        self.xml_headers = {
            'User-Agent': 'eLife Citation Research Tool/1.0 (Academic Research)'
        }
    
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
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        logger.error(f"API returned HTTP {response.status}: {await response.text()}")
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
                    await asyncio.sleep(1.0)  # Be respectful: 1 second between pages
                    
            except Exception as e:
                logger.error(f"Failed to fetch from API: {e}")
                break
        
        return articles[:count]
    
    async def get_latest_version_async(
        self,
        session: aiohttp.ClientSession,
        article_id: str
    ) -> int:
        """
        Query eLife API to get the latest version number for an article.
        
        Args:
            session: aiohttp session
            article_id: eLife article ID
            
        Returns:
            Version number or 1 if API call fails
        """
        try:
            api_url = f"{self.ELIFE_API_URL}/{article_id}"
            async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    version = data.get('version', 1)
                    logger.debug(f"Article {article_id}: latest version is v{version}")
                    return version
                else:
                    logger.warning(f"Failed to query API for {article_id}: HTTP {response.status}, defaulting to v1")
                    return 1
        except Exception as e:
            logger.warning(f"Failed to query API for {article_id}: {e}, defaulting to v1")
            return 1
    
    def check_xml_body_content(self, xml_path: Path) -> bool:
        """
        Check if XML file contains a <body> element (not just metadata).
        
        Args:
            xml_path: Path to XML file
            
        Returns:
            True if body element exists, False otherwise
        """
        import xml.etree.ElementTree as ET
        
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            body = root.find('.//body')
            return body is not None and len(body) > 0
        except Exception as e:
            logger.warning(f"Failed to parse {xml_path.name}: {e}")
            return False
    
    async def download_article_xml_async(
        self,
        session: aiohttp.ClientSession,
        article_id: str,
        version: int = 1,
        progress_bar: Optional[tqdm] = None
    ) -> Optional[Path]:
        """
        Download a single article XML asynchronously with version detection and validation.
        
        Tries to:
        1. Detect latest version from API
        2. Download from GitHub
        3. Validate body content exists
        4. Try alternate versions if needed (v1, v2, v3)
        
        Args:
            session: aiohttp session
            article_id: eLife article ID
            version: Article version (ignored - we detect automatically)
            progress_bar: Optional tqdm progress bar
        
        Returns:
            Path to downloaded file or None if failed
        """
        # Use semaphore to limit concurrency
        async with self.semaphore:
            # Step 1: Get latest version from API
            latest_version = await self.get_latest_version_async(session, article_id)
            
            # Step 2: Try versions in order: latest, then v3, v2, v1
            versions_to_try = [latest_version]
            for v in [3, 2, 1]:
                if v != latest_version and v not in versions_to_try:
                    versions_to_try.append(v)
            
            # Check cache first (any version)
            for v in versions_to_try:
                cached_path = self.output_dir / f"elife-{article_id}-v{v}.xml"
                if cached_path.exists():
                    if self.check_xml_body_content(cached_path):
                        self.stats['cached'] += 1
                        if progress_bar:
                            progress_bar.update(1)
                        logger.debug(f"✓ {article_id}: Found cached v{v} with body content")
                        return cached_path
                    else:
                        # Cached file has no body, delete it
                        cached_path.unlink()
                        logger.debug(f"✗ {article_id}: Deleted cached v{v} (no body content)")
            
            # Step 3: Try downloading versions until we find one with body content
            for v in versions_to_try:
                url = f"{self.GITHUB_RAW_URL}/elife-{article_id}-v{v}.xml"
                output_path = self.output_dir / f"elife-{article_id}-v{v}.xml"
            
            try:
                async with session.get(
                    url,
                    headers=self.xml_headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        content = await response.read()
                        output_path.write_bytes(content)
                            
                            # Validate body content
                            if self.check_xml_body_content(output_path):
                        self.stats['downloaded'] += 1
                        self.backoff_delay = 1.0  # Reset backoff on success
                        if progress_bar:
                            progress_bar.update(1)
                                logger.debug(f"✓ {article_id}: Downloaded v{v} with body content")
                                # Small delay to be respectful to GitHub
                                await asyncio.sleep(0.5)
                        return output_path
                            else:
                                # No body content, delete and try next version
                                output_path.unlink()
                                logger.debug(f"✗ {article_id}: v{v} has no body content, trying next version")
                                continue
                    elif response.status == 404:
                            logger.debug(f"✗ {article_id}: v{v} not found (404)")
                            continue  # Try next version
                    elif response.status == 429 or response.status == 403:
                            # Rate limited - wait and fail this article
                        self.stats['rate_limited'] += 1
                self.backoff_delay = min(self.backoff_delay * 2, self.max_backoff)
                jitter = random.uniform(0, 0.1 * self.backoff_delay)
                wait_time = self.backoff_delay + jitter
                            logger.warning(f"⚠ Rate limited! Backing off {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                            break  # Don't try more versions if rate limited
                        else:
                            logger.debug(f"✗ {article_id}: v{v} HTTP {response.status}")
                            continue
                            
            except asyncio.TimeoutError:
                    logger.debug(f"✗ {article_id}: v{v} timeout")
                    continue
            except Exception as e:
                    logger.debug(f"✗ {article_id}: v{v} error: {e}")
                    continue
            
            # All versions failed
                self.stats['failed'] += 1
                if progress_bar:
                    progress_bar.update(1)
            logger.warning(f"✗ {article_id}: All versions failed or have no body content")
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
        
        # Create SSL context with certifi certificates
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        
        # Create custom connector with connection pooling
        connector = aiohttp.TCPConnector(
            limit=self.max_concurrent,
            limit_per_host=self.max_concurrent,
            ttl_dns_cache=300,
            ssl=ssl_context
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
    
    def get_latest_version(self, article_id: str) -> int:
        """
        Query eLife API to get the latest version number for an article (synchronous).
        
        Args:
            article_id: eLife article ID
            
        Returns:
            Version number or 1 if API call fails
        """
        import requests
        
        try:
            api_url = f"{self.ELIFE_API_URL}/{article_id}"
            response = requests.get(api_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                version = data.get('version', 1)
                logger.debug(f"Article {article_id}: latest version is v{version}")
                return version
            else:
                logger.warning(f"API returned {response.status_code} for {article_id}, defaulting to v1")
                return 1
                
        except Exception as e:
            logger.warning(f"Failed to query API for {article_id}: {e}, defaulting to v1")
            return 1
    
    def download_article_xml(self, article_id: str, version: Optional[int] = None) -> Optional[Path]:
        """
        Download a single article XML (synchronous wrapper with version detection).
        
        Args:
            article_id: eLife article ID
            version: Article version (None = query API for latest)
            
        Returns:
            Path to downloaded file or None if failed
        """
        # Get latest version if not specified
        if version is None:
            version = self.get_latest_version(article_id)
        
        # Use async download in a sync wrapper
        async def _download():
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                return await self.download_article_xml_async(session, article_id, version)
        
        return asyncio.run(_download())
    
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
            # Create SSL context with certifi certificates
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            
            # Create session with proper headers and SSL
            connector = aiohttp.TCPConnector(limit=self.max_concurrent, ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector, headers=self.headers) as session:
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
