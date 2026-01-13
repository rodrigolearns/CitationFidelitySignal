"""Citation Qualification Pipeline - orchestrates context extraction and evidence retrieval."""

import logging
from typing import List, Dict
from pathlib import Path

from .extractors.context_extractor import CitationContextExtractor
from .retrievers.hybrid_retriever import HybridEvidenceRetriever
from .graph.neo4j_importer import StreamingNeo4jImporter
from .models import CitationContext

logger = logging.getLogger(__name__)


class CitationQualificationPipeline:
    """
    Orchestrates the qualification of eLife→eLife citations.
    
    Flow:
    1. Get unqualified citations from Neo4j
    2. For each citation:
       - Extract citation contexts (4-sentence windows)
       - Retrieve evidence segments (hybrid BM25 + semantic)
       - Store in Neo4j
    """
    
    def __init__(
        self, 
        xml_cache_dir: str = "data/raw_xml",
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "elifecitations2024",
        similarity_threshold: float = 0.7
    ):
        """
        Initialize the qualification pipeline.
        
        Args:
            xml_cache_dir: Directory where article XMLs are cached
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            similarity_threshold: Minimum similarity score for evidence retrieval
        """
        self.xml_cache_dir = Path(xml_cache_dir)
        self.similarity_threshold = similarity_threshold
        
        # Initialize components
        self.context_extractor = CitationContextExtractor()
        self.evidence_retriever = HybridEvidenceRetriever()
        self.neo4j = StreamingNeo4jImporter(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password
        )
        
        # Get cached article IDs
        self.cached_article_ids = self._get_cached_article_ids()
        logger.info(f"Found {len(self.cached_article_ids)} cached article XMLs")
        
        logger.info("✅ Citation qualification pipeline initialized")
    
    def _get_cached_article_ids(self):
        """Get set of article IDs that have cached XMLs."""
        article_ids = set()
        
        search_dirs = [
            self.xml_cache_dir,
            Path("data/samples"),
            Path("data/raw_xml")
        ]
        
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            
            for xml_file in search_dir.glob("elife-*.xml"):
                # Extract article ID (handle version numbers)
                name = xml_file.stem  # e.g., "elife-12345-v1"
                parts = name.split('-')
                if len(parts) >= 2:
                    article_id = parts[1]  # The number after "elife-"
                    article_ids.add(article_id)
        
        return article_ids
    
    def _get_cached_unqualified_citations(self, limit: int = None) -> List[Dict]:
        """
        Get unqualified citations where both articles have cached XMLs.
        Ordered by source article publication date (newest first) for chronological processing.
        """
        query = """
            MATCH (source:Article)-[c:CITES]->(target:Article)
            WHERE source.doi STARTS WITH '10.7554/eLife'
              AND target.doi STARTS WITH '10.7554/eLife'
              AND (c.qualified IS NULL OR c.qualified = false)
              AND source.article_id IN $cached_ids
              AND target.article_id IN $cached_ids
            RETURN source.article_id as source_id,
                   target.article_id as target_id,
                   source.doi as source_doi,
                   target.doi as target_doi,
                   source.pub_date as source_date,
                   c.reference_id as ref_id,
                   c.citation_count as count
            ORDER BY source.pub_date DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        with self.neo4j.driver.session() as session:
            result = session.run(query, cached_ids=list(self.cached_article_ids))
            citations = [dict(record) for record in result]
        
        logger.info(
            f"Found {len(citations)} unqualified citations with both XMLs cached"
        )
        return citations
    
    def close(self):
        """Close connections."""
        self.neo4j.close()
    
    def __enter__(self):
        """Context manager support."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()
    
    def get_article_xml(self, article_id: str) -> str:
        """
        Load article XML from cache (handles multiple locations and versions).
        
        Args:
            article_id: Article ID
        
        Returns:
            XML content as string
        
        Raises:
            FileNotFoundError: If XML not in cache
        """
        # Try multiple locations and patterns
        search_dirs = [
            self.xml_cache_dir,
            Path("data/samples"),
            Path("data/raw_xml")
        ]
        
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            
            # Try exact match first
            xml_path = search_dir / f"elife-{article_id}.xml"
            if xml_path.exists():
                with open(xml_path, 'r', encoding='utf-8') as f:
                    return f.read()
            
            # Try with version numbers (e.g., elife-12345-v1.xml)
            version_files = list(search_dir.glob(f"elife-{article_id}-v*.xml"))
            if version_files:
                # Use the latest version (highest v number)
                latest = sorted(version_files, reverse=True)[0]
                logger.debug(f"Using versioned XML: {latest.name}")
                with open(latest, 'r', encoding='utf-8') as f:
                    return f.read()
        
        raise FileNotFoundError(
            f"Article XML not found: {article_id}. "
            f"Searched in: {', '.join(str(d) for d in search_dirs)}"
        )
    
    def qualify_citation(
        self,
        source_id: str,
        target_id: str,
        ref_id: str,
        bm25_top_n: int = 20,
        final_top_k: int = 5,
        min_similarity: float = 0.7
    ) -> List[CitationContext]:
        """
        Qualify a single citation by extracting contexts and evidence.
        
        Args:
            source_id: Citing article ID
            target_id: Reference article ID
            ref_id: Reference ID in bibliography
            bm25_top_n: Number of BM25 candidates
            final_top_k: Final evidence segments per context
            min_similarity: Minimum similarity threshold
        
        Returns:
            List of CitationContext objects with evidence
        """
        logger.info(f"Qualifying citation: {source_id} → {target_id} (ref: {ref_id})")
        
        try:
            # Load XMLs
            source_xml = self.get_article_xml(source_id)
            target_xml = self.get_article_xml(target_id)
            
            # Extract citation contexts
            contexts = self.context_extractor.extract_contexts(
                source_xml,
                source_id,
                target_id,
                ref_id
            )
            
            if not contexts:
                logger.warning(f"No contexts found for {source_id} → {target_id}")
                return []
            
            logger.info(f"Extracted {len(contexts)} citation contexts")
            
            # Retrieve evidence for each context
            for context in contexts:
                evidence_segments = self.evidence_retriever.retrieve(
                    citation_context=context.context_text,
                    reference_article_xml=target_xml,
                    bm25_top_n=bm25_top_n,
                    final_top_k=final_top_k,
                    min_similarity=min_similarity
                )
                
                context.evidence_segments = evidence_segments
                
                logger.info(
                    f"  Instance {context.instance_id}: "
                    f"{len(evidence_segments)} evidence segments "
                    f"(similarity >= {min_similarity})"
                )
            
            return contexts
        
        except FileNotFoundError as e:
            logger.error(f"XML not found: {e}")
            return []
        except Exception as e:
            logger.error(f"Error qualifying citation: {e}", exc_info=True)
            return []
    
    def process_citations(
        self,
        limit: int = None,
        bm25_top_n: int = 20,
        final_top_k: int = 5,
        min_similarity: float = 0.7
    ) -> Dict[str, int]:
        """
        Process unqualified citations from Neo4j.
        
        Args:
            limit: Maximum number of citations to process
            bm25_top_n: Number of BM25 candidates
            final_top_k: Final evidence segments per context
            min_similarity: Minimum similarity threshold
        
        Returns:
            Dict with processing statistics
        """
        logger.info(
            f"🚀 Starting citation qualification pipeline "
            f"(limit: {limit or 'all'})"
        )
        
        # Get unqualified citations (only those with cached XMLs)
        citations = self._get_cached_unqualified_citations(limit=limit)
        
        if not citations:
            logger.info("✅ No unqualified citations found")
            return {
                'total': 0,
                'processed': 0,
                'failed': 0,
                'contexts_extracted': 0,
                'evidence_retrieved': 0
            }
        
        stats = {
            'total': len(citations),
            'processed': 0,
            'failed': 0,
            'contexts_extracted': 0,
            'evidence_retrieved': 0
        }
        
        # Process each citation
        for i, citation in enumerate(citations, 1):
            logger.info(
                f"\n📦 Processing citation {i}/{len(citations)}: "
                f"{citation['source_id']} → {citation['target_id']}"
            )
            
            try:
                # Qualify the citation
                contexts = self.qualify_citation(
                    source_id=citation['source_id'],
                    target_id=citation['target_id'],
                    ref_id=citation['ref_id'],
                    bm25_top_n=bm25_top_n,
                    final_top_k=final_top_k,
                    min_similarity=min_similarity
                )
                
                if contexts:
                    # Update Neo4j
                    self.neo4j.update_citation_contexts(
                        source_article_id=citation['source_id'],
                        target_article_id=citation['target_id'],
                        ref_id=citation['ref_id'],
                        contexts=contexts
                    )
                    
                    stats['processed'] += 1
                    stats['contexts_extracted'] += len(contexts)
                    stats['evidence_retrieved'] += sum(
                        len(ctx.evidence_segments) for ctx in contexts
                    )
                    
                    logger.info(f"✅ Citation qualified successfully")
                else:
                    logger.warning(f"⚠️  No contexts extracted")
                    stats['failed'] += 1
            
            except Exception as e:
                logger.error(f"❌ Failed to process citation: {e}")
                stats['failed'] += 1
        
        # Final summary
        logger.info("\n" + "=" * 70)
        logger.info("🎉 Citation Qualification Complete!")
        logger.info("=" * 70)
        logger.info(f"Total citations: {stats['total']}")
        logger.info(f"✅ Processed: {stats['processed']}")
        logger.info(f"❌ Failed: {stats['failed']}")
        logger.info(f"📝 Contexts extracted: {stats['contexts_extracted']}")
        logger.info(f"🔍 Evidence segments retrieved: {stats['evidence_retrieved']}")
        logger.info("=" * 70 + "\n")
        
        return stats


def run_qualification_pipeline(
    limit: int = None,
    bm25_top_n: int = 20,
    final_top_k: int = 5,
    min_similarity: float = 0.7
) -> Dict[str, int]:
    """
    Convenience function to run the qualification pipeline.
    
    Args:
        limit: Maximum citations to process
        bm25_top_n: Number of BM25 candidates
        final_top_k: Final evidence segments
        min_similarity: Minimum similarity threshold
    
    Returns:
        Processing statistics
    """
    with CitationQualificationPipeline() as pipeline:
        return pipeline.process_citations(
            limit=limit,
            bm25_top_n=bm25_top_n,
            final_top_k=final_top_k,
            min_similarity=min_similarity
        )
