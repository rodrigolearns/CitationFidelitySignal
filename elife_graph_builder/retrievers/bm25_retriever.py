"""BM25-based evidence retrieval for reference articles."""

import re
from typing import List, Tuple, Optional
from lxml import etree
import logging
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class Paragraph:
    """A paragraph from an article with metadata."""
    
    def __init__(self, text: str, section: str, index: int):
        """
        Initialize a paragraph.
        
        Args:
            text: Paragraph text content
            section: Section name (e.g., "Results")
            index: Paragraph index in document
        """
        self.text = text
        self.section = section
        self.index = index
        self.tokens = self._tokenize(text)
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization: lowercase and split on non-alphanumeric."""
        text = text.lower()
        tokens = re.findall(r'\b\w+\b', text)
        return tokens
    
    def __repr__(self):
        preview = self.text[:50] + "..." if len(self.text) > 50 else self.text
        return f"Paragraph(section='{self.section}', text='{preview}')"


class BM25Retriever:
    """BM25-based keyword search for evidence retrieval."""
    
    def __init__(self):
        """Initialize the BM25 retriever."""
        self.paragraphs: List[Paragraph] = []
        self.bm25: Optional[BM25Okapi] = None
    
    def build_index(self, xml_content: str) -> int:
        """
        Build BM25 index from article XML.
        
        Args:
            xml_content: Full JATS XML content
        
        Returns:
            Number of paragraphs indexed
        """
        self.paragraphs = self._extract_paragraphs(xml_content)
        
        if not self.paragraphs:
            logger.warning("No paragraphs extracted from article")
            return 0
        
        # Build BM25 index from paragraph tokens
        corpus = [p.tokens for p in self.paragraphs]
        self.bm25 = BM25Okapi(corpus)
        
        logger.info(f"Built BM25 index with {len(self.paragraphs)} paragraphs")
        return len(self.paragraphs)
    
    def search(self, query_text: str, top_n: int = 10) -> List[Paragraph]:
        """
        Search for relevant paragraphs using BM25.
        
        Args:
            query_text: Citation context text to search for
            top_n: Number of top results to return
        
        Returns:
            List of top-N most relevant paragraphs
        """
        if self.bm25 is None:
            raise ValueError("Index not built. Call build_index() first.")
        
        # Tokenize query
        query_tokens = self._tokenize_query(query_text)
        
        if not query_tokens:
            logger.warning("Empty query after tokenization")
            return []
        
        # Get BM25 scores
        scores = self.bm25.get_scores(query_tokens)
        
        # Get top-N indices
        top_indices = sorted(
            range(len(scores)), 
            key=lambda i: scores[i], 
            reverse=True
        )[:top_n]
        
        # Filter out zero scores
        top_indices = [i for i in top_indices if scores[i] > 0]
        
        # Return top paragraphs
        results = [self.paragraphs[i] for i in top_indices]
        
        logger.debug(f"BM25 search returned {len(results)} results for query")
        return results
    
    def _extract_paragraphs(self, xml_content: str) -> List[Paragraph]:
        """Extract all paragraphs from article body."""
        try:
            root = etree.fromstring(xml_content.encode('utf-8'))
        except etree.XMLSyntaxError as e:
            logger.error(f"XML parsing error: {e}")
            return []
        
        paragraphs = []
        index = 0
        
        # Find all paragraphs in body
        body = root.find('.//body')
        if body is None:
            logger.warning("No <body> element found in XML")
            return []
        
        # Iterate through sections
        for sec in body.findall('.//sec'):
            section_name = self._get_section_name(sec)
            
            # Find paragraphs in this section
            for p_elem in sec.findall('.//p'):
                text = self._extract_text(p_elem)
                
                if text and len(text.strip()) > 20:  # Minimum length threshold
                    para = Paragraph(text, section_name, index)
                    paragraphs.append(para)
                    index += 1
        
        # Also check abstract
        abstract_paras = self._extract_abstract_paragraphs(root)
        for para in abstract_paras:
            para.index = index
            paragraphs.append(para)
            index += 1
        
        return paragraphs
    
    def _extract_abstract_paragraphs(self, root: etree.Element) -> List[Paragraph]:
        """Extract paragraphs from abstract."""
        paragraphs = []
        abstract = root.find('.//abstract')
        
        if abstract is not None:
            for p_elem in abstract.findall('.//p'):
                text = self._extract_text(p_elem)
                if text and len(text.strip()) > 20:
                    paragraphs.append(Paragraph(text, "Abstract", 0))
        
        return paragraphs
    
    def _get_section_name(self, sec: etree.Element) -> str:
        """Get section title."""
        title_elem = sec.find('./title')
        if title_elem is not None:
            return self._extract_text(title_elem)
        return "Unknown Section"
    
    def _extract_text(self, element: etree.Element) -> str:
        """Recursively extract text from element."""
        text_parts = []
        
        if element.text:
            text_parts.append(element.text)
        
        for child in element:
            text_parts.append(self._extract_text(child))
            if child.tail:
                text_parts.append(child.tail)
        
        return ''.join(text_parts).strip()
    
    def _tokenize_query(self, text: str) -> List[str]:
        """Tokenize query text."""
        text = text.lower()
        tokens = re.findall(r'\b\w+\b', text)
        
        # Remove common stop words (simple list)
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these',
            'those', 'it', 'its', 'they', 'their', 'them', 'we', 'our', 'us'
        }
        
        tokens = [t for t in tokens if t not in stop_words and len(t) > 2]
        return tokens


def search_reference_article(
    reference_xml: str,
    citation_context: str,
    top_n: int = 10
) -> List[Paragraph]:
    """
    Convenience function to search a reference article.
    
    Args:
        reference_xml: Full JATS XML of reference article
        citation_context: Citation context text to search for
        top_n: Number of results to return
    
    Returns:
        List of relevant paragraphs
    """
    retriever = BM25Retriever()
    retriever.build_index(reference_xml)
    return retriever.search(citation_context, top_n=top_n)
