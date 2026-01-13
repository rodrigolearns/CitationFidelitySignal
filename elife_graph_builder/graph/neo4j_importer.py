"""Streaming Neo4j importer for incremental graph updates."""

import logging
import json
from typing import List, Dict, Optional
from neo4j import GraphDatabase
from pathlib import Path
import os
from dotenv import load_dotenv

from ..models import ArticleMetadata, CitationEdge, CitationContext

logger = logging.getLogger(__name__)

load_dotenv()


class StreamingNeo4jImporter:
    """
    Streaming importer that updates Neo4j graph incrementally.
    
    Handles:
    - Incremental article additions
    - Real-time edge creation
    - No data loss
    - Duplicate prevention
    """
    
    def __init__(
        self, 
        uri: str = None,
        user: str = None,
        password: str = None
    ):
        """
        Initialize Neo4j importer.
        
        Args:
            uri: Neo4j URI (defaults to env var or 'bolt://localhost:7687')
            user: Neo4j username (defaults to env var or 'neo4j')
            password: Neo4j password (defaults to env var or 'elifecitations2024')
        """
        self.uri = uri or os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        self.user = user or os.getenv('NEO4J_USER', 'neo4j')
        self.password = password or os.getenv('NEO4J_PASSWORD', 'elifecitations2024')
        
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_pool_size=50
            )
            self.driver.verify_connectivity()
            logger.info(f"✅ Connected to Neo4j at {self.uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
    
    def close(self):
        """Close the driver connection."""
        if self.driver:
            self.driver.close()
    
    def create_schema(self):
        """Create indexes and constraints for performance."""
        with self.driver.session() as session:
            # Constraints (uniqueness)
            session.run("""
                CREATE CONSTRAINT article_id_unique IF NOT EXISTS
                FOR (a:Article) REQUIRE a.article_id IS UNIQUE
            """)
            
            # Indexes (performance)
            session.run("""
                CREATE INDEX article_doi IF NOT EXISTS
                FOR (a:Article) ON (a.doi)
            """)
            
            session.run("""
                CREATE INDEX article_year IF NOT EXISTS
                FOR (a:Article) ON (a.year)
            """)
            
            logger.info("✅ Schema created")
    
    def import_article(self, metadata: ArticleMetadata):
        """
        Import single article (idempotent - safe to re-run).
        
        Uses MERGE so running multiple times won't duplicate.
        """
        with self.driver.session() as session:
            session.run("""
                MERGE (a:Article {article_id: $article_id})
                SET a.doi = $doi,
                    a.title = $title,
                    a.year = $year,
                    a.pub_year = $pub_year,
                    a.version = $version,
                    a.authors = $authors,
                    a.updated_at = datetime()
            """,
                article_id=metadata.article_id,
                doi=metadata.doi,
                title=metadata.title,
                year=metadata.publication_year,
                pub_year=metadata.publication_year,
                version=metadata.version,
                authors=metadata.authors
            )
    
    def import_articles_batch(self, articles: List[ArticleMetadata]):
        """Import multiple articles efficiently."""
        if not articles:
            return
        
        with self.driver.session() as session:
            session.run("""
                UNWIND $batch as article
                MERGE (a:Article {article_id: article.article_id})
                SET a.doi = article.doi,
                    a.title = article.title,
                    a.year = article.year,
                    a.pub_year = article.pub_year,
                    a.version = article.version,
                    a.authors = article.authors,
                    a.updated_at = datetime()
            """,
                batch=[{
                    'article_id': a.article_id,
                    'doi': a.doi,
                    'title': a.title,
                    'year': a.publication_year,
                    'pub_year': a.publication_year,
                    'version': a.version,
                    'authors': a.authors
                } for a in articles]
            )
        
        logger.info(f"✅ Imported {len(articles)} articles")
    
    def import_citation_edge(self, edge: CitationEdge):
        """
        Import single citation edge (idempotent).
        
        Creates both articles if they don't exist.
        """
        with self.driver.session() as session:
            session.run("""
                MERGE (source:Article {article_id: $source_id})
                ON CREATE SET source.doi = $source_doi
                
                MERGE (target:Article {article_id: $target_id})
                ON CREATE SET target.doi = $target_doi
                
                MERGE (source)-[c:CITES {reference_id: $ref_id}]->(target)
                SET c.citation_count = $count,
                    c.sections = $sections,
                    c.source_doi = $source_doi,
                    c.target_doi = $target_doi,
                    c.updated_at = datetime()
            """,
                source_id=edge.source_article_id,
                target_id=edge.target_article_id,
                source_doi=edge.source_doi,
                target_doi=edge.target_doi,
                ref_id=edge.reference_id,
                count=edge.citation_count,
                sections=list(edge.sections)
            )
    
    def import_edges_batch(self, edges: List[CitationEdge]):
        """Import multiple citation edges efficiently."""
        if not edges:
            return
        
        with self.driver.session() as session:
            session.run("""
                UNWIND $batch as edge
                
                MERGE (source:Article {article_id: edge.source_id})
                ON CREATE SET source.doi = edge.source_doi
                
                MERGE (target:Article {article_id: edge.target_id})
                ON CREATE SET target.doi = edge.target_doi
                
                MERGE (source)-[c:CITES {reference_id: edge.ref_id}]->(target)
                SET c.citation_count = edge.count,
                    c.sections = edge.sections,
                    c.source_doi = edge.source_doi,
                    c.target_doi = edge.target_doi,
                    c.updated_at = datetime()
            """,
                batch=[{
                    'source_id': e.source_article_id,
                    'target_id': e.target_article_id,
                    'source_doi': e.source_doi,
                    'target_doi': e.target_doi,
                    'ref_id': e.reference_id,
                    'count': e.citation_count,
                    'sections': list(e.sections)
                } for e in edges]
            )
        
        logger.info(f"✅ Imported {len(edges)} citation edges")
    
    def get_stats(self) -> Dict:
        """Get current graph statistics."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (a:Article)
                OPTIONAL MATCH ()-[c:CITES]->()
                RETURN count(DISTINCT a) as articles, count(c) as citations
            """)
            record = result.single()
            return {
                'articles': record['articles'],
                'citations': record['citations']
            }
    
    def update_citation_contexts(
        self,
        source_article_id: str,
        target_article_id: str,
        ref_id: str,
        contexts: List[CitationContext]
    ):
        """
        Update a CITES edge with citation contexts and evidence segments.
        
        Args:
            source_article_id: Citing article ID
            target_article_id: Reference article ID
            ref_id: Reference ID
            contexts: List of CitationContext objects with evidence
        """
        # Convert contexts to dict format
        contexts_data = []
        for ctx in contexts:
            context_dict = {
                'instance_id': ctx.instance_id,
                'section': ctx.section,
                'context_text': ctx.context_text,
                'evidence_count': len(ctx.evidence_segments),
                'evidence_segments': [
                    {
                        'section': seg.section,
                        'text': seg.text,
                        'similarity_score': seg.similarity_score,
                        'retrieval_method': seg.retrieval_method,
                        'paragraph_index': seg.paragraph_index
                    }
                    for seg in ctx.evidence_segments
                ]
            }
            contexts_data.append(context_dict)
        
        # Serialize to JSON string for Neo4j storage
        contexts_json = json.dumps(contexts_data)
        
        with self.driver.session() as session:
            session.run("""
                MATCH (source:Article {article_id: $source_id})
                      -[c:CITES {reference_id: $ref_id}]->
                      (target:Article {article_id: $target_id})
                SET c.citation_contexts_json = $contexts_json,
                    c.context_count = $context_count,
                    c.qualified = true,
                    c.qualified_at = datetime()
            """,
                source_id=source_article_id,
                target_id=target_article_id,
                ref_id=ref_id,
                contexts_json=contexts_json,
                context_count=len(contexts)
            )
        
        logger.debug(
            f"Updated citation contexts: {source_article_id} → {target_article_id} "
            f"({len(contexts)} instances, {sum(len(c.evidence_segments) for c in contexts)} evidence)"
        )
    
    def get_unqualified_citations(self, limit: int = None) -> List[Dict]:
        """
        Get eLife→eLife citations that haven't been qualified yet.
        
        Args:
            limit: Maximum number to return (None for all)
        
        Returns:
            List of citation dicts with source/target info
        """
        query = """
            MATCH (source:Article)-[c:CITES]->(target:Article)
            WHERE source.doi STARTS WITH '10.7554/eLife'
              AND target.doi STARTS WITH '10.7554/eLife'
              AND (c.qualified IS NULL OR c.qualified = false)
            RETURN source.article_id as source_id,
                   target.article_id as target_id,
                   source.doi as source_doi,
                   target.doi as target_doi,
                   c.reference_id as ref_id,
                   c.citation_count as count
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        with self.driver.session() as session:
            result = session.run(query)
            citations = [dict(record) for record in result]
        
        logger.info(f"Found {len(citations)} unqualified eLife→eLife citations")
        return citations
