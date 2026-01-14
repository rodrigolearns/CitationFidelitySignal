"""
Type-aware evidence retriever for second-round classification.

Applies citation type-specific section prioritization to retrieve more relevant evidence.
"""

import logging
from typing import List, Tuple, Dict, Optional
from lxml import etree

from ..models import EnhancedEvidenceSegment
from .bm25_retriever import BM25Retriever
from .semantic_retriever import SemanticRetriever

logger = logging.getLogger(__name__)


# Type-aware section weights
# Higher weight = more important for that citation type
TYPE_AWARE_SECTION_WEIGHTS = {
    "METHODOLOGICAL": {
        # Data sources, protocols, methods
        "Materials and methods": 3.5,
        "Materials and Methods": 3.5,
        "Methods": 3.5,
        "Experimental procedures": 3.5,
        "Results": 2.0,  # For data characteristics (sample sizes, measurements)
        "Abstract": 1.5,
        "Introduction": 0.3,
        "Background": 0.3,
        "Discussion": 0.3,  # Heavily downweight - conceptual, not methodological
        "Conclusions": 0.2,
        "Conclusion": 0.2
    },
    
    "CONCEPTUAL": {
        # Findings, conclusions, interpretations
        "Results": 3.0,
        "Discussion": 3.0,  # Where caveats and interpretations live
        "Abstract": 2.5,
        "Conclusions": 2.0,
        "Conclusion": 2.0,
        "Introduction": 1.0,
        "Background": 0.8,
        "Methods": 0.4,  # Downweight - usually not where claims are supported
        "Materials and methods": 0.4,
        "Materials and Methods": 0.4,
        "Experimental procedures": 0.4
    },
    
    "BACKGROUND": {
        # Field context, exploratory work
        "Abstract": 3.5,
        "Introduction": 3.0,
        "Background": 3.0,
        "Discussion": 1.5,
        "Conclusions": 1.2,
        "Results": 0.5,
        "Methods": 0.2,
        "Materials and methods": 0.2,
        "Materials and Methods": 0.2
    },
    
    "ATTRIBUTION": {
        # Original discoveries, inventions
        "Abstract": 3.0,
        "Results": 2.5,
        "Introduction": 2.0,
        "Discussion": 1.5,
        "Methods": 1.0,
        "Materials and methods": 1.0,
        "Materials and Methods": 1.0,
        "Conclusions": 1.5
    },
    
    "UNKNOWN": {
        # Fallback - equal weights (like standard retrieval)
        # Will be populated dynamically
    }
}


# Section name aliases for normalization
SECTION_ALIASES = {
    "methods": ["Methods", "Materials and methods", "Materials and Methods", 
                "Experimental procedures", "Materials & Methods"],
    "results": ["Results", "Results and discussion", "Results and Discussion"],
    "discussion": ["Discussion", "Results and discussion", "Results and Discussion"],
    "introduction": ["Introduction", "Background"],
    "conclusions": ["Conclusions", "Conclusion", "Concluding remarks"]
}


