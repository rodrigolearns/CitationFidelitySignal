"""Semantic embedding-based evidence retrieval."""

import numpy as np
from typing import List
import logging
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from ..models import EvidenceSegment
from .bm25_retriever import Paragraph

logger = logging.getLogger(__name__)


class SemanticRetriever:
    """Semantic similarity-based evidence retrieval using embeddings."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the semantic retriever.
        
        Args:
            model_name: Name of sentence-transformers model to use
                       Default: all-MiniLM-L6-v2 (fast, good quality)
        """
        logger.info(f"Loading sentence transformer model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        logger.info(f"Model loaded: {model_name}")
    
    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for a text string.
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector as numpy array
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding
    
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for a batch of texts.
        
        Args:
            texts: List of texts to embed
        
        Returns:
            Matrix of embeddings (n_texts x embedding_dim)
        """
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings
    
    def compute_similarity(
        self, 
        embedding1: np.ndarray, 
        embedding2: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
        
        Returns:
            Cosine similarity score (0-1)
        """
        # Reshape to 2D if needed
        if embedding1.ndim == 1:
            embedding1 = embedding1.reshape(1, -1)
        if embedding2.ndim == 1:
            embedding2 = embedding2.reshape(1, -1)
        
        similarity = cosine_similarity(embedding1, embedding2)[0][0]
        return float(similarity)
    
    def retrieve_evidence(
        self,
        citation_context: str,
        candidate_paragraphs: List[Paragraph],
        top_k: int = 3,
        min_similarity: float = 0.7
    ) -> List[EvidenceSegment]:
        """
        Retrieve most relevant evidence segments using semantic similarity.
        
        Args:
            citation_context: Citation context text
            candidate_paragraphs: List of candidate paragraphs (from BM25)
            top_k: Number of top segments to return
            min_similarity: Minimum similarity threshold
        
        Returns:
            List of EvidenceSegment objects with similarity scores
        """
        if not candidate_paragraphs:
            logger.warning("No candidate paragraphs provided")
            return []
        
        # Embed citation context
        context_embedding = self.embed_text(citation_context)
        
        # Embed all candidate paragraphs
        paragraph_texts = [p.text for p in candidate_paragraphs]
        paragraph_embeddings = self.embed_batch(paragraph_texts)
        
        # Compute similarities
        similarities = []
        for i, (para, embedding) in enumerate(zip(candidate_paragraphs, paragraph_embeddings)):
            similarity = self.compute_similarity(context_embedding, embedding)
            similarities.append((para, similarity))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Filter by minimum similarity and take top-K
        evidence_segments = []
        for para, score in similarities[:top_k]:
            if score >= min_similarity:
                segment = EvidenceSegment(
                    section=para.section,
                    text=para.text,
                    similarity_score=score,
                    retrieval_method="semantic",
                    paragraph_index=para.index
                )
                evidence_segments.append(segment)
        
        logger.info(
            f"Retrieved {len(evidence_segments)} evidence segments "
            f"(threshold: {min_similarity}, top_k: {top_k})"
        )
        
        return evidence_segments
    
    def batch_retrieve_evidence(
        self,
        citation_contexts: List[str],
        candidate_paragraphs_list: List[List[Paragraph]],
        top_k: int = 3,
        min_similarity: float = 0.7
    ) -> List[List[EvidenceSegment]]:
        """
        Retrieve evidence for multiple citation contexts in batch.
        
        Args:
            citation_contexts: List of citation context texts
            candidate_paragraphs_list: List of candidate paragraph lists
            top_k: Number of top segments per context
            min_similarity: Minimum similarity threshold
        
        Returns:
            List of evidence segment lists (one per context)
        """
        results = []
        
        for context, candidates in zip(citation_contexts, candidate_paragraphs_list):
            evidence = self.retrieve_evidence(
                context,
                candidates,
                top_k=top_k,
                min_similarity=min_similarity
            )
            results.append(evidence)
        
        return results


def retrieve_semantic_evidence(
    citation_context: str,
    candidate_paragraphs: List[Paragraph],
    top_k: int = 3,
    min_similarity: float = 0.7,
    model_name: str = "all-MiniLM-L6-v2"
) -> List[EvidenceSegment]:
    """
    Convenience function for semantic evidence retrieval.
    
    Args:
        citation_context: Citation context text
        candidate_paragraphs: List of candidate paragraphs
        top_k: Number of top results
        min_similarity: Minimum similarity threshold
        model_name: Sentence transformer model name
    
    Returns:
        List of EvidenceSegment objects
    """
    retriever = SemanticRetriever(model_name=model_name)
    return retriever.retrieve_evidence(
        citation_context,
        candidate_paragraphs,
        top_k=top_k,
        min_similarity=min_similarity
    )
