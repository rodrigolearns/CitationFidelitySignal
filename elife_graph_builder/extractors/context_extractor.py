"""Extract citation contexts from JATS XML articles."""

import re
from typing import List, Optional, Tuple
from lxml import etree
import logging

from ..models import CitationContext

logger = logging.getLogger(__name__)


class CitationContextExtractor:
    """Extract 4-sentence windows around in-text citations."""
    
    def __init__(self):
        """Initialize the context extractor."""
        self.sentence_splitter = re.compile(r'(?<=[.!?])\s+')
    
    def extract_contexts(
        self,
        xml_content: str,
        source_article_id: str,
        target_article_id: str,
        ref_id: str
    ) -> List[CitationContext]:
        """
        Extract all citation contexts for a specific reference.
        
        Args:
            xml_content: Full JATS XML content
            source_article_id: ID of citing article
            target_article_id: ID of reference article
            ref_id: Reference ID (e.g., 'bib23')
        
        Returns:
            List of CitationContext objects, one per citation instance
        """
        try:
            root = etree.fromstring(xml_content.encode('utf-8'))
        except etree.XMLSyntaxError as e:
            logger.error(f"XML parsing error for article {source_article_id}: {e}")
            return []
        
        contexts = []
        instance_id = 1
        
        # Find all <xref> tags that reference this ref_id
        xrefs = root.xpath(f'.//xref[@ref-type="bibr" and @rid="{ref_id}"]')
        
        for xref in xrefs:
            context = self._extract_context_for_xref(
                xref, 
                source_article_id,
                target_article_id,
                ref_id,
                instance_id
            )
            
            if context:
                contexts.append(context)
                instance_id += 1
        
        logger.info(
            f"Extracted {len(contexts)} contexts for {source_article_id} → "
            f"{target_article_id} (ref_id: {ref_id})"
        )
        
        return contexts
    
    def _extract_context_for_xref(
        self,
        xref: etree.Element,
        source_article_id: str,
        target_article_id: str,
        ref_id: str,
        instance_id: int
    ) -> Optional[CitationContext]:
        """Extract context for a single xref element."""
        
        # Find the containing paragraph
        paragraph = self._find_containing_paragraph(xref)
        if paragraph is None:
            logger.warning(f"Could not find paragraph for xref in {source_article_id}")
            return None
        
        # Get section name
        section = self._get_section_name(xref)
        
        # Extract paragraph text
        para_text = self._extract_paragraph_text(paragraph)
        
        # Split into sentences
        sentences = self._split_sentences(para_text)
        
        if not sentences:
            return None
        
        # Extract the in-text citation text (e.g., "Smith et al., 2020")
        in_text_citation = self._extract_text(xref).strip()
        
        # Find which sentence contains the citation
        citation_sentence_idx = self._find_citation_sentence(
            sentences, 
            in_text_citation
        )
        
        if citation_sentence_idx is None:
            logger.warning(
                f"Could not locate citation sentence in {source_article_id}"
            )
            return None
        
        # Extract 4-sentence window (2 before, citation, 1 after)
        context = self._build_context(
            sentences,
            citation_sentence_idx,
            source_article_id,
            target_article_id,
            ref_id,
            section,
            instance_id,
            in_text_citation
        )
        
        return context
    
    def _find_containing_paragraph(self, xref: etree.Element) -> Optional[etree.Element]:
        """Find the <p> element containing this xref."""
        current = xref
        while current is not None:
            if current.tag == 'p':
                return current
            current = current.getparent()
        return None
    
    def _get_section_name(self, xref: etree.Element) -> str:
        """Get the main section (Introduction, Methods, Results, Discussion) containing this xref."""
        # Find all parent sections (from innermost to outermost)
        sections = []
        current = xref
        while current is not None:
            if current.tag == 'sec':
                title_elem = current.find('./title')  # Direct child only
                if title_elem is not None:
                    sections.append(self._extract_text(title_elem))
            current = current.getparent()
        
        # Try to find a main section by checking from outermost to innermost
        # This handles cases where the structure is Main > Sub > SubSub
        for section_title in reversed(sections):
            normalized = self._normalize_section_name(section_title)
            # If normalization returned a standard section (not the original title), use it
            if normalized in ['Introduction', 'Methods', 'Results', 'Discussion', 'Abstract']:
                return normalized
        
        # If no standard section found, return the outermost section or Unknown
        if sections:
            return self._normalize_section_name(sections[-1])
        return "Unknown"
    
    def _normalize_section_name(self, section_title: str) -> str:
        """Normalize section titles to standard categories."""
        section_lower = section_title.lower()
        
        # Map to standard sections
        if 'introduction' in section_lower or 'background' in section_lower:
            return 'Introduction'
        elif 'method' in section_lower or 'material' in section_lower or 'experimental' in section_lower:
            return 'Methods'
        elif 'result' in section_lower or 'finding' in section_lower:
            return 'Results'
        elif 'discussion' in section_lower or 'conclusion' in section_lower:
            return 'Discussion'
        elif 'abstract' in section_lower:
            return 'Abstract'
        elif 'reference' in section_lower or 'bibliograph' in section_lower:
            return 'References'
        else:
            # Return the original title if it doesn't match standard sections
            return section_title
    
    def _extract_paragraph_text(self, paragraph: etree.Element) -> str:
        """Extract all text from a paragraph, preserving inline citations."""
        return self._extract_text(paragraph)
    
    def _extract_text(self, element: etree.Element) -> str:
        """Recursively extract text from an element and its children."""
        text_parts = []
        
        # Get element's direct text
        if element.text:
            text_parts.append(element.text)
        
        # Get text from children
        for child in element:
            # For xref tags, just include the text content
            text_parts.append(self._extract_text(child))
            
            # Get tail text after child
            if child.tail:
                text_parts.append(child.tail)
        
        return ''.join(text_parts).strip()
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Split on sentence boundaries
        sentences = self.sentence_splitter.split(text)
        
        # Clean each sentence
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    def _find_citation_sentence(
        self, 
        sentences: List[str], 
        citation_text: str
    ) -> Optional[int]:
        """Find which sentence contains the citation."""
        # Try exact match first
        for i, sentence in enumerate(sentences):
            if citation_text in sentence:
                return i
        
        # Try fuzzy match (citation might be split across elements)
        citation_words = set(citation_text.lower().split())
        for i, sentence in enumerate(sentences):
            sentence_words = set(sentence.lower().split())
            if citation_words.issubset(sentence_words):
                return i
        
        return None
    
    def _build_context(
        self,
        sentences: List[str],
        citation_idx: int,
        source_article_id: str,
        target_article_id: str,
        ref_id: str,
        section: str,
        instance_id: int,
        in_text_citation: str = ""
    ) -> CitationContext:
        """Build a CitationContext with 4-sentence window."""
        
        # Get sentences with bounds checking
        sent_before_2 = sentences[citation_idx - 2] if citation_idx >= 2 else ""
        sent_before_1 = sentences[citation_idx - 1] if citation_idx >= 1 else ""
        citation_sent = sentences[citation_idx]
        sent_after_1 = (
            sentences[citation_idx + 1] 
            if citation_idx + 1 < len(sentences) 
            else ""
        )
        
        # Build full context text
        context_parts = [sent_before_2, sent_before_1, citation_sent, sent_after_1]
        context_text = " ".join(s for s in context_parts if s)
        
        return CitationContext(
            instance_id=instance_id,
            source_article_id=source_article_id,
            target_article_id=target_article_id,
            ref_id=ref_id,
            section=section,
            in_text_citation=in_text_citation,
            sentence_before_2=sent_before_2,
            sentence_before_1=sent_before_1,
            citation_sentence=citation_sent,
            sentence_after_1=sent_after_1,
            context_text=context_text
        )


def extract_citation_contexts_from_file(
    xml_file_path: str,
    source_article_id: str,
    target_article_id: str,
    ref_id: str
) -> List[CitationContext]:
    """
    Convenience function to extract contexts from a file.
    
    Args:
        xml_file_path: Path to JATS XML file
        source_article_id: ID of citing article
        target_article_id: ID of reference article  
        ref_id: Reference ID
    
    Returns:
        List of CitationContext objects
    """
    with open(xml_file_path, 'r', encoding='utf-8') as f:
        xml_content = f.read()
    
    extractor = CitationContextExtractor()
    return extractor.extract_contexts(
        xml_content,
        source_article_id,
        target_article_id,
        ref_id
    )
