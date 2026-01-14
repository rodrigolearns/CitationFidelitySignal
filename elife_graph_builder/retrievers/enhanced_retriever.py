"""
Enhanced evidence retriever for second-round classification.

Provides expanded evidence with section awareness and full abstracts.
"""

import logging
from typing import List, Tuple, Optional, Dict
from lxml import etree
import numpy as np

from ..models import EnhancedEvidenceSegment
from .bm25_retriever import BM25Retriever
from .semantic_retriever import SemanticRetriever

logger = logging.getLogger(__name__)


# Section weights for prioritization
SECTION_WEIGHTS = {
    "Methods": 0.40,
    "Results": 0.40,
    "Discussion": 0.15,
    "Introduction": 0.05,
    "Abstract": 0.00,  # Provided separately
    "Materials and Methods": 0.40,
    "Results and Discussion": 0.35,
    "Conclusion": 0.10,
    "Background": 0.05,
}


class EnhancedEvidenceRetriever:
    """
    Retrieves expanded evidence for second-round classification.
    
    Features:
    - Extracts full abstract
    - Retrieves top 15 evidence segments (vs. 5 in first round)
    - Lower similarity threshold (0.5 vs. 0.7)
    - Section-aware with prioritization
    - Includes full paragraph context
    """
    
    def __init__(self):
        """Initialize retrievers."""
        self.bm25 = BM25Retriever()
        self.semantic = SemanticRetriever()
        logger.info("EnhancedEvidenceRetriever initialized")
    
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
            logger.info(f"Extracted abstract: {len(abstract_text)} characters")
            return abstract_text
            
        except Exception as e:
            logger.error(f"Error extracting abstract: {e}")
            return ""
    
    def _get_section_weight(self, section: str) -> float:
        """Get priority weight for a section."""
        # Try exact match first
        if section in SECTION_WEIGHTS:
            return SECTION_WEIGHTS[section]
        
        # Try partial match
        section_lower = section.lower()
        for key, weight in SECTION_WEIGHTS.items():
            if key.lower() in section_lower:
                return weight
        
        # Default weight for unknown sections
        return 0.05
    
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
            
            logger.info(f"Extracted {len(paragraphs)} paragraphs with section labels")
            return paragraphs
            
        except Exception as e:
            logger.error(f"Error extracting paragraphs with sections: {e}")
            return []
    
    def _categorize_section(self, title: str) -> str:
        """
        Categorize a section title into standard categories.
        
        Args:
            title: Section title text
            
        Returns:
            Standardized section name
        """
        title_lower = title.lower()
        
        if any(kw in title_lower for kw in ['method', 'material', 'experimental']):
            return "Methods"
        elif any(kw in title_lower for kw in ['result', 'finding']):
            return "Results"
        elif any(kw in title_lower for kw in ['discussion', 'conclusion']):
            return "Discussion"
        elif any(kw in title_lower for kw in ['introduction', 'background']):
            return "Introduction"
        else:
            # Return original title if can't categorize
            return title
    
    def retrieve_with_abstract(
        self,
        citation_context: str,
        reference_xml: str,
        top_n: int = 15,
        min_similarity: float = 0.5
    ) -> Tuple[str, List[EnhancedEvidenceSegment]]:
        """
        Retrieve enhanced evidence with abstract and section awareness.
        
        Args:
            citation_context: The citation context text to match
            reference_xml: Full XML of the reference article
            top_n: Number of evidence segments to return (default 15)
            min_similarity: Minimum similarity threshold (default 0.5)
            
        Returns:
            Tuple of (abstract_text, enhanced_evidence_segments)
        """
        logger.info(f"Retrieving enhanced evidence (top_n={top_n}, threshold={min_similarity})")
        
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
        
        # 4. Get BM25 candidates (top 30 for re-ranking)
        bm25_candidates = self.bm25.search(citation_context, top_n=30)
        
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
        
        # 6. Create enhanced segments with section info and apply section weighting
        enhanced_segments = []
        for i, (cand, sim) in enumerate(zip(bm25_candidates, similarities)):
            if sim >= min_similarity:
                para_text, section, section_title = paragraphs_with_sections[cand.index]
                
                # Apply section weight to similarity score
                section_weight = self._get_section_weight(section)
                weighted_sim = sim * (0.7 + (section_weight * 0.3))  # 70% base, 30% section bonus
                
                segment = EnhancedEvidenceSegment(
                    section=section,
                    section_title=section_title,
                    text=para_text[:500],  # Limit to 500 chars per segment
                    paragraph_context=para_text,  # Full paragraph
                    similarity_score=weighted_sim,
                    retrieval_method="hybrid_enhanced",
                    paragraph_index=cand.index
                )
                enhanced_segments.append((weighted_sim, segment))
        
        # 7. Sort by weighted similarity and take top_n
        enhanced_segments.sort(key=lambda x: x[0], reverse=True)
        final_segments = [seg for _, seg in enhanced_segments[:top_n]]
        
        logger.info(
            f"Retrieved {len(final_segments)} enhanced evidence segments "
            f"(abstract: {len(abstract)} chars)"
        )
        
        return abstract, final_segments
    
    def build_index_from_paragraphs(self, paragraphs: List[str]) -> int:
        """Helper to build BM25 index from paragraph list."""
        return self.bm25.build_index_from_paragraphs(paragraphs)
    
    def assess_evidence_quality(
        self,
        evidence_segments: List[EnhancedEvidenceSegment],
        citation_context: str
    ) -> Dict:
        """
        Assess the quality of retrieved evidence segments.
        
        Args:
            evidence_segments: List of enhanced evidence segments
            citation_context: Original citation context
            
        Returns:
            Dictionary with quality metrics
        """
        if not evidence_segments:
            return {
                'average_similarity': 0.0,
                'min_similarity': 0.0,
                'max_similarity': 0.0,
                'section_diversity': 0,
                'quality_score': 0.0,
                'confidence_level': 'VERY_LOW'
            }
        
        # Calculate similarity statistics
        similarities = [seg.similarity_score for seg in evidence_segments]
        avg_similarity = sum(similarities) / len(similarities)
        min_similarity = min(similarities)
        max_similarity = max(similarities)
        
        # Section diversity (how many unique sections)
        unique_sections = len(set(seg.section for seg in evidence_segments))
        
        # Check for high-priority sections (Methods, Results)
        high_priority_count = sum(
            1 for seg in evidence_segments 
            if seg.section in ["Methods", "Results", "Materials and Methods"]
        )
        
        # Detect potential contradictions by checking semantic similarity between segments
        contradiction_score = self._detect_contradictions(evidence_segments)
        
        # Compute overall quality score (0-1)
        quality_score = self._compute_quality_score(
            avg_similarity=avg_similarity,
            min_similarity=min_similarity,
            section_diversity=unique_sections,
            high_priority_count=high_priority_count,
            contradiction_score=contradiction_score,
            total_segments=len(evidence_segments)
        )
        
        # Determine confidence level
        if quality_score >= 0.8:
            confidence_level = "HIGH"
        elif quality_score >= 0.6:
            confidence_level = "MEDIUM"
        elif quality_score >= 0.4:
            confidence_level = "LOW"
        else:
            confidence_level = "VERY_LOW"
        
        return {
            'average_similarity': round(avg_similarity, 3),
            'min_similarity': round(min_similarity, 3),
            'max_similarity': round(max_similarity, 3),
            'section_diversity': unique_sections,
            'high_priority_segments': high_priority_count,
            'contradiction_score': round(contradiction_score, 3),
            'quality_score': round(quality_score, 3),
            'confidence_level': confidence_level
        }
    
    def _detect_contradictions(
        self, 
        evidence_segments: List[EnhancedEvidenceSegment]
    ) -> float:
        """
        Detect potential contradictions between evidence segments.
        
        Returns a score from 0 (no contradictions) to 1 (high contradictions).
        
        Args:
            evidence_segments: List of evidence segments
            
        Returns:
            Contradiction score (0-1)
        """
        if len(evidence_segments) < 2:
            return 0.0
        
        try:
            # Embed all segments
            segment_texts = [seg.text for seg in evidence_segments]
            embeddings = self.semantic.embed_batch(segment_texts)
            
            # Compute pairwise similarities
            similarities = []
            for i in range(len(embeddings)):
                for j in range(i + 1, len(embeddings)):
                    sim = self.semantic.compute_similarity(embeddings[i], embeddings[j])
                    similarities.append(sim)
            
            if not similarities:
                return 0.0
            
            # Low inter-segment similarity suggests potential contradiction or inconsistency
            avg_inter_similarity = sum(similarities) / len(similarities)
            
            # Convert to contradiction score (inverse relationship)
            # High similarity (0.8+) = low contradiction
            # Low similarity (0.3-) = high contradiction
            if avg_inter_similarity >= 0.7:
                contradiction_score = 0.0  # Segments agree
            elif avg_inter_similarity >= 0.5:
                contradiction_score = 0.3  # Moderate consistency
            elif avg_inter_similarity >= 0.3:
                contradiction_score = 0.6  # Potential inconsistency
            else:
                contradiction_score = 0.9  # High contradiction
            
            return contradiction_score
            
        except Exception as e:
            logger.error(f"Error detecting contradictions: {e}")
            return 0.0
    
    def _compute_quality_score(
        self,
        avg_similarity: float,
        min_similarity: float,
        section_diversity: int,
        high_priority_count: int,
        contradiction_score: float,
        total_segments: int
    ) -> float:
        """
        Compute overall evidence quality score (0-1).
        
        Args:
            avg_similarity: Average similarity score
            min_similarity: Minimum similarity score
            section_diversity: Number of unique sections
            high_priority_count: Number of segments from Methods/Results
            contradiction_score: Contradiction score (0-1)
            total_segments: Total number of segments
            
        Returns:
            Quality score (0-1)
        """
        # Component weights
        weights = {
            'avg_similarity': 0.35,
            'min_similarity': 0.15,
            'section_diversity': 0.20,
            'high_priority': 0.20,
            'contradiction': 0.10
        }
        
        # Normalize components
        similarity_score = avg_similarity  # Already 0-1
        min_score = min_similarity  # Already 0-1
        
        # Section diversity (3+ unique sections is ideal)
        diversity_score = min(section_diversity / 3.0, 1.0)
        
        # High priority sections (40% of segments is good)
        priority_ratio = high_priority_count / total_segments if total_segments > 0 else 0
        priority_score = min(priority_ratio / 0.4, 1.0)
        
        # Contradiction (inverse - low contradiction is good)
        consistency_score = 1.0 - contradiction_score
        
        # Weighted sum
        quality = (
            weights['avg_similarity'] * similarity_score +
            weights['min_similarity'] * min_score +
            weights['section_diversity'] * diversity_score +
            weights['high_priority'] * priority_score +
            weights['contradiction'] * consistency_score
        )
        
        return quality
