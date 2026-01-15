#!/usr/bin/env python3
"""
Workflow 1: Process our specific 662 target papers through graph construction.

Uses the scan results to process only papers that cite eLife,
building a targeted citation graph in Neo4j.
"""

import json
import logging
from pathlib import Path
import sys
from typing import List, Set

sys.path.insert(0, str(Path(__file__).parent.parent))

from elife_graph_builder.parsers.parallel_parser import ParallelParser
from elife_graph_builder.matchers.elife_matcher import ELifeRegistry, ELifeMatcher
from elife_graph_builder.graph.neo4j_importer import StreamingNeo4jImporter
from elife_graph_builder.evidence_retrieval import CitationQualificationPipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TargetPaperProcessor:
    """Process our pre-scanned target papers."""
    
    def __init__(self, scan_results_file: Path, samples_dir: Path):
        self.scan_results_file = scan_results_file
        self.samples_dir = Path(samples_dir)
        
        self.registry = ELifeRegistry()
        self.matcher = ELifeMatcher(self.registry)
        self.neo4j = StreamingNeo4jImporter()
        self.parser = ParallelParser()
        
    def _get_xml_path(self, article_id: str) -> Path:
        """Get path to XML file (prefer unversioned, fall back to versioned)."""
        # Try unversioned first
        unversioned = self.samples_dir / f"elife-{article_id}.xml"
        if unversioned.exists():
            return unversioned
        
        # Try versioned (v1-v6)
        for version in range(1, 7):
            versioned = self.samples_dir / f"elife-{article_id}-v{version}.xml"
            if versioned.exists():
                return versioned
        
        return None
    
    def _fetch_missing_references(self, article_ids: Set[str]) -> list:
        """
        Parse XMLs for referenced articles that aren't in the database yet.
        """
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
        
        # Get XML paths for missing articles
        xml_files = []
        not_found = []
        
        for article_id in missing_ids:
            xml_path = self._get_xml_path(article_id)
            if xml_path:
                xml_files.append(xml_path)
            else:
                not_found.append(article_id)
        
        if not_found:
            logger.warning(f"      XMLs not found for {len(not_found)} articles: {not_found[:5]}...")
        
        if not xml_files:
            return []
        
        # Parse the XMLs
        logger.info(f"      Parsing {len(xml_files)} XML files...")
        results = self.parser.parse_batch(xml_files, method="threading", show_progress=False)
        
        # Extract metadata
        referenced_articles = []
        for metadata, references, anchors in results:
            if metadata:
                referenced_articles.append(metadata)
                self.registry.add_article(metadata)
        
        logger.info(f"      Successfully parsed {len(referenced_articles)} referenced articles")
        return referenced_articles
    
    def process_batch(self, batch_num: int, citing_paper_ids: List[str], batch_size: int = 100):
        """Process a batch of citing papers."""
        start_idx = (batch_num - 1) * batch_size
        end_idx = min(start_idx + batch_size, len(citing_paper_ids))
        batch_ids = citing_paper_ids[start_idx:end_idx]
        
        logger.info(f"\n📦 Processing Batch {batch_num}: Papers {start_idx+1}-{end_idx}")
        
        # Get XML paths
        xml_files = []
        missing = []
        for article_id in batch_ids:
            xml_path = self._get_xml_path(article_id)
            if xml_path:
                xml_files.append(xml_path)
            else:
                missing.append(article_id)
                logger.warning(f"   ⚠️  XML not found for {article_id}")
        
        if not xml_files:
            logger.error("   ❌ No XML files found for this batch")
            return
        
        logger.info(f"   → Parsing {len(xml_files)} XML files...")
        results = self.parser.parse_batch(xml_files, method="threading", show_progress=False)
        
        # Extract articles and edges
        articles = []
        edges = []
        referenced_article_ids = set()
        
        for metadata, references, anchors in results:
            if not metadata:
                continue
            
            articles.append(metadata)
            self.registry.add_article(metadata)
            self.matcher.identify_elife_references(references)
            batch_edges = self.matcher.match_citations(metadata, references, anchors)
            edges.extend(batch_edges)
            
            # Collect all referenced eLife article IDs
            for edge in batch_edges:
                referenced_article_ids.add(edge.target_article_id)
        
        # Import source articles first
        if articles:
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
        
        # Stats
        stats = self.neo4j.get_stats()
        logger.info(f"   ✅ Batch {batch_num} complete: {len(articles)} articles, {len(edges)} edges")
        logger.info(f"   📊 Graph total: {stats['articles']} articles, {stats['citations']} citations")
    
    def process_all(self, batch_size: int = 100):
        """Process all citing papers."""
        # Load scan results
        with open(self.scan_results_file, 'r') as f:
            scan_data = json.load(f)
        
        citing_paper_ids = [p['article_id'] for p in scan_data['citing_papers']]
        
        print("=" * 70)
        print("🚀 WORKFLOW 1: GRAPH CONSTRUCTION (TARGET PAPERS)")
        print("=" * 70)
        print(f"\nPhases:")
        print(f"  1. Build graph (parse XMLs, create nodes & edges)")
        print(f"  2. Qualify citations (extract contexts & retrieve evidence)")
        print(f"\n📊 Dataset:")
        print(f"   Citing papers to process: {len(citing_paper_ids)}")
        print(f"   Expected citations: {scan_data['scan_metadata']['total_elife_citations']}")
        print(f"   Expected referenced papers: {scan_data['scan_metadata']['unique_papers_cited']}")
        print(f"   Batch size: {batch_size} papers")
        print(f"   Total batches: {(len(citing_paper_ids) + batch_size - 1) // batch_size}")
        print()
        
        # Create schema
        self.neo4j.create_schema()
        
        # Process in batches
        num_batches = (len(citing_paper_ids) + batch_size - 1) // batch_size
        
        for batch_num in range(1, num_batches + 1):
            try:
                self.process_batch(batch_num, citing_paper_ids, batch_size)
            except Exception as e:
                logger.error(f"❌ Error processing batch {batch_num}: {e}")
                import traceback
                traceback.print_exc()
                raise
        
        # Final stats after graph construction
        final_stats = self.neo4j.get_stats()
        
        print("\n" + "=" * 70)
        print("✅ GRAPH CONSTRUCTION COMPLETE!")
        print("=" * 70)
        print(f"📊 Graph:")
        print(f"   Total articles: {final_stats['articles']}")
        print(f"   Total citations: {final_stats['citations']}")
        
        # Now run qualification: extract contexts + retrieve evidence
        print("\n" + "=" * 70)
        print("🔍 PHASE 2: CITATION QUALIFICATION")
        print("   (Extracting contexts & retrieving evidence)")
        print("=" * 70)
        
        qualification_pipeline = CitationQualificationPipeline(
            xml_cache_dir=str(self.samples_dir),
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="elifecitations2024"
        )
        
        try:
            qual_stats = qualification_pipeline.process_citations(
                limit=None,  # Process all citations
                bm25_top_n=20,
                final_top_k=5,
                min_similarity=0.7
            )
            
            print(f"\n✅ Qualification Complete!")
            print(f"   Citations processed: {qual_stats['processed']}/{qual_stats['total']}")
            print(f"   Contexts extracted: {qual_stats['contexts_extracted']}")
            print(f"   Evidence segments retrieved: {qual_stats['evidence_retrieved']}")
            if qual_stats['failed'] > 0:
                print(f"   Failed: {qual_stats['failed']}")
            
        finally:
            qualification_pipeline.close()
        
        print("\n" + "=" * 70)
        print("🎉 WORKFLOW 1 COMPLETE!")
        print("=" * 70)
        print(f"✅ Ready for Workflow 2 (LLM Classification)")
        print("=" * 70)
    
    def close(self):
        """Clean up resources."""
        self.neo4j.close()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Process target papers through Workflow 1')
    parser.add_argument('--scan-results', type=str, 
                        default='data/scan_results_1000.json',
                        help='Path to scan results JSON')
    parser.add_argument('--samples-dir', type=str,
                        default='data/samples',
                        help='Directory containing XMLs')
    parser.add_argument('--batch-size', type=int, default=100,
                        help='Papers per batch (default: 100)')
    args = parser.parse_args()
    
    # Paths
    project_root = Path(__file__).parent.parent
    scan_results_file = project_root / args.scan_results
    samples_dir = project_root / args.samples_dir
    
    if not scan_results_file.exists():
        print(f"❌ Scan results not found: {scan_results_file}")
        sys.exit(1)
    
    if not samples_dir.exists():
        print(f"❌ Samples directory not found: {samples_dir}")
        sys.exit(1)
    
    # Run processing
    processor = TargetPaperProcessor(scan_results_file, samples_dir)
    
    try:
        processor.process_all(batch_size=args.batch_size)
    except KeyboardInterrupt:
        print("\n\n⚠️  Processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        processor.close()


if __name__ == '__main__':
    main()
