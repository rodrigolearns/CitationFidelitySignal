"""Neo4j client for fetching citation qualification data."""
import json
from typing import List, Dict, Optional
from neo4j import GraphDatabase


class Neo4jClient:
    """Client for querying Neo4j citation data."""
    
    def __init__(self, uri: str = "bolt://localhost:7687", 
                 user: str = "neo4j", 
                 password: str = "elifecitations2024"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        """Close the Neo4j driver."""
        self.driver.close()
    
    def get_qualified_citations(self) -> List[Dict]:
        """
        Get all qualified citations with metadata and classifications.
        
        Returns:
            List of citation dictionaries with source/target metadata and classifications.
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (source:Article)-[c:CITES]->(target:Article)
                WHERE c.qualified = true
                RETURN 
                    source.article_id as source_id,
                    source.doi as source_doi,
                    source.title as source_title,
                    source.pub_year as source_year,
                    source.authors as source_authors,
                    target.article_id as target_id,
                    target.doi as target_doi,
                    target.title as target_title,
                    target.pub_year as target_year,
                    target.authors as target_authors,
                    c.reference_id as reference_id,
                    c.context_count as context_count,
                    c.qualified_at as qualified_at,
                    c.classified as classified,
                    c.citation_contexts_json as contexts_json
                ORDER BY c.qualified_at DESC
            """)
            
            citations = []
            for record in result:
                # Extract primary classification from contexts
                classification = None
                manually_reviewed = False
                
                if record["contexts_json"]:
                    try:
                        contexts = json.loads(record["contexts_json"])
                        if contexts and len(contexts) > 0:
                            # Use first context's classification as primary
                            first_ctx = contexts[0]
                            if 'classification' in first_ctx:
                                classification = first_ctx['classification'].get('category')
                                manually_reviewed = first_ctx['classification'].get('manually_reviewed', False)
                    except:
                        pass
                
                citations.append({
                    "source_id": record["source_id"],
                    "source_doi": record["source_doi"],
                    "source_title": record["source_title"],
                    "source_year": record["source_year"],
                    "source_authors": record["source_authors"],
                    "target_id": record["target_id"],
                    "target_doi": record["target_doi"],
                    "target_title": record["target_title"],
                    "target_year": record["target_year"],
                    "target_authors": record["target_authors"],
                    "reference_id": record["reference_id"],
                    "context_count": record["context_count"],
                    "qualified_at": str(record["qualified_at"]) if record["qualified_at"] else None,
                    "classified": bool(record.get("classified")),
                    "classification": classification,
                    "manually_reviewed": manually_reviewed
                })
            
            return citations
    
    def get_citation_detail(self, source_id: str, target_id: str) -> Optional[Dict]:
        """
        Get detailed citation data including contexts and evidence.
        
        Args:
            source_id: Source article ID
            target_id: Target article ID
            
        Returns:
            Dictionary with full citation data including contexts and evidence segments.
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (source:Article)-[c:CITES]->(target:Article)
                WHERE source.article_id = $source_id 
                  AND target.article_id = $target_id
                  AND c.qualified = true
                RETURN 
                    source.article_id as source_id,
                    source.doi as source_doi,
                    source.title as source_title,
                    source.pub_date as source_date,
                    target.article_id as target_id,
                    target.doi as target_doi,
                    target.title as target_title,
                    target.pub_date as target_date,
                    c.reference_id as reference_id,
                    c.context_count as context_count,
                    c.citation_contexts_json as contexts_json,
                    c.qualified_at as qualified_at
                LIMIT 1
            """, source_id=source_id, target_id=target_id)
            
            record = result.single()
            if not record:
                return None
            
            # Parse the JSON string containing contexts and evidence
            contexts_data = []
            if record["contexts_json"]:
                try:
                    contexts_data = json.loads(record["contexts_json"])
                except json.JSONDecodeError:
                    contexts_data = []
            
            return {
                "source": {
                    "id": record["source_id"],
                    "doi": record["source_doi"],
                    "title": record["source_title"],
                    "date": record["source_date"]
                },
                "target": {
                    "id": record["target_id"],
                    "doi": record["target_doi"],
                    "title": record["target_title"],
                    "date": record["target_date"]
                },
                "reference_id": record["reference_id"],
                "context_count": record["context_count"],
                "contexts": contexts_data,
                "qualified_at": str(record["qualified_at"]) if record["qualified_at"] else None
            }
    
    def get_stats(self) -> Dict:
        """Get overall statistics."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH ()-[c:CITES]->()
                WHERE c.qualified = true
                RETURN 
                    count(c) as qualified_citations,
                    sum(c.context_count) as total_contexts
            """)
            
            record = result.single()
            
            # Get classification stats
            class_result = session.run("""
                MATCH ()-[c:CITES]->()
                WHERE c.classified = true
                RETURN count(c) as classified_count
            """)
            class_record = class_result.single()
            
            return {
                "qualified_citations": record["qualified_citations"],
                "total_contexts": record["total_contexts"],
                "classified_citations": class_record["classified_count"] if class_record else 0
            }
    
    def update_review_status(
        self,
        source_id: str,
        target_id: str,
        reviewed: bool
    ) -> bool:
        """Update manual review status for a citation."""
        with self.driver.session() as session:
            # Load current contexts
            result = session.run("""
                MATCH (source:Article {article_id: $source_id})
                      -[c:CITES]->
                      (target:Article {article_id: $target_id})
                RETURN c.citation_contexts_json as contexts_json
            """, source_id=source_id, target_id=target_id)
            
            record = result.single()
            if not record or not record['contexts_json']:
                return False
            
            # Parse and update
            contexts = json.loads(record['contexts_json'])
            for ctx in contexts:
                if 'classification' not in ctx:
                    ctx['classification'] = {}
                ctx['classification']['manually_reviewed'] = reviewed
            
            # Save back
            session.run("""
                MATCH (source:Article {article_id: $source_id})
                      -[c:CITES]->
                      (target:Article {article_id: $target_id})
                SET c.citation_contexts_json = $contexts_json
            """, 
                source_id=source_id,
                target_id=target_id,
                contexts_json=json.dumps(contexts)
            )
            
            return True
    
    def update_user_classification(
        self,
        source_id: str,
        target_id: str,
        instance_id: int,
        user_classification: str
    ) -> bool:
        """Update user's classification override for a specific context."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (source:Article {article_id: $source_id})
                      -[c:CITES]->
                      (target:Article {article_id: $target_id})
                RETURN c.citation_contexts_json as contexts_json
            """, source_id=source_id, target_id=target_id)
            
            record = result.single()
            if not record or not record['contexts_json']:
                return False
            
            contexts = json.loads(record['contexts_json'])
            for ctx in contexts:
                if ctx.get('instance_id') == instance_id:
                    if 'classification' not in ctx:
                        ctx['classification'] = {}
                    ctx['classification']['user_classification'] = user_classification
                    break
            
            session.run("""
                MATCH (source:Article {article_id: $source_id})
                      -[c:CITES]->
                      (target:Article {article_id: $target_id})
                SET c.citation_contexts_json = $contexts_json
            """,
                source_id=source_id,
                target_id=target_id,
                contexts_json=json.dumps(contexts)
            )
            
            return True
    
    def update_user_comment(
        self,
        source_id: str,
        target_id: str,
        instance_id: int,
        comment: str
    ) -> bool:
        """Update user's comment for a specific context."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (source:Article {article_id: $source_id})
                      -[c:CITES]->
                      (target:Article {article_id: $target_id})
                RETURN c.citation_contexts_json as contexts_json
            """, source_id=source_id, target_id=target_id)
            
            record = result.single()
            if not record or not record['contexts_json']:
                return False
            
            contexts = json.loads(record['contexts_json'])
            for ctx in contexts:
                if ctx.get('instance_id') == instance_id:
                    if 'classification' not in ctx:
                        ctx['classification'] = {}
                    ctx['classification']['user_comment'] = comment
                    break
            
            session.run("""
                MATCH (source:Article {article_id: $source_id})
                      -[c:CITES]->
                      (target:Article {article_id: $target_id})
                SET c.citation_contexts_json = $contexts_json
            """,
                source_id=source_id,
                target_id=target_id,
                contexts_json=json.dumps(contexts)
            )
            
            return True
