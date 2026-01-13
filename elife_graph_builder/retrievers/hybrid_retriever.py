"""Hybrid BM25 + Semantic evidence retrieval."""

from typing import List
import logging

from ..models import EvidenceSegment
from .bm25_retriever import BM25Retriever
from .semantic_retriever import SemanticRetriever

logger = logging.getLogger(__name__)


class HybridEvidenceRetriever:
    """Combines BM25 keyword search with semantic similarity."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize hybrid retriever.
        
        Args:
            model_name: Sentence transformer model for semantic retrieval
        """
        self.bm25 = BM25Retriever()
        self.semantic = SemanticRetriever(model_name=model_name)
        logger.info("Hybrid retriever initialized (BM25 + Semantic)")
    
    def retrieve(
        self,
        citation_context: str,
        reference_article_xml: str,
        bm25_top_n: int = 20,
        final_top_k: int = 5,
        min_similarity: float = 0.7,
        minimum_segments: int = 3
    ) -> List[EvidenceSegment]:
        """
        Hybrid retrieval: BM25 filtering + semantic re-ranking.
        
        Stage 1 (BM25): Fast keyword-based filtering to get candidate passages
        Stage 2 (Semantic): Re-rank candidates using semantic similarity
        
        IMPORTANT: Always returns at least `minimum_segments` results, even if
        similarity scores are low. This ensures LLM always has evidence to evaluate.
        
        Args:
            citation_context: Citation context text
            reference_article_xml: Full JATS XML of reference article
            bm25_top_n: Number of candidates to get from BM25 (default: 20)
            final_top_k: Final number of evidence segments (default: 5)
            min_similarity: Initial minimum semantic similarity threshold (default: 0.7)
            minimum_segments: Always return at least this many (default: 3)
        
        Returns:
            List of EvidenceSegment objects, ranked by semantic similarity
        """
        logger.info(f"Starting hybrid retrieval for context: {citation_context[:50]}...")
        
        # Stage 1: BM25 keyword search (fast filtering)
        logger.debug(f"Stage 1: BM25 search (top_n={bm25_top_n})")
        self.bm25.build_index(reference_article_xml)
        bm25_candidates = self.bm25.search(citation_context, top_n=bm25_top_n)
        
        logger.info(f"BM25 returned {len(bm25_candidates)} candidate paragraphs")
        
        if not bm25_candidates:
            logger.warning("No BM25 candidates found")
            return []
        
        # Stage 2: Semantic re-ranking with adaptive threshold
        evidence_segments = []
        current_threshold = min_similarity
        
        # Try progressively lower thresholds until we have enough segments
        thresholds = [min_similarity, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0]
        
        for threshold in thresholds:
            if threshold > min_similarity:
                continue  # Skip higher thresholds
            
            evidence_segments = self.semantic.retrieve_evidence(
                citation_context,
                bm25_candidates,
                top_k=max(final_top_k, minimum_segments),  # Get enough for minimum
                min_similarity=threshold
            )
            
            if len(evidence_segments) >= minimum_segments:
                current_threshold = threshold
                break
        
        # Update retrieval method to "hybrid"
        for segment in evidence_segments:
            segment.retrieval_method = "hybrid"
        
        # Log results
        if current_threshold < min_similarity:
            logger.warning(
                f"Lowered threshold from {min_similarity:.2f} to {current_threshold:.2f} "
                f"to get {len(evidence_segments)} segments (minimum: {minimum_segments})"
            )
        else:
            logger.info(
                f"Hybrid retrieval returned {len(evidence_segments)} evidence segments "
                f"(similarity >= {current_threshold:.2f})"
            )
        
        # Ensure we have at least minimum_segments (take top by score)
        if len(evidence_segments) < minimum_segments and len(bm25_candidates) >= minimum_segments:
            logger.warning(
                f"Only {len(evidence_segments)} segments found, forcing minimum {minimum_segments}"
            )
            # Get top N by similarity, even with very low scores
            all_scored = self.semantic.retrieve_evidence(
                citation_context,
                bm25_candidates,
                top_k=minimum_segments,
                min_similarity=0.0  # No threshold
            )
            evidence_segments = all_scored[:minimum_segments]
        
        return evidence_segments
    
    def batch_retrieve(
        self,
        citation_contexts: List[str],
        reference_article_xmls: List[str],
        bm25_top_n: int = 20,
        final_top_k: int = 5,
        min_similarity: float = 0.7
    ) -> List[List[EvidenceSegment]]:
        """
        Retrieve evidence for multiple citation contexts.
        
        Args:
            citation_contexts: List of citation context texts
            reference_article_xmls: List of reference article XMLs
            bm25_top_n: Number of BM25 candidates
            final_top_k: Final number per context
            min_similarity: Minimum similarity threshold
        
        Returns:
            List of evidence segment lists
        """
        results = []
        
        for context, xml in zip(citation_contexts, reference_article_xmls):
            evidence = self.retrieve(
                context,
                xml,
                bm25_top_n=bm25_top_n,
                final_top_k=final_top_k,
                min_similarity=min_similarity
            )
            results.append(evidence)
        
        return results


def retrieve_hybrid_evidence(
    citation_context: str,
    reference_article_xml: str,
    bm25_top_n: int = 20,
    final_top_k: int = 5,
    min_similarity: float = 0.7
) -> List[EvidenceSegment]:
    """
    Convenience function for hybrid evidence retrieval.
    
    Args:
        citation_context: Citation context text
        reference_article_xml: Full JATS XML of reference article
        bm25_top_n: Number of BM25 candidates
        final_top_k: Final number of results
        min_similarity: Minimum similarity threshold
    
    Returns:
        List of EvidenceSegment objects
    """
    retriever = HybridEvidenceRetriever()
    return retriever.retrieve(
        citation_context,
        reference_article_xml,
        bm25_top_n=bm25_top_n,
        final_top_k=final_top_k,
        min_similarity=min_similarity
    )
