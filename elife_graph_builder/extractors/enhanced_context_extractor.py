"""
Enhanced context extractor for Part 5: Deep Impact Analysis.

Extracts full sections, author affiliations, funding information, and provides
citation type-aware section selection for cost-optimized LLM analysis.
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from lxml import etree

logger = logging.getLogger(__name__)


class EnhancedContextExtractor:
    """Extract enriched context for deep impact analysis."""
    
    SECTION_TYPE_MAP = {
        'intro': 'Introduction',
        'introduction': 'Introduction',
        'methods': 'Methods',
        'materials|methods': 'Methods',
        'materials-methods': 'Methods',
        'results': 'Results',
        'results|discussion': 'Results',
        'discussion': 'Discussion',
        'conclusions': 'Conclusions',
        'conclusion': 'Conclusions',
    }
    
    def __init__(self):
        """Initialize extractor."""
        self.logger = logging.getLogger(__name__)
    
    def extract_full_sections(self, xml_path: Path) -> Dict[str, str]:
        """
        Extract all major sections from the paper.
        
        Returns:
            Dict mapping section names to full section text
            Example: {'Introduction': '...', 'Methods': '...', 'Results': '...'}
        """
        try:
            tree = etree.parse(str(xml_path))
            root = tree.getroot()
            
            sections = {}
            
            # Extract abstract
            abstract = self._extract_abstract(root)
            if abstract:
                sections['Abstract'] = abstract
            
            # Extract body sections
            body = root.find('.//body')
            if body is not None:
                for sec in body.findall('.//sec'):
                    section_type = sec.get('sec-type', '')
                    
                    # Get section title
                    title_elem = sec.find('.//title')
                    title = self._get_text_content(title_elem) if title_elem is not None else None
                    
                    # Map to standard section name
                    section_name = self._map_section_type(section_type, title)
                    
                    # Extract full section text (all paragraphs)
                    section_text = self._extract_section_text(sec)
                    
                    if section_text:
                        # If section already exists, append (handles multiple Results sections, etc.)
                        if section_name in sections:
                            sections[section_name] += "\n\n" + section_text
                        else:
                            sections[section_name] = section_text
            
            return sections
            
        except Exception as e:
            self.logger.error(f"Failed to extract sections from {xml_path}: {e}")
            return {}
    
    def extract_authors_with_affiliations(self, xml_path: Path) -> List[Dict[str, any]]:
        """
        Extract authors with their affiliations.
        
        Returns:
            List of dicts with 'name', 'affiliations', 'is_corresponding'
        """
        try:
            tree = etree.parse(str(xml_path))
            root = tree.getroot()
            
            article_meta = root.find('.//article-meta')
            if article_meta is None:
                return []
            
            # Extract all affiliations first
            affiliations = self._extract_affiliations_map(article_meta)
            
            # Extract authors with their affiliation references
            authors = []
            contrib_group = article_meta.find('.//contrib-group')
            if contrib_group is not None:
                for contrib in contrib_group.findall('.//contrib'):
                    if contrib.get('contrib-type') == 'author':
                        author_info = self._extract_author_info(contrib, affiliations)
                        if author_info:
                            authors.append(author_info)
            
            return authors
            
        except Exception as e:
            self.logger.error(f"Failed to extract authors from {xml_path}: {e}")
            return []
    
    def extract_funding_sources(self, xml_path: Path) -> List[str]:
        """
        Extract funding sources from the paper.
        
        Returns:
            List of funding source strings
        """
        try:
            tree = etree.parse(str(xml_path))
            root = tree.getroot()
            
            funding_sources = []
            
            # Look for funding-group in article-meta or back matter
            funding_group = root.find('.//funding-group')
            if funding_group is not None:
                for award_group in funding_group.findall('.//award-group'):
                    # Extract funding source
                    funding_source = award_group.find('.//funding-source')
                    if funding_source is not None:
                        source_text = self._get_text_content(funding_source)
                        if source_text:
                            funding_sources.append(source_text)
            
            return list(set(funding_sources))  # Remove duplicates
            
        except Exception as e:
            self.logger.error(f"Failed to extract funding from {xml_path}: {e}")
            return []
    
    def extract_relevant_sections(
        self,
        xml_path: Path,
        citation_section: str,
        citation_type: str
    ) -> Dict[str, str]:
        """
        Extract only relevant sections based on citation location and type.
        
        This is the KEY optimization for cost reduction (67% token savings).
        
        Args:
            xml_path: Path to XML file
            citation_section: Section where citation appears (e.g., "Discussion")
            citation_type: Type of citation (CONCEPTUAL, METHODOLOGICAL, BACKGROUND, ATTRIBUTION)
        
        Returns:
            Dict of relevant sections only
        """
        all_sections = self.extract_full_sections(xml_path)
        
        # Always include abstract for context
        relevant = {}
        if 'Abstract' in all_sections:
            relevant['Abstract'] = all_sections['Abstract']
        
        # Add sections based on citation type
        if citation_type == 'METHODOLOGICAL':
            # For methodological citations, focus on Methods and Results
            if 'Methods' in all_sections:
                relevant['Methods'] = all_sections['Methods']
            if 'Results' in all_sections:
                relevant['Results'] = all_sections['Results']
        
        elif citation_type == 'CONCEPTUAL':
            # For conceptual citations, focus on Results and Discussion
            if 'Results' in all_sections:
                relevant['Results'] = all_sections['Results']
            if 'Discussion' in all_sections:
                relevant['Discussion'] = all_sections['Discussion']
        
        elif citation_type == 'BACKGROUND':
            # For background citations, Introduction is key
            if 'Introduction' in all_sections:
                relevant['Introduction'] = all_sections['Introduction']
        
        elif citation_type == 'ATTRIBUTION':
            # For attribution, check all major sections
            for section in ['Introduction', 'Methods', 'Results', 'Discussion']:
                if section in all_sections:
                    relevant[section] = all_sections[section]
        
        else:
            # Unknown type - include all main sections
            for section in ['Introduction', 'Methods', 'Results', 'Discussion']:
                if section in all_sections:
                    relevant[section] = all_sections[section]
        
        return relevant
    
    def get_citation_location(
        self,
        xml_path: Path,
        ref_id: str
    ) -> Optional[Dict[str, any]]:
        """
        Find the location of a citation in the paper.
        
        Returns:
            Dict with 'section', 'section_title', 'paragraph_number', 'full_paragraph', 'surrounding_context'
        """
        try:
            tree = etree.parse(str(xml_path))
            root = tree.getroot()
            
            body = root.find('.//body')
            if body is None:
                return None
            
            # Search for citation anchor
            for sec in body.findall('.//sec'):
                section_type = sec.get('sec-type', '')
                title_elem = sec.find('.//title')
                section_title = self._get_text_content(title_elem) if title_elem is not None else ''
                section_name = self._map_section_type(section_type, section_title)
                
                # Find all paragraphs in section
                paragraphs = sec.findall('.//p')
                for para_idx, para in enumerate(paragraphs):
                    # Check if this paragraph contains the citation
                    xrefs = para.findall('.//xref')
                    for xref in xrefs:
                        if xref.get('ref-type') == 'bibr' and xref.get('rid') == ref_id:
                            # Found the citation!
                            full_paragraph = self._get_text_content(para)
                            
                            # Get surrounding context (2 paragraphs before/after)
                            surrounding = self._get_surrounding_paragraphs(
                                paragraphs, para_idx, context_size=2
                            )
                            
                            return {
                                'section': section_name,
                                'section_title': section_title,
                                'paragraph_number': para_idx + 1,
                                'full_paragraph': full_paragraph,
                                'surrounding_context': surrounding
                            }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get citation location from {xml_path}: {e}")
            return None
    
    # Helper methods
    
    def _extract_abstract(self, root: etree.Element) -> Optional[str]:
        """Extract abstract text."""
        abstract_elem = root.find('.//abstract')
        if abstract_elem is not None:
            # Get all paragraph text
            paragraphs = []
            for p in abstract_elem.findall('.//p'):
                text = self._get_text_content(p)
                if text:
                    paragraphs.append(text)
            return "\n\n".join(paragraphs) if paragraphs else None
        return None
    
    def _extract_section_text(self, sec_elem: etree.Element) -> str:
        """Extract all text from a section element."""
        paragraphs = []
        for p in sec_elem.findall('.//p'):
            text = self._get_text_content(p)
            if text:
                paragraphs.append(text)
        return "\n\n".join(paragraphs)
    
    def _map_section_type(self, section_type: str, title: Optional[str]) -> str:
        """Map section type or title to standard section name."""
        # Try section type first
        section_type_lower = section_type.lower()
        for key, value in self.SECTION_TYPE_MAP.items():
            if key in section_type_lower:
                return value
        
        # Try title if section type didn't match
        if title:
            title_lower = title.lower()
            for key, value in self.SECTION_TYPE_MAP.items():
                if key in title_lower:
                    return value
            # Return title if it's a main section
            return title
        
        return "Other"
    
    def _extract_affiliations_map(self, article_meta: etree.Element) -> Dict[str, str]:
        """Extract affiliations and map them by ID."""
        affiliations = {}
        for aff in article_meta.findall('.//aff'):
            aff_id = aff.get('id', '')
            aff_text = self._get_text_content(aff)
            if aff_id and aff_text:
                affiliations[aff_id] = aff_text
        return affiliations
    
    def _extract_author_info(
        self,
        contrib: etree.Element,
        affiliations: Dict[str, str]
    ) -> Optional[Dict]:
        """Extract author information including affiliations."""
        name_elem = contrib.find('.//name')
        if name_elem is None:
            return None
        
        surname = name_elem.find('.//surname')
        given_names = name_elem.find('.//given-names')
        
        if surname is None or surname.text is None:
            return None
        
        # Format name
        author_name = surname.text.strip()
        if given_names is not None and given_names.text:
            initials = ''.join([n[0] for n in given_names.text.split()])
            author_name = f"{author_name} {initials}"
        
        # Extract affiliation references
        author_affiliations = []
        for xref in contrib.findall('.//xref'):
            if xref.get('ref-type') == 'aff':
                aff_id = xref.get('rid', '')
                if aff_id in affiliations:
                    author_affiliations.append(affiliations[aff_id])
        
        # Check if corresponding author
        is_corresponding = contrib.get('corresp') == 'yes'
        
        return {
            'name': author_name,
            'affiliations': author_affiliations,
            'is_corresponding': is_corresponding
        }
    
    def _get_text_content(self, elem: Optional[etree.Element]) -> str:
        """Get all text content from an element, recursively."""
        if elem is None:
            return ""
        
        # Get text from element and all children
        texts = [elem.text or ""]
        for child in elem:
            texts.append(self._get_text_content(child))
            texts.append(child.tail or "")
        
        return "".join(texts).strip()
    
    def _get_surrounding_paragraphs(
        self,
        paragraphs: List[etree.Element],
        target_index: int,
        context_size: int = 2
    ) -> str:
        """Get paragraphs surrounding the target paragraph."""
        start_idx = max(0, target_index - context_size)
        end_idx = min(len(paragraphs), target_index + context_size + 1)
        
        context_paragraphs = []
        for i in range(start_idx, end_idx):
            text = self._get_text_content(paragraphs[i])
            if text:
                context_paragraphs.append(text)
        
        return "\n\n".join(context_paragraphs)
