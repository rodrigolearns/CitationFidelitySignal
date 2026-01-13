"""Matcher for identifying eLife→eLife citations."""

import logging
from typing import Dict, List, Optional
from ..models import Reference, CitationEdge, CitationAnchor, ArticleMetadata
from ..config import Config

logger = logging.getLogger(__name__)


class ELifeRegistry:
    """Registry of all eLife articles for matching citations."""
    
    def __init__(self):
        """Initialize empty registry."""
        self.doi_to_article_id: Dict[str, str] = {}
        self.article_id_to_doi: Dict[str, str] = {}
        self.article_id_to_metadata: Dict[str, ArticleMetadata] = {}
    
    def add_article(self, metadata: ArticleMetadata):
        """Register an eLife article."""
        self.doi_to_article_id[metadata.doi] = metadata.article_id
        self.article_id_to_doi[metadata.article_id] = metadata.doi
        self.article_id_to_metadata[metadata.article_id] = metadata
    
    def is_elife_doi(self, doi: str) -> bool:
        """Check if a DOI belongs to an eLife paper."""
        if not doi:
            return False
        
        # Normalize DOI
        doi = self._normalize_doi(doi)
        
        # Check if it matches eLife pattern
        if Config.ELIFE_DOI_PREFIX in doi:
            return True
        
        # Check if it's in our registry
        return doi in self.doi_to_article_id
    
    def get_article_id(self, doi: str) -> Optional[str]:
        """Get article ID from DOI if it's an eLife paper."""
        if not doi:
            return None
        
        doi = self._normalize_doi(doi)
        
        # Try direct lookup first
        if doi in self.doi_to_article_id:
            return self.doi_to_article_id[doi]
        
        # If it's an eLife DOI but not in registry, extract ID from DOI
        if Config.ELIFE_DOI_PREFIX in doi:
            try:
                # Extract article ID from DOI (e.g., "10.7554/eLife.12345" -> "12345")
                article_id = doi.split('eLife.')[-1].split('.')[0]
                return article_id
            except:
                pass
        
        return None
    
    def _normalize_doi(self, doi: str) -> str:
        """Normalize DOI format for consistent matching."""
        doi = doi.strip()
        
        # Remove common prefixes (case-insensitive)
        doi_lower = doi.lower()
        for prefix in ['https://doi.org/', 'http://doi.org/', 'doi:', 'dx.doi.org/']:
            if doi_lower.startswith(prefix):
                doi = doi[len(prefix):]
                break
        
        return doi.strip()
    
    def size(self) -> int:
        """Return number of registered articles."""
        return len(self.article_id_to_doi)


class ELifeMatcher:
    """Match citations to identify eLife→eLife relationships."""
    
    def __init__(self, registry: ELifeRegistry):
        """Initialize matcher with a registry."""
        self.registry = registry
        self.logger = logging.getLogger(__name__)
    
    def identify_elife_references(self, references: List[Reference]) -> List[Reference]:
        """
        Identify which references are to eLife papers.
        
        Updates the is_elife and target_article_id fields.
        """
        for ref in references:
            if ref.doi:
                if self.registry.is_elife_doi(ref.doi):
                    ref.is_elife = True
                    ref.target_article_id = self.registry.get_article_id(ref.doi)
        
        return references
    
    def match_citations(
        self,
        source_article: ArticleMetadata,
        references: List[Reference],
        citation_anchors: List[CitationAnchor]
    ) -> List[CitationEdge]:
        """
        Create citation edges for all eLife→eLife citations.
        
        Args:
            source_article: The source article metadata
            references: List of references from the bibliography
            citation_anchors: List of in-text citation anchors
        
        Returns:
            List of citation edges (only for eLife→eLife citations)
        """
        # First, identify eLife references
        self.identify_elife_references(references)
        
        # Create a mapping of ref_id to reference
        ref_map = {ref.ref_id: ref for ref in references}
        
        # Group anchors by reference ID
        anchors_by_ref: Dict[str, List[CitationAnchor]] = {}
        for anchor in citation_anchors:
            ref_id = anchor.reference_id
            if ref_id not in anchors_by_ref:
                anchors_by_ref[ref_id] = []
            anchors_by_ref[ref_id].append(anchor)
        
        # Create citation edges for eLife references that have anchors
        edges = []
        for ref in references:
            if not ref.is_elife or not ref.target_article_id:
                continue
            
            # Get anchors for this reference
            anchors = anchors_by_ref.get(ref.ref_id, [])
            
            # Skip if no in-text citations found
            if not anchors:
                self.logger.debug(
                    f"Reference {ref.ref_id} to eLife article {ref.target_article_id} "
                    f"has no in-text citations"
                )
                continue
            
            # Collect sections where citation appears
            sections = {anchor.section for anchor in anchors if anchor.section}
            
            # Get target DOI (normalize it)
            target_doi = ref.doi if ref.doi else f"10.7554/eLife.{ref.target_article_id}"
            
            edge = CitationEdge(
                source_article_id=source_article.article_id,
                target_article_id=ref.target_article_id,
                source_doi=source_article.doi,
                target_doi=target_doi,
                reference_id=ref.ref_id,
                citation_anchors=anchors,
                citation_count=len(anchors),
                sections=sections
            )
            edges.append(edge)
        
        return edges
    
    def find_citation_chains(
        self,
        start_article_id: str,
        edges: List[CitationEdge],
        max_depth: int = 3
    ) -> List[List[str]]:
        """
        Find citation chains starting from an article.
        
        This is a simple implementation - more sophisticated graph traversal
        will be done in Neo4j.
        """
        # Build adjacency list
        graph: Dict[str, List[str]] = {}
        for edge in edges:
            if edge.source_article_id not in graph:
                graph[edge.source_article_id] = []
            graph[edge.source_article_id].append(edge.target_article_id)
        
        # DFS to find chains
        chains = []
        
        def dfs(current: str, path: List[str], depth: int):
            if depth >= max_depth:
                chains.append(path.copy())
                return
            
            if current not in graph:
                chains.append(path.copy())
                return
            
            for neighbor in graph[current]:
                if neighbor not in path:  # Avoid cycles
                    path.append(neighbor)
                    dfs(neighbor, path, depth + 1)
                    path.pop()
        
        dfs(start_article_id, [start_article_id], 0)
        return chains
