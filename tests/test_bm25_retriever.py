"""Tests for BM25Retriever."""

import pytest
from elife_graph_builder.retrievers.bm25_retriever import BM25Retriever, Paragraph


def test_paragraph_tokenization():
    """Test paragraph tokenization."""
    para = Paragraph(
        text="Neural circuits process information rapidly.",
        section="Results",
        index=0
    )
    
    assert "neural" in para.tokens
    assert "circuits" in para.tokens
    assert "process" in para.tokens
    assert "information" in para.tokens


def test_build_index(sample_article_xml):
    """Test building BM25 index from XML."""
    retriever = BM25Retriever()
    count = retriever.build_index(sample_article_xml)
    
    assert count > 0
    assert len(retriever.paragraphs) == count
    assert retriever.bm25 is not None


def test_search_relevant_content(sample_article_xml):
    """Test searching for relevant paragraphs."""
    retriever = BM25Retriever()
    retriever.build_index(sample_article_xml)
    
    # Search for something that should be in the sample article
    query = "neural circuits pattern recognition behavior"
    results = retriever.search(query, top_n=5)
    
    # Should return results
    assert len(results) > 0
    assert all(isinstance(p, Paragraph) for p in results)
    
    # Results should have text
    for para in results:
        assert len(para.text) > 0
        assert para.section != ""


def test_search_no_matches(sample_article_xml):
    """Test search with completely irrelevant query."""
    retriever = BM25Retriever()
    retriever.build_index(sample_article_xml)
    
    # Search for something very unlikely to be in article
    query = "xylophone zymology quintessential"
    results = retriever.search(query, top_n=5)
    
    # Might return empty or low-score results
    # Just verify it doesn't crash
    assert isinstance(results, list)


def test_search_before_build():
    """Test that search fails before building index."""
    retriever = BM25Retriever()
    
    with pytest.raises(ValueError, match="Index not built"):
        retriever.search("test query")


def test_tokenize_query():
    """Test query tokenization with stop word removal."""
    retriever = BM25Retriever()
    
    query = "The neural circuits process information in the brain"
    tokens = retriever._tokenize_query(query)
    
    # Should have meaningful words
    assert "neural" in tokens
    assert "circuits" in tokens
    assert "process" in tokens
    assert "information" in tokens
    assert "brain" in tokens
    
    # Should remove stop words
    assert "the" not in tokens
    assert "in" not in tokens
