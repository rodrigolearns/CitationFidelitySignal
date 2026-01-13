"""Tests for CitationContextExtractor."""

import pytest
from elife_graph_builder.extractors.context_extractor import CitationContextExtractor


def test_extract_contexts_basic(sample_article_xml):
    """Test basic context extraction."""
    extractor = CitationContextExtractor()
    
    contexts = extractor.extract_contexts(
        xml_content=sample_article_xml,
        source_article_id="12345",
        target_article_id="67890",
        ref_id="bib1"
    )
    
    # Should find at least one context
    assert len(contexts) > 0
    
    # Each context should have required fields
    for context in contexts:
        assert context.source_article_id == "12345"
        assert context.target_article_id == "67890"
        assert context.ref_id == "bib1"
        assert context.section != ""
        assert context.citation_sentence != ""
        assert context.context_text != ""


def test_sentence_splitting():
    """Test sentence splitting logic."""
    extractor = CitationContextExtractor()
    
    text = "This is sentence one. This is sentence two! Is this three? Yes it is."
    sentences = extractor._split_sentences(text)
    
    assert len(sentences) == 4
    assert sentences[0] == "This is sentence one."
    assert sentences[1] == "This is sentence two!"
    assert sentences[2] == "Is this three?"
    assert sentences[3] == "Yes it is."


def test_build_context():
    """Test 4-sentence window construction."""
    extractor = CitationContextExtractor()
    
    sentences = [
        "Sentence zero.",
        "Sentence one.",
        "Sentence two with citation.",
        "Sentence three.",
        "Sentence four."
    ]
    
    context = extractor._build_context(
        sentences=sentences,
        citation_idx=2,
        source_article_id="12345",
        target_article_id="67890",
        ref_id="bib1",
        section="Results",
        instance_id=1
    )
    
    assert context.sentence_before_2 == "Sentence zero."
    assert context.sentence_before_1 == "Sentence one."
    assert context.citation_sentence == "Sentence two with citation."
    assert context.sentence_after_1 == "Sentence three."
    assert "Sentence zero." in context.context_text
    assert "Sentence three." in context.context_text


def test_build_context_at_start():
    """Test context extraction at document start."""
    extractor = CitationContextExtractor()
    
    sentences = [
        "First sentence with citation.",
        "Second sentence.",
        "Third sentence."
    ]
    
    context = extractor._build_context(
        sentences=sentences,
        citation_idx=0,
        source_article_id="12345",
        target_article_id="67890",
        ref_id="bib1",
        section="Introduction",
        instance_id=1
    )
    
    # Should handle missing "before" sentences gracefully
    assert context.sentence_before_2 == ""
    assert context.sentence_before_1 == ""
    assert context.citation_sentence == "First sentence with citation."
    assert context.sentence_after_1 == "Second sentence."


def test_build_context_at_end():
    """Test context extraction at document end."""
    extractor = CitationContextExtractor()
    
    sentences = [
        "Sentence one.",
        "Sentence two.",
        "Last sentence with citation."
    ]
    
    context = extractor._build_context(
        sentences=sentences,
        citation_idx=2,
        source_article_id="12345",
        target_article_id="67890",
        ref_id="bib1",
        section="Discussion",
        instance_id=1
    )
    
    # Should handle missing "after" sentence gracefully
    assert context.sentence_before_2 == "Sentence one."
    assert context.sentence_before_1 == "Sentence two."
    assert context.citation_sentence == "Last sentence with citation."
    assert context.sentence_after_1 == ""
