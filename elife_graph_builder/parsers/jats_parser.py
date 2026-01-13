"""JATS XML parser for eLife articles."""

import logging
from pathlib import Path
from typing import List, Optional, Tuple
from lxml import etree
from datetime import datetime

from ..models import ArticleMetadata, Reference, CitationAnchor

logger = logging.getLogger(__name__)


class JATSParser:
    """Parser for JATS XML format used by eLife."""
    
    # Common JATS XML namespaces
    NAMESPACES = {
        'jats': 'http://jats.nlm.nih.gov',
        'xlink': 'http://www.w3.org/1999/xlink',
        'mml': 'http://www.w3.org/1998/Math/MathML',
    }
    
    def __init__(self):
        """Initialize parser."""
        self.logger = logging.getLogger(__name__)
    
    def parse_file(self, xml_path: Path) -> Optional[Tuple[ArticleMetadata, List[Reference], List[CitationAnchor]]]:
        """
        Parse a JATS XML file.
        
        Returns:
            Tuple of (metadata, references, citation_anchors) or None if parsing fails
        """
        try:
            tree = etree.parse(str(xml_path))
            root = tree.getroot()
            
            metadata = self.extract_metadata(root, xml_path)
            references = self.extract_references(root)
            citation_anchors = self.extract_citation_anchors(root, metadata.article_id)
            
            return metadata, references, citation_anchors
            
        except Exception as e:
            self.logger.error(f"Failed to parse {xml_path}: {e}")
            return None
    
    def extract_metadata(self, root: etree.Element, xml_path: Path) -> ArticleMetadata:
        """Extract article metadata from XML."""
        
        # Try multiple paths for article-meta (with and without namespace)
        article_meta = root.find('.//article-meta')
        if article_meta is None:
            article_meta = root.find('.//{http://jats.nlm.nih.gov}article-meta')
        if article_meta is None:
            article_meta = root.find('.//front/article-meta')
        
        if article_meta is None:
            raise ValueError("Could not find article-meta element")
        
        # Extract article ID (multiple possible locations)
        article_id = self._extract_article_id(article_meta)
        
        # Extract DOI
        doi = self._extract_doi(article_meta)
        
        # Extract title
        title_elem = article_meta.find('.//article-title')
        if title_elem is None:
            title_elem = article_meta.find('.//{http://jats.nlm.nih.gov}article-title')
        title = self._get_text_content(title_elem) if title_elem is not None else "Unknown Title"
        
        # Extract publication year
        year = self._extract_publication_year(article_meta)
        
        # Extract version (if available)
        version = self._extract_version(article_meta)
        
        # Extract authors (optional)
        authors = self._extract_authors(article_meta)
        
        return ArticleMetadata(
            article_id=article_id,
            doi=doi,
            title=title,
            publication_year=year,
            version=version,
            authors=authors,
            xml_file_path=str(xml_path)
        )
    
    def extract_references(self, root: etree.Element) -> List[Reference]:
        """Extract all references from the bibliography."""
        references = []
        
        # Find ref-list (with and without namespace)
        ref_list = root.find('.//ref-list')
        if ref_list is None:
            ref_list = root.find('.//{http://jats.nlm.nih.gov}ref-list')
        if ref_list is None:
            ref_list = root.find('.//back/ref-list')
        
        if ref_list is None:
            self.logger.warning("No ref-list found in document")
            return references
        
        # Find all ref elements
        ref_elements = ref_list.findall('.//ref')
        if not ref_elements:
            ref_elements = ref_list.findall('.//{http://jats.nlm.nih.gov}ref')
        
        for ref_elem in ref_elements:
            try:
                ref = self._parse_reference(ref_elem)
                if ref:
                    references.append(ref)
            except Exception as e:
                self.logger.warning(f"Failed to parse reference: {e}")
        
        return references
    
    def extract_citation_anchors(self, root: etree.Element, article_id: str) -> List[CitationAnchor]:
        """Extract all in-text citation anchors."""
        anchors = []
        
        # Find body element
        body = root.find('.//body')
        if body is None:
            body = root.find('.//{http://jats.nlm.nih.gov}body')
        if body is None:
            self.logger.warning("No body element found")
            return anchors
        
        # Find all xref elements with ref-type="bibr"
        xrefs = []
        for xref in body.iter():
            # Check both with and without namespace
            tag = xref.tag.replace('{http://jats.nlm.nih.gov}', '')
            if tag == 'xref' and xref.get('ref-type') == 'bibr':
                xrefs.append(xref)
        
        for xref in xrefs:
            try:
                anchor = self._parse_citation_anchor(xref, article_id)
                if anchor:
                    anchors.append(anchor)
            except Exception as e:
                self.logger.debug(f"Failed to parse citation anchor: {e}")
        
        return anchors
    
    # Helper methods
    
    def _extract_article_id(self, article_meta: etree.Element) -> str:
        """Extract article ID from various possible locations."""
        # Try article-id with pub-id-type="publisher-id"
        for elem in article_meta.findall('.//article-id'):
            if elem.get('pub-id-type') == 'publisher-id':
                return elem.text.strip()
        
        # Try elocation-id
        elocation = article_meta.find('.//elocation-id')
        if elocation is not None and elocation.text:
            return elocation.text.strip()
        
        # Extract from DOI as last resort
        doi = self._extract_doi(article_meta)
        if doi and 'eLife.' in doi:
            return doi.split('eLife.')[-1].split('.')[0]
        
        raise ValueError("Could not extract article ID")
    
    def _extract_doi(self, article_meta: etree.Element) -> str:
        """Extract DOI from article metadata."""
        # Try article-id with pub-id-type="doi"
        for elem in article_meta.findall('.//article-id'):
            if elem.get('pub-id-type') == 'doi':
                return elem.text.strip()
        
        # Try pub-id with pub-id-type="doi"
        for elem in article_meta.findall('.//pub-id'):
            if elem.get('pub-id-type') == 'doi':
                return elem.text.strip()
        
        raise ValueError("Could not extract DOI")
    
    def _extract_publication_year(self, article_meta: etree.Element) -> int:
        """Extract publication year."""
        # Try pub-date with pub-type="epub" or "ppub"
        for pub_date in article_meta.findall('.//pub-date'):
            year_elem = pub_date.find('.//year')
            if year_elem is not None and year_elem.text:
                try:
                    return int(year_elem.text)
                except ValueError:
                    pass
        
        # Default to current year if not found
        self.logger.warning("Could not extract publication year, using current year")
        return datetime.now().year
    
    def _extract_version(self, article_meta: etree.Element) -> Optional[str]:
        """Extract article version if available."""
        version_elem = article_meta.find('.//article-version')
        if version_elem is not None and version_elem.text:
            return version_elem.text.strip()
        return None
    
    def _extract_authors(self, article_meta: etree.Element) -> List[str]:
        """
        Extract author names in eLife format (abbreviated).
        
        Format: "Surname Initial(s)" (e.g., "Smith J", "Smith JA")
        
        Returns:
            List of author names in eLife format
        """
        authors = []
        contrib_group = article_meta.find('.//contrib-group')
        if contrib_group is not None:
            for contrib in contrib_group.findall('.//contrib'):
                if contrib.get('contrib-type') == 'author':
                    name_elem = contrib.find('.//name')
                    if name_elem is not None:
                        surname = name_elem.find('.//surname')
                        given_names = name_elem.find('.//given-names')
                        if surname is not None and surname.text:
                            # Format: "Surname Initial(s)"
                            author_name = surname.text.strip()
                            
                            if given_names is not None and given_names.text:
                                # Extract initials from given names
                                given = given_names.text.strip()
                                # Handle multiple given names (e.g., "John A" -> "JA")
                                initials = ''.join([
                                    name[0].upper() 
                                    for name in given.split() 
                                    if name
                                ])
                                author_name = f"{author_name} {initials}"
                            
                            authors.append(author_name)
        return authors
    
    def _parse_reference(self, ref_elem: etree.Element) -> Optional[Reference]:
        """Parse a single reference element."""
        ref_id = ref_elem.get('id')
        if not ref_id:
            return None
        
        # Extract DOI
        doi = None
        for pub_id in ref_elem.findall('.//pub-id'):
            if pub_id.get('pub-id-type') == 'doi' and pub_id.text:
                doi = pub_id.text.strip()
                break
        
        # Try ext-link if pub-id not found
        if not doi:
            for ext_link in ref_elem.findall('.//ext-link'):
                if ext_link.get('ext-link-type') == 'doi' and ext_link.text:
                    doi = ext_link.text.strip()
                    break
        
        # Extract journal/source
        journal = None
        source_elem = ref_elem.find('.//source')
        if source_elem is not None:
            journal = self._get_text_content(source_elem)
        
        # Extract title
        title = None
        article_title = ref_elem.find('.//article-title')
        if article_title is not None:
            title = self._get_text_content(article_title)
        
        # Extract year
        year = None
        year_elem = ref_elem.find('.//year')
        if year_elem is not None and year_elem.text:
            try:
                year = int(year_elem.text)
            except ValueError:
                pass
        
        return Reference(
            ref_id=ref_id,
            doi=doi,
            journal=journal,
            title=title,
            year=year
        )
    
    def _parse_citation_anchor(self, xref: etree.Element, article_id: str) -> Optional[CitationAnchor]:
        """Parse an in-text citation anchor."""
        rid = xref.get('rid')
        if not rid:
            return None
        
        # Get paragraph text
        paragraph = self._find_parent_by_tag(xref, 'p')
        paragraph_text = self._get_text_content(paragraph) if paragraph is not None else ""
        
        # Get section
        section_elem = self._find_parent_by_tag(xref, 'sec')
        section = None
        if section_elem is not None:
            title_elem = section_elem.find('.//title')
            if title_elem is not None:
                section = self._get_text_content(title_elem)
        
        # Get surrounding context
        context_before = ""
        context_after = ""
        if paragraph is not None:
            # Get text before and after the xref
            # This is simplified - full implementation would be more sophisticated
            full_text = self._get_text_content(paragraph)
            xref_text = self._get_text_content(xref)
            if xref_text in full_text:
                idx = full_text.index(xref_text)
                context_before = full_text[max(0, idx-50):idx]
                context_after = full_text[idx+len(xref_text):idx+len(xref_text)+50]
        
        return CitationAnchor(
            source_article_id=article_id,
            reference_id=rid,
            section=section,
            paragraph_text=paragraph_text[:1000],  # Limit length
            context_before=context_before,
            context_after=context_after
        )
    
    def _find_parent_by_tag(self, element: etree.Element, tag: str) -> Optional[etree.Element]:
        """Find parent element by tag name."""
        parent = element.getparent()
        while parent is not None:
            parent_tag = parent.tag.replace('{http://jats.nlm.nih.gov}', '')
            if parent_tag == tag:
                return parent
            parent = parent.getparent()
        return None
    
    def _get_text_content(self, element: Optional[etree.Element]) -> str:
        """Extract all text content from an element and its children."""
        if element is None:
            return ""
        
        # Use itertext() which properly handles text extraction
        texts = list(element.itertext())
        return ' '.join(text.strip() for text in texts if text.strip())