class TypeAwareEnhancedRetriever:
    """
    Enhanced evidence retriever with citation type-aware section prioritization.
    
    Uses the citation type detected in Workflow 2 to apply appropriate section weights,
    ensuring the LLM receives evidence from the most relevant sections.
    
    Example:
        - METHODOLOGICAL citations prioritize Methods and Results sections
        - CONCEPTUAL citations prioritize Results and Discussion sections
        - BACKGROUND citations prioritize Abstract and Introduction sections
    """
    
    def __init__(self):
        """Initialize retrievers."""
        self.bm25 = BM25Retriever()
        self.semantic = SemanticRetriever()
        self.section_weights = TYPE_AWARE_SECTION_WEIGHTS
        logger.info("TypeAwareEnhancedRetriever initialized")
    
    def extract_abstract(self, xml_content: str) -> str:
        """
        Extract the full abstract from a JATS XML article.
        
        Args:
            xml_content: Raw XML string
            
        Returns:
            Formatted abstract text, or empty string if not found
        """
        try:
            root = etree.fromstring(xml_content.encode('utf-8'))
            
            # Find abstract element
            abstract = root.find('.//abstract')
            if abstract is None:
                logger.warning("No <abstract> element found")
                return ""
            
            # Extract all text from abstract, preserving paragraph structure
            paragraphs = []
            for p in abstract.findall('.//p'):
                text = ''.join(p.itertext()).strip()
                if text:
                    paragraphs.append(text)
            
            # If no <p> tags, just get all text
            if not paragraphs:
                text = ''.join(abstract.itertext()).strip()
                if text:
                    paragraphs = [text]
            
            abstract_text = "\n\n".join(paragraphs)
            logger.debug(f"Extracted abstract: {len(abstract_text)} characters")
            return abstract_text
            
        except Exception as e:
            logger.error(f"Error extracting abstract: {e}")
            return ""
    
    def _normalize_section_name(self, section: str) -> str:
        """
        Normalize section names to standard categories.
        
        Args:
            section: Raw section name
            
        Returns:
            Normalized section name
        """
        section_lower = section.lower()
        
        # Check aliases
        for canonical, aliases in SECTION_ALIASES.items():
            if any(alias.lower() == section_lower for alias in aliases):
                return aliases[0]  # Return first (canonical) name
        
        # Return original if no match
        return section
    
    def _get_section_weight(self, section: str, citation_type: str) -> float:
        """
        Get priority weight for a section based on citation type.
        
        Args:
            section: Section name
            citation_type: Type of citation (METHODOLOGICAL, CONCEPTUAL, etc.)
            
        Returns:
            Weight multiplier (higher = more important)
        """
        # Get weights for this citation type
        if citation_type not in self.section_weights:
            logger.warning(f"Unknown citation_type: {citation_type}, using default weights")
            citation_type = "UNKNOWN"
        
        weights = self.section_weights[citation_type]
        
        # For UNKNOWN type, return 1.0 for all sections
        if citation_type == "UNKNOWN":
            return 1.0
        
        # Try exact match first
        if section in weights:
            return weights[section]
        
        # Try normalized match
        normalized = self._normalize_section_name(section)
        if normalized in weights:
            return weights[normalized]
        
        # Try partial match (case-insensitive)
        section_lower = section.lower()
        for key, weight in weights.items():
            if key.lower() in section_lower or section_lower in key.lower():
                return weight
        
        # Default weight for unknown sections (low but not zero)
        return 0.5
    
    def _categorize_section(self, title: str) -> str:
        """
        Categorize a section title into standard categories.
        
        Args:
            title: Section title text
            
        Returns:
            Standardized section name
        """
        title_lower = title.lower()
        
        # Methods keywords (including subsection indicators)
        if any(kw in title_lower for kw in [
            'method', 'material', 'experimental', 'procedure',
            'genotyp', 'imputation', 'sequencing', 'quantification',
            'assay', 'collection', 'analysis', 'metric', 'protocol'
        ]):
            return "Methods"
        # Results keywords
        elif any(kw in title_lower for kw in ['result', 'finding', 'association']):
            return "Results"
        # Discussion keywords
        elif any(kw in title_lower for kw in ['discussion', 'conclusion']):
            return "Discussion"
        # Introduction keywords
        elif any(kw in title_lower for kw in ['introduction', 'background']):
            return "Introduction"
        else:
            # Return original title if can't categorize
            return title
    
    def _extract_paragraphs_with_sections(
        self, 
        xml_content: str
    ) -> List[Tuple[str, str, str]]:
        """
        Extract paragraphs with section metadata.
        
        Args:
            xml_content: Raw XML string
            
        Returns:
            List of (paragraph_text, section, section_title) tuples
        """
        try:
            root = etree.fromstring(xml_content.encode('utf-8'))
            body = root.find('.//body')
            
            if body is None:
                logger.warning("No <body> element found")
                return []
            
            paragraphs = []
            current_section = "Unknown"
            current_section_title = None
            
            # Walk through body elements
            for elem in body.iter():
                # Check if this is a section element
                if elem.tag == 'sec':
                    # Try to find the section title
                    title_elem = elem.find('./title')
                    if title_elem is not None:
                        title_text = ''.join(title_elem.itertext()).strip()
                        current_section = self._categorize_section(title_text)
                        current_section_title = title_text
                
                # Check if this is a paragraph
                elif elem.tag == 'p':
                    text = ''.join(elem.itertext()).strip()
                    if text and len(text) > 50:  # Skip very short paragraphs
                        paragraphs.append((text, current_section, current_section_title))
            
            logger.debug(f"Extracted {len(paragraphs)} paragraphs with section labels")
            return paragraphs
            
        except Exception as e:
            logger.error(f"Error extracting paragraphs with sections: {e}")
            return []
    
    def retrieve_with_abstract(
        self,
        citation_context: str,
        reference_xml: str,
        citation_type: str,
        top_n: int = 15,
        min_similarity: float = 0.5
    ) -> Tuple[str, List[EnhancedEvidenceSegment]]:
        """
        Retrieve enhanced evidence with type-aware section prioritization.
        
        Strategy:
        1. Retrieve top_n * 3 candidates using hybrid search
        2. Apply section weights based on citation_type
        3. Re-rank: adjusted_score = similarity * section_weight
        4. Return top_n after re-ranking
        
        Args:
            citation_context: The citation context text to match
            reference_xml: Full XML of the reference article
            citation_type: Type of citation (METHODOLOGICAL, CONCEPTUAL, etc.)
            top_n: Number of evidence segments to return (default 15)
            min_similarity: Minimum similarity threshold (default 0.5)
            
        Returns:
            Tuple of (abstract_text, enhanced_evidence_segments)
        """
        logger.info(
            f"Type-aware retrieval for {citation_type} citation "
            f"(top_n={top_n}, threshold={min_similarity})"
        )
        
        # 1. Extract abstract
        abstract = self.extract_abstract(reference_xml)
        
        # 2. Extract paragraphs with section labels
        paragraphs_with_sections = self._extract_paragraphs_with_sections(reference_xml)
        
        if not paragraphs_with_sections:
            logger.warning("No paragraphs found in reference article")
            return abstract, []
        
        # 3. Build BM25 index from paragraphs
        paragraph_texts = [p[0] for p in paragraphs_with_sections]
        num_paragraphs = self.bm25.build_index_from_paragraphs(paragraph_texts)
        
        if num_paragraphs == 0 or self.bm25.bm25 is None:
            logger.warning("BM25 index build failed")
            return abstract, []
        
        # 4. Get BM25 candidates (retrieve more for better re-ranking)
        candidate_count = min(top_n * 3, len(paragraph_texts))  # Get 3x candidates
        bm25_candidates = self.bm25.search(citation_context, top_n=candidate_count)
        
        if not bm25_candidates:
            logger.warning("No BM25 candidates found")
            return abstract, []
        
        # 5. Compute semantic similarity for candidates
        candidate_texts = [
            paragraphs_with_sections[cand.index][0] 
            for cand in bm25_candidates
        ]
        
        # Embed query and candidates
        query_embedding = self.semantic.embed_text(citation_context)
        candidate_embeddings = self.semantic.embed_batch(candidate_texts)
        
        # Compute similarities
        similarities = []
        for cand_emb in candidate_embeddings:
            sim = self.semantic.compute_similarity(query_embedding, cand_emb)
            similarities.append(sim)
        
        # 6. Apply type-aware section weighting and create enhanced segments
        enhanced_segments = []
        section_counts = {}
        
        for i, (cand, sim) in enumerate(zip(bm25_candidates, similarities)):
            # Use lower threshold for candidates (will be filtered after re-ranking)
            if sim >= min_similarity * 0.7:
                para_text, section, section_title = paragraphs_with_sections[cand.index]
                
                # Get type-aware section weight
                section_weight = self._get_section_weight(section, citation_type)
                
                # Calculate adjusted score: similarity * section_weight
                # This is the KEY innovation - sections prioritized by type get boosted
                adjusted_score = sim * section_weight
                
                # Track section distribution
                section_counts[section] = section_counts.get(section, 0) + 1
                
                # Log significant adjustments
                if section_weight >= 2.5:
                    logger.debug(
                        f"Boosted {section}: sim={sim:.2f} → adjusted={adjusted_score:.2f} "
                        f"(weight={section_weight:.1f}x)"
                    )
                elif section_weight <= 0.5:
                    logger.debug(
                        f"Downweighted {section}: sim={sim:.2f} → adjusted={adjusted_score:.2f} "
                        f"(weight={section_weight:.1f}x)"
                    )
                
                segment = EnhancedEvidenceSegment(
                    section=section,
                    section_title=section_title,
                    text=para_text[:500],  # Limit to 500 chars for display
                    paragraph_context=para_text,  # Full paragraph for context
                    similarity_score=adjusted_score,  # Store adjusted score
                    retrieval_method=f"type_aware_{citation_type.lower()}",
                    paragraph_index=cand.index
                )
                enhanced_segments.append((adjusted_score, segment))
        
        # 7. Sort by adjusted score and take top_n
        enhanced_segments.sort(key=lambda x: x[0], reverse=True)
        final_segments = [seg for _, seg in enhanced_segments[:top_n]]
        
        # Log section distribution in final selection
        final_section_counts = {}
        for seg in final_segments:
            final_section_counts[seg.section] = final_section_counts.get(seg.section, 0) + 1
        
        logger.info(
            f"Retrieved {len(final_segments)} type-aware evidence segments "
            f"for {citation_type}"
        )
        logger.info(f"Section distribution: {dict(final_section_counts)}")
        
        # Check if we met minimum coverage expectations
        self._check_coverage(final_segments, citation_type)
        
        return abstract, final_segments
    
    def _check_coverage(
        self,
        segments: List[EnhancedEvidenceSegment],
        citation_type: str
    ) -> None:
        """
        Check if we have minimum coverage of critical sections.
        Logs warnings if coverage is insufficient.
        
        Args:
            segments: Final selected segments
            citation_type: Type of citation
        """
        if not segments:
            return
        
        section_counts = {}
        for seg in segments:
            normalized = self._normalize_section_name(seg.section)
            section_counts[normalized] = section_counts.get(normalized, 0) + 1
        
        # Define minimum coverage requirements
        if citation_type == "METHODOLOGICAL":
            methods_count = section_counts.get("Methods", 0)
            if methods_count < 2:
                logger.warning(
                    f"Low Methods coverage for METHODOLOGICAL citation: "
                    f"{methods_count} segments (expected ≥2)"
                )
        
        elif citation_type == "CONCEPTUAL":
            results_count = section_counts.get("Results", 0)
            discussion_count = section_counts.get("Discussion", 0)
            if results_count < 1 or discussion_count < 1:
                logger.warning(
                    f"Low Results/Discussion coverage for CONCEPTUAL citation: "
                    f"Results={results_count}, Discussion={discussion_count} "
                    f"(expected ≥1 each)"
                )
