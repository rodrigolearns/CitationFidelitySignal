"""Streaming pipeline for continuous processing into Neo4j."""

import logging
from pathlib import Path
from typing import Optional
import time

from .data_ingestion.async_fetcher import AsyncELifeFetcher
from .parsers.parallel_parser import ParallelParser
from .matchers.elife_matcher import ELifeRegistry, ELifeMatcher
from .graph.neo4j_importer import StreamingNeo4jImporter
from .progress_tracker import ProgressTracker
from .utils.xml_cleanup import cleanup_non_citing_articles

logger = logging.getLogger(__name__)


class StreamingCitationPipeline:
    """
    Continuous pipeline: Download → Parse → Match → Stream to Neo4j
    
    Features:
    - Processes articles in batches
    - Streams results to Neo4j incrementally
    - Handles rate limiting with backoff
    - Resume capability
    - Real-time progress updates
    """
    
    def __init__(self, data_dir: Path = Path("data")):
        self.data_dir = Path(data_dir)
        self.samples_dir = self.data_dir / "samples"
        
        self.registry = ELifeRegistry()
        self.matcher = ELifeMatcher(self.registry)
        self.neo4j = StreamingNeo4jImporter()
        self.fetcher = AsyncELifeFetcher(self.samples_dir, max_concurrent=3)  # Be respectful: only 3 concurrent
        self.tracker = ProgressTracker(self.data_dir / "progress.json")  # Track progress
    
    def _fetch_missing_references(self, article_ids: set) -> list:
        """
        Fetch metadata for referenced articles that aren't in the database yet.
        
        Args:
            article_ids: Set of article IDs to check
            
        Returns:
            List of ArticleMetadata for missing articles
        """
        from .parsers.parallel_parser import ParallelParser
        
        # Check which articles are missing from Neo4j
        with self.neo4j.driver.session() as session:
            result = session.run("""
                UNWIND $ids as id
                OPTIONAL MATCH (a:Article {article_id: id})
                WHERE a.authors IS NOT NULL
                RETURN id, a IS NOT NULL as exists
            """, ids=list(article_ids))
            
            missing_ids = [record['id'] for record in result if not record['exists']]
        
        if not missing_ids:
            return []
        
        logger.info(f"   → Fetching {len(missing_ids)} missing referenced articles...")
        
        # Try to download XMLs for missing articles
        xml_files = []
        downloaded = 0
        cached = 0
        failed = 0
        
        for article_id in missing_ids:
            # Try both v1 and v2 (most common versions)
            for version in [1, 2]:
                xml_path = self.samples_dir / f"elife-{article_id}-v{version}.xml"
                if xml_path.exists():
                    xml_files.append(xml_path)
                    cached += 1
                    break
            else:
                # Not cached, download using fetcher (with automatic version detection)
                try:
                    xml_path = self.fetcher.download_article_xml(article_id)
                    if xml_path:
                        xml_files.append(xml_path)
                        downloaded += 1
                    else:
                        failed += 1
                        logger.warning(f"Download returned None for {article_id}")
                except Exception as e:
                    failed += 1
                    logger.warning(f"Could not fetch {article_id}: {e}")
        
        logger.info(f"      Downloaded: {downloaded}, Cached: {cached}, Failed: {failed}")
        
        if not xml_files:
            logger.warning(f"      No XML files available for referenced articles!")
            return []
        
        # Parse the fetched XMLs
        logger.info(f"      Parsing {len(xml_files)} XML files...")
        parser = ParallelParser()
        results = parser.parse_batch(xml_files, method="threading", show_progress=False)
        
        # Extract metadata
        referenced_articles = []
        for metadata, references, anchors in results:
            if metadata:
                referenced_articles.append(metadata)
                self.registry.add_article(metadata)
        
        logger.info(f"      Successfully parsed {len(referenced_articles)} referenced articles")
        return referenced_articles
    
    def run_continuous(
        self,
        total_articles: Optional[int] = None,
        batch_size: int = 50,
        start_page: Optional[int] = None,
        skip_cleanup: bool = True
    ):
        """
        Run continuous processing.
        
        Args:
            total_articles: Total to process (None = process all)
            batch_size: Articles per batch
            start_page: Starting page (None = resume from tracker)
            skip_cleanup: If True, don't delete XMLs for non-citing articles (default: True)
        """
        logger.info(f"🚀 Starting continuous processing")
        logger.info(f"   Batch size: {batch_size}")
        logger.info(f"   Target: {total_articles or 'ALL'} articles")
        
        # Create schema
        self.neo4j.create_schema()
        
        # Resume from where we left off
        if start_page is None:
            start_page = self.tracker.last_api_page
        
        logger.info(f"   Starting from API page: {start_page}")
        
        processed = 0
        batch_num = 0
        current_page = start_page
        max_batches = (total_articles // batch_size) + 1 if total_articles else None
        
        while True:
            if total_articles and processed >= total_articles:
                logger.info(f"✅ Reached target of {total_articles} articles")
                break
            
            if max_batches and batch_num >= max_batches:
                logger.info(f"✅ Completed {max_batches} batches")
                break
            
            batch_num += 1
            logger.info(f"\n📦 Processing batch {batch_num} (target: {batch_size} articles)")
            
            try:
                # Download using persistent fetcher from current page
                xml_files = self.fetcher.download_sample_articles(batch_size, page=current_page)
                
                if not xml_files:
                    logger.error("❌ No articles downloaded - stopping")
                    break
                
                # Parse
                parser = ParallelParser()
                results = parser.parse_batch(xml_files, method="threading", show_progress=False)
                
                # Extract articles and edges
                articles = []
                edges = []
                referenced_article_ids = set()
                
                for metadata, references, anchors in results:
                    # Skip if already processed
                    if self.tracker.is_processed(metadata.article_id):
                        logger.debug(f"Skipping {metadata.article_id} (already processed)")
                        continue
                    
                    articles.append(metadata)
                    self.registry.add_article(metadata)
                    self.matcher.identify_elife_references(references)
                    batch_edges = self.matcher.match_citations(metadata, references, anchors)
                    edges.extend(batch_edges)
                    
                    # Collect all referenced eLife article IDs
                    for edge in batch_edges:
                        referenced_article_ids.add(edge.target_article_id)
                    
                    # Mark as processed
                    pub_date = metadata.publication_date.isoformat() if metadata.publication_date else str(metadata.publication_year)
                    self.tracker.mark_processed(metadata.article_id, pub_date)
                
                # Import source articles first
                logger.info(f"   → Importing {len(articles)} articles to Neo4j...")
                self.neo4j.import_articles_batch(articles)
                
                # Fetch and import referenced articles that aren't in the database yet
                if referenced_article_ids:
                    missing_refs = self._fetch_missing_references(referenced_article_ids)
                    if missing_refs:
                        logger.info(f"   → Importing {len(missing_refs)} referenced articles...")
                        self.neo4j.import_articles_batch(missing_refs)
                
                # Now create edges (both sides should exist)
                if edges:
                    logger.info(f"   → Importing {len(edges)} citation edges to Neo4j...")
                    self.neo4j.import_edges_batch(edges)
                
                # Phase 1 Cleanup: Remove XMLs for articles without eLife citations
                if not skip_cleanup:
                    try:
                        deleted = cleanup_non_citing_articles(self.neo4j, self.samples_dir)
                        if deleted > 0:
                            logger.info(f"   🧹 Cleaned up {deleted} XML files (no eLife citations)")
                    except Exception as e:
                        logger.warning(f"   ⚠️  Cleanup failed: {e}")
                
                # Update stats and save progress
                processed += len(articles)
                
                # Advance to next page for next batch
                current_page += 1
                self.tracker.last_api_page = current_page
                self.tracker.save()  # Save checkpoint after each batch
                
                stats = self.neo4j.get_stats()
                tracker_status = self.tracker.get_status()
                logger.info(f"   ✅ Batch {batch_num} complete. New articles: {len(articles)}, Total this session: {processed}/{total_articles or '?'}")
                logger.info(f"   📊 Graph: {stats['articles']} articles, {stats['citations']} citations")
                logger.info(f"   💾 Total ever processed: {tracker_status['total_processed']}, Next page: {current_page}")
                
                # Small delay between batches
                time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("\n⚠️  Interrupted by user")
                break
            except Exception as e:
                logger.error(f"❌ Error processing batch {batch_num}: {e}")
                import traceback
                traceback.print_exc()
                logger.info("⚠️  Stopping due to error")
                break
        
        # Final stats
        final_stats = self.neo4j.get_stats()
        logger.info(f"\n🎉 Processing complete!")
        logger.info(f"   Total articles in graph: {final_stats['articles']}")
        logger.info(f"   Total citations: {final_stats['citations']}")
    
    def close(self):
        """Clean up resources."""
        self.neo4j.close()
