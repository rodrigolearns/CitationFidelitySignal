"""Tests for eLife citation matcher."""

import pytest
from elife_graph_builder.matchers.elife_matcher import ELifeRegistry, ELifeMatcher
from elife_graph_builder.models import Reference


class TestELifeRegistry:
    """Test suite for ELifeRegistry."""
    
    def test_registry_initialization(self):
        """Test registry can be initialized."""
        registry = ELifeRegistry()
        assert registry.size() == 0
    
    def test_add_article(self, sample_metadata):
        """Test adding articles to registry."""
        registry = ELifeRegistry()
        registry.add_article(sample_metadata)
        
        assert registry.size() == 1
        assert registry.is_elife_doi("10.7554/eLife.12345")
        assert registry.get_article_id("10.7554/eLife.12345") == "12345"
    
    def test_is_elife_doi(self, elife_registry):
        """Test eLife DOI identification."""
        # Known eLife DOIs
        assert elife_registry.is_elife_doi("10.7554/eLife.11111")
        assert elife_registry.is_elife_doi("10.7554/eLife.99999")  # Pattern match
        
        # Non-eLife DOIs
        assert not elife_registry.is_elife_doi("10.1038/nature.12345")
        assert not elife_registry.is_elife_doi("10.1126/science.123")
        
        # Various formats
        assert elife_registry.is_elife_doi("https://doi.org/10.7554/eLife.12345")
        assert elife_registry.is_elife_doi("doi:10.7554/eLife.12345")
    
    def test_doi_normalization(self, elife_registry):
        """Test DOI normalization."""
        # All these should be recognized as the same DOI
        formats = [
            "10.7554/eLife.11111",
            "https://doi.org/10.7554/eLife.11111",
            "http://doi.org/10.7554/eLife.11111",
            "doi:10.7554/eLife.11111",
            "  10.7554/eLife.11111  ",
        ]
        
        for doi_format in formats:
            assert elife_registry.is_elife_doi(doi_format)
            assert elife_registry.get_article_id(doi_format) == "11111"
    
    def test_get_article_id(self, elife_registry):
        """Test article ID retrieval."""
        # Known article
        assert elife_registry.get_article_id("10.7554/eLife.11111") == "11111"
        
        # Unknown article (but valid eLife DOI)
        assert elife_registry.get_article_id("10.7554/eLife.99999") == "99999"
        
        # Non-eLife DOI
        assert elife_registry.get_article_id("10.1038/nature.123") is None


class TestELifeMatcher:
    """Test suite for ELifeMatcher."""
    
    def test_matcher_initialization(self, elife_registry):
        """Test matcher can be initialized."""
        matcher = ELifeMatcher(elife_registry)
        assert matcher is not None
    
    def test_identify_elife_references(self, elife_registry, sample_references):
        """Test identification of eLife references."""
        matcher = ELifeMatcher(elife_registry)
        
        # Initially, references are not marked as eLife
        assert not sample_references[0].is_elife
        
        # Identify eLife references
        matcher.identify_elife_references(sample_references)
        
        # First two should be eLife
        assert sample_references[0].is_elife
        assert sample_references[0].target_article_id == "11111"
        
        assert sample_references[1].is_elife
        assert sample_references[1].target_article_id == "22222"
        
        # Last two should not be eLife
        assert not sample_references[2].is_elife
        assert not sample_references[3].is_elife
    
    def test_match_citations(
        self, 
        elife_registry, 
        sample_metadata, 
        sample_references, 
        sample_citation_anchors
    ):
        """Test full citation matching."""
        matcher = ELifeMatcher(elife_registry)
        
        edges = matcher.match_citations(
            sample_metadata,
            sample_references,
            sample_citation_anchors
        )
        
        # Should have edges for eLife citations only
        assert len(edges) > 0
        
        # Check first edge
        edge = edges[0]
        assert edge.source_article_id == "12345"
        assert edge.target_article_id in ["11111", "22222"]
        assert edge.citation_count > 0
        assert len(edge.citation_anchors) > 0
    
    def test_match_citations_groups_anchors(
        self, 
        elife_registry, 
        sample_metadata, 
        sample_references, 
        sample_citation_anchors
    ):
        """Test that anchors are correctly grouped by reference."""
        matcher = ELifeMatcher(elife_registry)
        
        edges = matcher.match_citations(
            sample_metadata,
            sample_references,
            sample_citation_anchors
        )
        
        # bib1 is cited twice, so should have 2 anchors
        bib1_edge = next((e for e in edges if e.reference_id == "bib1"), None)
        if bib1_edge:
            assert bib1_edge.citation_count == 2
            assert len(bib1_edge.citation_anchors) == 2
    
    def test_sections_collected(
        self, 
        elife_registry, 
        sample_metadata, 
        sample_references, 
        sample_citation_anchors
    ):
        """Test that sections are collected from anchors."""
        matcher = ELifeMatcher(elife_registry)
        
        edges = matcher.match_citations(
            sample_metadata,
            sample_references,
            sample_citation_anchors
        )
        
        # bib1 is cited in Introduction and Results
        bib1_edge = next((e for e in edges if e.reference_id == "bib1"), None)
        if bib1_edge:
            assert "Introduction" in bib1_edge.sections
            assert "Results" in bib1_edge.sections
    
    def test_no_edges_for_non_elife_citations(
        self, 
        elife_registry, 
        sample_metadata, 
        sample_references, 
        sample_citation_anchors
    ):
        """Test that non-eLife citations don't create edges."""
        matcher = ELifeMatcher(elife_registry)
        
        edges = matcher.match_citations(
            sample_metadata,
            sample_references,
            sample_citation_anchors
        )
        
        # Should only have edges for eLife papers (bib1 and bib2)
        # bib3 and bib4 are not eLife papers
        edge_ref_ids = {e.reference_id for e in edges}
        assert "bib3" not in edge_ref_ids
        assert "bib4" not in edge_ref_ids
