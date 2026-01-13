"""Tests for SemanticRetriever."""

import pytest
import numpy as np
from elife_graph_builder.retrievers.semantic_retriever import SemanticRetriever
from elife_graph_builder.retrievers.bm25_retriever import Paragraph
from elife_graph_builder.models import EvidenceSegment


@pytest.fixture(scope="module")
def semantic_retriever():
    """Fixture to load model once per test module."""
    return SemanticRetriever(model_name="all-MiniLM-L6-v2")


def test_embed_text(semantic_retriever):
    """Test text embedding generation."""
    text = "Neural circuits process information."
    embedding = semantic_retriever.embed_text(text)
    
    # Should return numpy array
    assert isinstance(embedding, np.ndarray)
    
    # Should have reasonable dimensions (model produces 384-dim vectors)
    assert len(embedding) == 384
    
    # Should be normalized (for this model)
    assert -2.0 <= np.mean(embedding) <= 2.0


def test_embed_batch(semantic_retriever):
    """Test batch embedding generation."""
    texts = [
        "Neural circuits are complex.",
        "Neurons fire in patterns.",
        "Synaptic connections enable learning."
    ]
    
    embeddings = semantic_retriever.embed_batch(texts)
    
    # Should return matrix with correct shape
    assert embeddings.shape == (3, 384)
    
    # Each row should be a valid embedding
    for emb in embeddings:
        assert -2.0 <= np.mean(emb) <= 2.0


def test_compute_similarity(semantic_retriever):
    """Test similarity computation."""
    text1 = "Neural circuits process information."
    text2 = "Neurons process data in networks."
    text3 = "The weather is sunny today."
    
    emb1 = semantic_retriever.embed_text(text1)
    emb2 = semantic_retriever.embed_text(text2)
    emb3 = semantic_retriever.embed_text(text3)
    
    # Similar texts should have higher similarity
    sim_related = semantic_retriever.compute_similarity(emb1, emb2)
    sim_unrelated = semantic_retriever.compute_similarity(emb1, emb3)
    
    # Cosine similarity ranges from -1 to 1
    assert -1.0 <= sim_related <= 1.0
    assert -1.0 <= sim_unrelated <= 1.0
    assert sim_related > sim_unrelated
    
    # Self-similarity should be ~1.0
    sim_self = semantic_retriever.compute_similarity(emb1, emb1)
    assert sim_self > 0.99


def test_retrieve_evidence(semantic_retriever):
    """Test evidence retrieval from candidates."""
    citation_context = "Studies show that neural circuits process visual information rapidly."
    
    # Create candidate paragraphs
    candidates = [
        Paragraph(
            "Our experiments revealed that visual processing in neural circuits occurs within 50ms.",
            "Results",
            0
        ),
        Paragraph(
            "The weather patterns changed dramatically over the study period.",
            "Methods",
            1
        ),
        Paragraph(
            "Neural networks in the visual cortex respond to specific stimulus patterns.",
            "Results",
            2
        )
    ]
    
    # Retrieve evidence
    evidence = semantic_retriever.retrieve_evidence(
        citation_context,
        candidates,
        top_k=2,
        min_similarity=0.3  # Lower threshold for test
    )
    
    # Should return EvidenceSegment objects
    assert len(evidence) > 0
    assert all(isinstance(seg, EvidenceSegment) for seg in evidence)
    
    # Should have similarity scores
    for seg in evidence:
        assert 0.0 <= seg.similarity_score <= 1.0
        assert seg.retrieval_method == "semantic"
    
    # First result should be most similar (about visual processing)
    assert evidence[0].similarity_score >= evidence[-1].similarity_score


def test_retrieve_evidence_with_threshold(semantic_retriever):
    """Test that minimum similarity threshold is respected."""
    citation_context = "Neural circuits are important."
    
    candidates = [
        Paragraph(
            "The methodology involved complex statistical analysis.",
            "Methods",
            0
        )
    ]
    
    # High threshold should filter out irrelevant results
    evidence = semantic_retriever.retrieve_evidence(
        citation_context,
        candidates,
        top_k=5,
        min_similarity=0.9  # Very high threshold
    )
    
    # Might return empty or only very relevant results
    assert isinstance(evidence, list)
    for seg in evidence:
        assert seg.similarity_score >= 0.9


def test_retrieve_evidence_empty_candidates(semantic_retriever):
    """Test handling of empty candidate list."""
    citation_context = "Neural circuits process information."
    
    evidence = semantic_retriever.retrieve_evidence(
        citation_context,
        [],
        top_k=3
    )
    
    assert evidence == []
