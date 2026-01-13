"""Processing pipeline for building citation graph."""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json
from datetime import datetime
import pickle

from .data_ingestion.async_fetcher import AsyncELifeFetcher
from .parsers.parallel_parser import ParallelParser
from .matchers.elife_matcher import ELifeRegistry, ELifeMatcher
from .models import ArticleMetadata, Reference, CitationAnchor, CitationEdge

logger = logging.getLogger(__name__)


class CitationGraphBuilder:
    """
    End-to-end pipeline: Download → Parse → Match → Store relations.
    
    Stores citation edges as JSON for Sprint 3 graph building.
    """
    
    def __init__(self, data_dir: Path = Path("data")):
        self.data_dir = Path(data_dir)
        self.samples_dir = self.data_dir / "samples"
        self.processed_dir = self.data_dir / "processed"
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        
        self.registry = ELifeRegistry()
        self.matcher = ELifeMatcher(self.registry)
        self.checkpoint_file = self.data_dir / "checkpoint.json"
    
    def process_articles(
        self,
        count: int = 100,
        resume: bool = True
    ) -> Dict:
        """
        Process articles: download, parse, find eLife citations.
        
        Args:
            count: Number of articles to process
            resume: Resume from checkpoint if exists
        
        Returns:
            Statistics dict
        """
        stats = {
            'started': datetime.now().isoformat(),
            'articles_downloaded': 0,
            'articles_parsed': 0,
            'total_references': 0,
            'elife_references': 0,
            'citation_edges': 0
        }
        
        # Check checkpoint
        if resume and self.checkpoint_file.exists():
            logger.info("Resuming from checkpoint...")
            checkpoint = json.loads(self.checkpoint_file.read_text())
            if checkpoint.get('completed', False):
                logger.info("Already completed. Delete checkpoint to rerun.")
                return checkpoint['stats']
        
        # Step 1: Download
        logger.info(f"Step 1: Downloading {count} articles...")
        fetcher = AsyncELifeFetcher(self.samples_dir)
        xml_files = fetcher.download_sample_articles(count)
        stats['articles_downloaded'] = len(xml_files)
        
        # Step 2: Parse
        logger.info(f"Step 2: Parsing {len(xml_files)} articles...")
        parser = ParallelParser()
        results = parser.parse_batch(xml_files, method="threading")
        stats['articles_parsed'] = len(results)
        
        # Step 3: Build registry
        logger.info("Step 3: Building article registry...")
        for metadata, _, _ in results:
            self.registry.add_article(metadata)
        
        # Step 4: Match citations
        logger.info("Step 4: Matching eLife citations...")
        all_edges = []
        
        for metadata, references, anchors in results:
            self.matcher.identify_elife_references(references)
            edges = self.matcher.match_citations(metadata, references, anchors)
            all_edges.extend(edges)
            
            stats['total_references'] += len(references)
            stats['elife_references'] += sum(1 for r in references if r.is_elife)
        
        stats['citation_edges'] = len(all_edges)
        stats['completed'] = datetime.now().isoformat()
        
        # Step 5: Save edges
        self._save_edges(all_edges)
        
        # Save checkpoint
        self._save_checkpoint(stats, completed=True)
        
        logger.info(f"\n✅ Processing complete:")
        logger.info(f"   Articles: {stats['articles_parsed']}")
        logger.info(f"   eLife citations: {stats['elife_references']}/{stats['total_references']}")
        logger.info(f"   Citation edges: {stats['citation_edges']}")
        
        return stats
    
    def _save_edges(self, edges: List[CitationEdge]):
        """Save citation edges to JSON for Sprint 3."""
        output_file = self.processed_dir / "citation_edges.json"
        
        edges_data = []
        for edge in edges:
            edges_data.append({
                'source': edge.source_article_id,
                'target': edge.target_article_id,
                'source_doi': edge.source_doi,
                'target_doi': edge.target_doi,
                'reference_id': edge.reference_id,
                'citation_count': edge.citation_count,
                'sections': list(edge.sections)
            })
        
        output_file.write_text(json.dumps(edges_data, indent=2))
        logger.info(f"Saved {len(edges)} edges to {output_file}")
    
    def _save_checkpoint(self, stats: Dict, completed: bool = False):
        """Save processing checkpoint."""
        checkpoint = {
            'stats': stats,
            'completed': completed,
            'registry_size': self.registry.size()
        }
        self.checkpoint_file.write_text(json.dumps(checkpoint, indent=2))
    
    def get_edges(self) -> List[Dict]:
        """Load saved citation edges."""
        edges_file = self.processed_dir / "citation_edges.json"
        if edges_file.exists():
            return json.loads(edges_file.read_text())
        return []