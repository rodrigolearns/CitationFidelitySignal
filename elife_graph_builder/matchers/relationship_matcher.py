"""
Relationship matcher for detecting author and affiliation overlaps.

Used in Workflow 5 to identify self-citations and institutional bias patterns.
"""

import logging
from typing import List, Dict, Set, Tuple, Optional
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class RelationshipMatcher:
    """Match authors and affiliations between papers."""
    
    def __init__(self, affiliation_similarity_threshold: float = 0.8):
        """
        Initialize matcher.
        
        Args:
            affiliation_similarity_threshold: Minimum similarity for affiliation matching (0.0-1.0)
        """
        self.affiliation_threshold = affiliation_similarity_threshold
        self.logger = logging.getLogger(__name__)
    
    def find_shared_authors(
        self,
        authors1: List[Dict[str, any]],
        authors2: List[Dict[str, any]]
    ) -> List[str]:
        """
        Find authors that appear in both paper author lists.
        
        Handles name variations:
        - "Smith J" = "Smith JA" = "J Smith" = "Smith, John"
        
        Args:
            authors1: List of author dicts from paper 1 ({'name': 'Smith J', ...})
            authors2: List of author dicts from paper 2
        
        Returns:
            List of shared author names (in normalized format)
        """
        # Normalize all names
        names1 = {self._normalize_name(a['name']): a['name'] for a in authors1}
        names2 = {self._normalize_name(a['name']): a['name'] for a in authors2}
        
        # Find intersection
        shared_normalized = set(names1.keys()) & set(names2.keys())
        
        # Return original names
        return [names1[norm] for norm in shared_normalized]
    
    def is_self_citation(
        self,
        citing_authors: List[Dict[str, any]],
        reference_authors: List[Dict[str, any]]
    ) -> Tuple[bool, List[str]]:
        """
        Check if this is a self-citation (any shared authors).
        
        Returns:
            Tuple of (is_self_citation: bool, shared_authors: List[str])
        """
        shared = self.find_shared_authors(citing_authors, reference_authors)
        return len(shared) > 0, shared
    
    def is_senior_author_self_citation(
        self,
        citing_authors: List[Dict[str, any]],
        reference_authors: List[Dict[str, any]]
    ) -> bool:
        """
        Check if the last author (typically senior author) is the same.
        
        This is a particularly strong indicator of self-citation bias.
        
        Returns:
            True if last author is the same in both papers
        """
        if not citing_authors or not reference_authors:
            return False
        
        last_citing = self._normalize_name(citing_authors[-1]['name'])
        last_reference = self._normalize_name(reference_authors[-1]['name'])
        
        return last_citing == last_reference
    
    def find_shared_affiliations(
        self,
        authors1: List[Dict[str, any]],
        authors2: List[Dict[str, any]]
    ) -> List[str]:
        """
        Find shared institutional affiliations between two papers.
        
        Uses fuzzy matching to handle variations:
        - "Harvard Medical School" = "Harvard Med Sch" = "HMS"
        
        Args:
            authors1: List of author dicts with 'affiliations' field
            authors2: List of author dicts with 'affiliations' field
        
        Returns:
            List of shared affiliations (deduplicated)
        """
        # Collect all affiliations from both papers
        affs1 = set()
        for author in authors1:
            for aff in author.get('affiliations', []):
                affs1.add(aff)
        
        affs2 = set()
        for author in authors2:
            for aff in author.get('affiliations', []):
                affs2.add(aff)
        
        # Find fuzzy matches
        shared = []
        for aff1 in affs1:
            for aff2 in affs2:
                if self._affiliations_match(aff1, aff2):
                    # Use the longer, more detailed version
                    shared_aff = aff1 if len(aff1) >= len(aff2) else aff2
                    if shared_aff not in shared:
                        shared.append(shared_aff)
        
        return shared
    
    def is_same_institution(
        self,
        citing_authors: List[Dict[str, any]],
        reference_authors: List[Dict[str, any]]
    ) -> Tuple[bool, List[str]]:
        """
        Check if papers are from the same institution(s).
        
        Returns:
            Tuple of (is_same_institution: bool, shared_affiliations: List[str])
        """
        shared = self.find_shared_affiliations(citing_authors, reference_authors)
        return len(shared) > 0, shared
    
    def calculate_citation_age(
        self,
        citing_pub_date: str,
        reference_pub_date: str
    ) -> float:
        """
        Calculate the age of the citation in years.
        
        Args:
            citing_pub_date: Publication date of citing paper (ISO format or year)
            reference_pub_date: Publication date of reference paper
        
        Returns:
            Age in years (float)
        """
        try:
            # Extract years
            citing_year = self._extract_year(citing_pub_date)
            reference_year = self._extract_year(reference_pub_date)
            
            if citing_year and reference_year:
                return float(citing_year - reference_year)
            
            return 0.0
            
        except Exception as e:
            self.logger.warning(f"Failed to calculate citation age: {e}")
            return 0.0
    
    # Helper methods
    
    def _normalize_name(self, name: str) -> str:
        """
        Normalize author name for matching.
        
        Examples:
        - "Smith, John" → "smith j"
        - "Smith JA" → "smith ja"
        - "J Smith" → "smith j"
        """
        # Remove common punctuation
        name = name.replace(',', '').replace('.', '')
        
        # Split into parts
        parts = name.lower().split()
        
        if len(parts) < 2:
            return name.lower().strip()
        
        # Assume format is either "Surname Initials" or "Initials Surname"
        # Check if first part looks like initials (short, all caps)
        if len(parts[0]) <= 3 and parts[0].replace('.', '').isupper():
            # "J Smith" format → "smith j"
            surname = parts[-1]
            initials = ''.join(p.replace('.', '') for p in parts[:-1])
            return f"{surname} {initials}".lower()
        else:
            # "Smith J" or "Smith JA" format
            surname = parts[0]
            initials = ''.join(p.replace('.', '') for p in parts[1:])
            return f"{surname} {initials}".lower()
    
    def _affiliations_match(self, aff1: str, aff2: str) -> bool:
        """
        Check if two affiliations are likely the same using fuzzy matching.
        
        Examples that should match:
        - "Harvard Medical School" ↔ "Harvard Med Sch"
        - "Stanford University" ↔ "Stanford Univ"
        - "MIT" ↔ "Massachusetts Institute of Technology"
        """
        # Exact match
        if aff1 == aff2:
            return True
        
        # Normalize
        aff1_norm = aff1.lower().strip()
        aff2_norm = aff2.lower().strip()
        
        # Check if one is a substring of the other
        if aff1_norm in aff2_norm or aff2_norm in aff1_norm:
            return True
        
        # Fuzzy string matching
        similarity = SequenceMatcher(None, aff1_norm, aff2_norm).ratio()
        
        return similarity >= self.affiliation_threshold
    
    def _extract_year(self, date_string: str) -> Optional[int]:
        """Extract year from a date string."""
        if not date_string:
            return None
        
        # If it's already just a year
        if len(date_string) == 4 and date_string.isdigit():
            return int(date_string)
        
        # Try to extract year from ISO format (YYYY-MM-DD)
        if '-' in date_string:
            return int(date_string.split('-')[0])
        
        # Try to find any 4-digit number (likely a year)
        import re
        match = re.search(r'\b(19|20)\d{2}\b', date_string)
        if match:
            return int(match.group())
        
        return None
