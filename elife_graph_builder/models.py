"""Data models for eLife citation graph."""

from datetime import datetime
from typing import List, Optional, Set
from pydantic import BaseModel, Field, validator
import uuid


class ArticleMetadata(BaseModel):
    """Metadata for an eLife article."""
    
    article_id: str
    doi: str
    title: str
    publication_year: int
    publication_date: Optional[datetime] = None
    version: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    abstract: Optional[str] = None
    xml_file_path: str
    
    @validator('doi')
    def validate_doi(cls, v):
        """Ensure DOI is properly formatted."""
        if not v.startswith('10.'):
            raise ValueError(f'Invalid DOI format: {v}')
        return v.strip()
    
    @validator('article_id', 'doi')
    def strip_whitespace(cls, v):
        """Strip whitespace from string fields."""
        return v.strip() if isinstance(v, str) else v


class Reference(BaseModel):
    """A reference from the bibliography."""
    
    ref_id: str  # The ID from <ref id="...">
    doi: Optional[str] = None
    journal: Optional[str] = None
    title: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    is_elife: bool = False  # Computed: whether this references an eLife paper
    target_article_id: Optional[str] = None  # If eLife paper, the article ID
    
    @validator('doi')
    def normalize_doi(cls, v):
        """Normalize DOI format."""
        if v is None:
            return None
        # Remove common prefixes
        v = v.strip()
        for prefix in ['https://doi.org/', 'http://doi.org/', 'doi:', 'DOI:']:
            if v.startswith(prefix):
                v = v[len(prefix):]
        return v.strip()


class CitationAnchor(BaseModel):
    """An in-text citation location."""
    
    anchor_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_article_id: str
    reference_id: str  # The rid attribute from <xref>
    section: Optional[str] = None
    paragraph_text: str
    sentence_text: Optional[str] = None
    char_offset_start: int = 0
    char_offset_end: int = 0
    xml_path: Optional[str] = None
    context_before: str = ""
    context_after: str = ""


class CitationEdge(BaseModel):
    """A citation edge between two articles."""
    
    source_article_id: str
    target_article_id: str
    source_doi: str
    target_doi: str
    reference_id: str  # The ref_id from bibliography
    citation_anchors: List[CitationAnchor] = Field(default_factory=list)
    citation_count: int = 0
    sections: Set[str] = Field(default_factory=set)
    
    class Config:
        """Pydantic configuration."""
        # Allow mutable default for sections set
        validate_assignment = True


class ProcessedArticle(BaseModel):
    """Complete processed article with all citation data."""
    
    metadata: ArticleMetadata
    references: List[Reference]
    citation_anchors: List[CitationAnchor]
    elife_citations: List[CitationEdge] = Field(default_factory=list)
    
    @property
    def elife_reference_count(self) -> int:
        """Count of references to eLife papers."""
        return sum(1 for ref in self.references if ref.is_elife)
    
    @property
    def total_reference_count(self) -> int:
        """Total reference count."""
        return len(self.references)


class ParsingError(BaseModel):
    """Record of a parsing error."""
    
    article_id: Optional[str] = None
    file_path: str
    error_type: str
    error_message: str
    timestamp: datetime = Field(default_factory=datetime.now)


class EvidenceSegment(BaseModel):
    """A relevant passage from a reference article."""
    
    section: str  # Section where evidence was found (e.g., "Results")
    text: str  # The actual text of the evidence passage
    similarity_score: float  # Semantic similarity score (0-1)
    retrieval_method: str = "hybrid"  # How it was retrieved (bm25, semantic, hybrid)
    paragraph_index: Optional[int] = None  # Position in article


class CitationContext(BaseModel):
    """A 4-sentence context window around an in-text citation."""
    
    instance_id: int  # Which instance of this citation (1st, 2nd, 3rd mention)
    source_article_id: str
    target_article_id: str
    ref_id: str  # Reference ID from bibliography
    section: str  # Section containing the citation
    
    # The 4-sentence window
    sentence_before_2: str = ""  # 2nd sentence before citation
    sentence_before_1: str = ""  # 1st sentence before citation
    citation_sentence: str = ""  # Sentence containing the citation
    sentence_after_1: str = ""  # 1st sentence after citation
    
    # Full context as single string
    context_text: str = ""
    
    # Evidence from reference article
    evidence_segments: List[EvidenceSegment] = Field(default_factory=list)
    
    def __post_init__(self):
        """Build context_text from individual sentences."""
        if not self.context_text:
            parts = [
                self.sentence_before_2,
                self.sentence_before_1,
                self.citation_sentence,
                self.sentence_after_1
            ]
            self.context_text = " ".join(s for s in parts if s)


class CitationContextWithEvidence(BaseModel):
    """Complete citation qualification data ready for analysis."""
    
    source_doi: str
    target_doi: str
    ref_id: str
    contexts: List[CitationContext] = Field(default_factory=list)


class CitationClassification(BaseModel):
    """LLM classification of a citation context."""
    
    classification: str  # SUPPORT, CONTRADICT, NOT_SUBSTANTIATE, etc.
    confidence: float  # 0.0-1.0
    justification: str  # LLM's reasoning (2-3 sentences)
    classified_at: Optional[str] = None  # ISO timestamp
    model_used: str = "gpt-5-mini"
    tokens_used: Optional[int] = None
    
    # User review fields
    manually_reviewed: bool = False
    user_classification: Optional[str] = None  # User's override
    user_comment: Optional[str] = None  # User's notes
