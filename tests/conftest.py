"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path
from elife_graph_builder.models import ArticleMetadata, Reference, CitationAnchor
from elife_graph_builder.matchers.elife_matcher import ELifeRegistry


@pytest.fixture
def sample_xml_path():
    """Path to sample XML file."""
    return Path(__file__).parent / "fixtures" / "sample_article.xml"


@pytest.fixture
def sample_article_xml(sample_xml_path):
    """Load sample XML content."""
    with open(sample_xml_path, 'r', encoding='utf-8') as f:
        return f.read()


@pytest.fixture
def sample_metadata():
    """Sample article metadata."""
    return ArticleMetadata(
        article_id="12345",
        doi="10.7554/eLife.12345",
        title="Test Article About Neural Circuits",
        publication_year=2023,
        authors=["John Smith", "Jane Doe"],
        xml_file_path="/path/to/sample.xml"
    )


@pytest.fixture
def sample_references():
    """Sample references including eLife papers."""
    return [
        Reference(
            ref_id="bib1",
            doi="10.7554/eLife.11111",
            journal="eLife",
            title="Neural circuit analysis in model organisms",
            year=2020
        ),
        Reference(
            ref_id="bib2",
            doi="10.7554/eLife.22222",
            journal="eLife",
            title="Pattern recognition in neural systems",
            year=2021
        ),
        Reference(
            ref_id="bib3",
            doi="10.1038/nn.9999",
            journal="Nature Neuroscience",
            title="Advanced techniques",
            year=2022
        ),
        Reference(
            ref_id="bib4",
            doi="10.1126/science.8888",
            journal="Science",
            title="Historical perspectives",
            year=2019
        ),
    ]


@pytest.fixture
def sample_citation_anchors():
    """Sample citation anchors."""
    return [
        CitationAnchor(
            source_article_id="12345",
            reference_id="bib1",
            section="Introduction",
            paragraph_text="Neural circuits are complex (Jones et al., 2020).",
            context_before="Neural circuits are ",
            context_after="). Previous work has shown"
        ),
        CitationAnchor(
            source_article_id="12345",
            reference_id="bib2",
            section="Introduction",
            paragraph_text="Previous work has shown interesting patterns (Brown, 2021; Miller et al., 2022).",
            context_before="Previous work has shown interesting patterns (",
            context_after="; Miller et al., 2022)."
        ),
        CitationAnchor(
            source_article_id="12345",
            reference_id="bib1",
            section="Results",
            paragraph_text="Our findings confirm previous observations (Jones et al., 2020) and extend them.",
            context_before="Our findings confirm previous observations (",
            context_after=") and extend them."
        ),
    ]


@pytest.fixture
def elife_registry():
    """Sample eLife registry with test articles."""
    registry = ELifeRegistry()
    
    # Add some test articles
    articles = [
        ArticleMetadata(
            article_id="11111",
            doi="10.7554/eLife.11111",
            title="Neural circuit analysis",
            publication_year=2020,
            xml_file_path="/path/to/11111.xml"
        ),
        ArticleMetadata(
            article_id="22222",
            doi="10.7554/eLife.22222",
            title="Pattern recognition",
            publication_year=2021,
            xml_file_path="/path/to/22222.xml"
        ),
        ArticleMetadata(
            article_id="12345",
            doi="10.7554/eLife.12345",
            title="Test article",
            publication_year=2023,
            xml_file_path="/path/to/12345.xml"
        ),
    ]
    
    for article in articles:
        registry.add_article(article)
    
    return registry
