"""Tests for JATS XML parser."""

import pytest
from pathlib import Path
from elife_graph_builder.parsers.jats_parser import JATSParser
from elife_graph_builder.models import ArticleMetadata, Reference


class TestJATSParser:
    """Test suite for JATS XML parser."""
    
    def test_parser_initialization(self):
        """Test parser can be initialized."""
        parser = JATSParser()
        assert parser is not None
    
    def test_parse_sample_file(self, sample_xml_path):
        """Test parsing a complete sample file."""
        parser = JATSParser()
        result = parser.parse_file(sample_xml_path)
        
        assert result is not None
        metadata, references, citation_anchors = result
        
        # Check metadata
        assert metadata.article_id == "12345"
        assert metadata.doi == "10.7554/eLife.12345"
        assert "Neural Circuits" in metadata.title
        assert metadata.publication_year == 2023
        assert len(metadata.authors) == 2
        
        # Check references
        assert len(references) == 4
        assert any(ref.ref_id == "bib1" for ref in references)
        
        # Check citation anchors
        assert len(citation_anchors) > 0
    
    def test_extract_metadata(self, sample_xml_path):
        """Test metadata extraction."""
        parser = JATSParser()
        result = parser.parse_file(sample_xml_path)
        metadata, _, _ = result
        
        assert metadata.article_id == "12345"
        assert metadata.doi == "10.7554/eLife.12345"
        assert metadata.publication_year == 2023
        assert "Smith" in metadata.authors[0]
        assert "Doe" in metadata.authors[1]
    
    def test_extract_references(self, sample_xml_path):
        """Test reference extraction."""
        parser = JATSParser()
        result = parser.parse_file(sample_xml_path)
        _, references, _ = result
        
        # Should have 4 references
        assert len(references) == 4
        
        # Check first reference (eLife paper)
        bib1 = next(ref for ref in references if ref.ref_id == "bib1")
        assert bib1.doi == "10.7554/eLife.11111"
        assert bib1.journal == "eLife"
        assert bib1.year == 2020
        
        # Check third reference (non-eLife paper)
        bib3 = next(ref for ref in references if ref.ref_id == "bib3")
        assert bib3.doi == "10.1038/nn.9999"
        assert bib3.journal == "Nature Neuroscience"
    
    def test_extract_citation_anchors(self, sample_xml_path):
        """Test in-text citation anchor extraction."""
        parser = JATSParser()
        result = parser.parse_file(sample_xml_path)
        _, _, citation_anchors = result
        
        # Should have multiple anchors
        assert len(citation_anchors) > 0
        
        # Check that bib1 has anchors (it's cited twice)
        bib1_anchors = [a for a in citation_anchors if a.reference_id == "bib1"]
        assert len(bib1_anchors) >= 1
        
        # Check anchor has section info
        first_anchor = citation_anchors[0]
        assert first_anchor.section is not None
        assert first_anchor.paragraph_text != ""
    
    def test_doi_normalization(self):
        """Test DOI normalization in references."""
        from elife_graph_builder.models import Reference
        
        # Test various DOI formats
        ref1 = Reference(
            ref_id="test1",
            doi="https://doi.org/10.7554/eLife.12345"
        )
        assert ref1.doi == "10.7554/eLife.12345"
        
        ref2 = Reference(
            ref_id="test2",
            doi="doi:10.7554/eLife.12345"
        )
        assert ref2.doi == "10.7554/eLife.12345"
        
        ref3 = Reference(
            ref_id="test3",
            doi="  10.7554/eLife.12345  "
        )
        assert ref3.doi == "10.7554/eLife.12345"
    
    def test_parse_nonexistent_file(self):
        """Test parser handles missing files gracefully."""
        parser = JATSParser()
        result = parser.parse_file(Path("/nonexistent/file.xml"))
        assert result is None
    
    def test_metadata_validation(self):
        """Test that metadata validation works."""
        # Valid metadata
        metadata = ArticleMetadata(
            article_id="12345",
            doi="10.7554/eLife.12345",
            title="Test",
            publication_year=2023,
            xml_file_path="/path/to/file.xml"
        )
        assert metadata.doi == "10.7554/eLife.12345"
        
        # Invalid DOI should raise error
        with pytest.raises(ValueError):
            ArticleMetadata(
                article_id="12345",
                doi="invalid-doi",
                title="Test",
                publication_year=2023,
                xml_file_path="/path/to/file.xml"
            )
