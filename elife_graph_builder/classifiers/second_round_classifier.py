"""
Second-round LLM classifier for in-depth citation fidelity verification.

Uses DeepSeek Reasoner (thinking mode) with expanded evidence to confirm or correct 
first-round classifications.
"""

import json
import logging
import os
from typing import Dict, List, Optional
from datetime import datetime

from openai import OpenAI

from ..models import SecondRoundClassification, EnhancedEvidenceSegment
from ..config import Config

logger = logging.getLogger(__name__)


SECOND_ROUND_PROMPT_TEMPLATE = """You are evaluating the accuracy of a scientific citation. This is a SECOND-ROUND verification with expanded evidence.

FIRST-ROUND CLASSIFICATION:
- Category: {first_round_category}
- Confidence: {first_round_confidence:.2f}
- Justification: {first_round_justification}

CITATION CONTEXT (from citing paper):
Section: {section}
Text: {citation_context}
Reference: {reference_citation}

REFERENCE ARTICLE ABSTRACT:
{abstract_text}

EVIDENCE SEGMENTS FROM REFERENCE ARTICLE:
{formatted_evidence}

IMPORTANT: CITATION TYPE DETECTION

Before evaluating, identify the citation type, as different types have different evaluation criteria:

1. METHODOLOGICAL CITATION - Cites data sources, methods, or protocols
   Examples:
   - "We meta-analyzed four datasets (A, B, C, D)" ← Each cited paper is a data source
   - "We used the protocol from Smith et al."
   - "Summary statistics were obtained from Jones et al."
   
   Evaluation criteria:
   ✓ Does the reference provide the data/method mentioned?
   ✗ NOT required: Supporting the broader research question
   ✗ NOT required: Discussing meta-analysis, sample sizes, or study design concepts
   
   CRITICAL: If the first round flagged this as NOT_SUBSTANTIATE because "the reference
   doesn't discuss sample size effects" or "doesn't address the research question" -
   this may be INCORRECT for methodological citations. The reference only needs to have
   PROVIDED THE DATA, not support the conceptual framework.

2. CONCEPTUAL CITATION - Makes claims about findings or conclusions
   Examples:
   - "Studies show X causes Y (Smith et al.)"
   - "This finding is supported by Jones et al."
   
   Evaluation criteria:
   ✓ Does the reference support this specific claim?
   ✓ Check for oversimplification, missing nuance, or conditional findings

3. BACKGROUND CITATION - Lists studies that explored a topic
   Evaluation: Did the reference explore/investigate the topic mentioned?

4. ATTRIBUTION CITATION - Credits original discovery
   Evaluation: Is this the correct attribution?

YOUR TASK:
Evaluate this citation systematically using the expanded evidence to confirm or correct the first-round classification.

SYSTEMATIC EVALUATION STEPS:

STEP 1: CITATION TYPE IDENTIFICATION
Determine: METHODOLOGICAL, CONCEPTUAL, BACKGROUND, or ATTRIBUTION
This fundamentally changes what evidence you need to look for.
For METHODOLOGICAL: Only verify data/method exists, don't evaluate conceptual support.

STEP 2: ABSTRACT ANALYSIS
Does the abstract support the general claim? What is the paper's main finding?
For METHODOLOGICAL citations: Does it indicate the data/method was generated?
For CONCEPTUAL citations: Does it support the claim being made?

STEP 3: METHODS VERIFICATION
Do the methods sections explain how the data was collected/analyzed to support the claim?
For METHODOLOGICAL citations: This is the PRIMARY section to verify.

STEP 4: RESULTS VERIFICATION
Do the results sections provide direct evidence for the specific claim made in the citation?
For METHODOLOGICAL data source citations: Verify sample sizes/data exist.

STEP 5: DISCUSSION CONTEXT
Does the discussion provide nuances, caveats, or limitations that the citation omits?
LESS RELEVANT for pure METHODOLOGICAL citations.

STEP 6: EVIDENCE CONSISTENCY
Do the evidence segments agree with each other, or do they contradict?

STEP 7: FIRST-ROUND ASSESSMENT
Was the first-round classification correct based on this deeper evidence?
CRITICAL: If first round was NOT_SUBSTANTIATE for a METHODOLOGICAL citation,
check if the LLM incorrectly expected conceptual support rather than just data provision.

CLASSIFICATION CATEGORIES:
- SUPPORT: Reference substantiates the citation claim
- CONTRADICT: Reference contradicts the citation claim
- NOT_SUBSTANTIATE: Reference doesn't provide evidence for the specific claim
- OVERSIMPLIFY: Citation oversimplifies nuanced/conditional findings
- IRRELEVANT: Evidence unrelated to the citation claim
- MISQUOTE: Citation misquotes or misattributes findings
- INDIRECT: Citation treats secondary source as primary
- ETIQUETTE: Courtesy citation without substantive support

CONFIDENCE CALIBRATION:
- 0.9-1.0: Evidence is clear and unambiguous
- 0.7-0.9: Evidence strongly suggests this classification
- 0.5-0.7: Evidence moderately supports this classification
- 0.3-0.5: Evidence is weak or contradictory
- 0.0-0.3: Cannot determine with available evidence

Return JSON with this exact structure:
{{
  "citation_type": "METHODOLOGICAL | CONCEPTUAL | BACKGROUND | ATTRIBUTION",
  "category": "...",
  "confidence": 0.0-1.0,
  "determination": "CONFIRMED or CORRECTED",
  "detailed_explanation": "Write a comprehensive 150-250 word explanation for researchers, explaining your decision in eloquent, accessible language. Structure: (1) What the citing paper claims about the reference, (2) What the reference actually says/provides (cite specific sections/findings), (3) Why this led to your classification decision, (4) Any important nuances or context. Be specific and reference concrete evidence. For CORRECTED determinations, clearly explain why the first-round was wrong. For CONFIRMED issues, explain the specific nature of the problem (e.g., 'The citing paper claims X causes Y, but the reference only shows correlation, not causation').",
  "justification": "Technical 250+ word analysis for system debugging. START with citation type identification and why it matters. For METHODOLOGICAL citations flagged as NOT_SUBSTANTIATE, explicitly state whether the LLM incorrectly expected conceptual support when only data provision was needed. Then explain your determination step-by-step, referencing specific evidence segments by number.",
  "user_overview": "1 sentence verdict. Examples: 'Valid methodological citation - reference provided the claimed data.' OR 'Citation overstates findings - reference shows correlation, not causation.' OR 'Accurate representation of the reference's conclusions.'",
  "key_findings": ["List 2-4 bullet points highlighting the most important evidence", "For METHODOLOGICAL: Focus on whether data/method was provided", "For CONCEPTUAL: Focus on whether findings support the claim"],
  "recommendation": "ACCURATE (citation correctly represents the reference) | NEEDS_REVIEW (citation has issues but may be contextually acceptable) | MISREPRESENTATION (citation significantly misrepresents the reference)"
}}"""


class SecondRoundClassifier:
    """
    LLM-based classifier for in-depth citation verification.
    
    Uses GPT-4o with expanded evidence (abstract + 15 segments) to perform
    second-round classification of citations flagged as suspicious.
    """
    
    def __init__(self, model: Optional[str] = None, provider: Optional[str] = None):
        """
        Initialize classifier.
        
        Args:
            model: Model to use (defaults based on provider)
            provider: "deepseek" or "openai" (defaults to env var or deepseek)
        """
        self.provider = provider or os.getenv('LLM_PROVIDER', 'deepseek')
        
        if self.provider == 'deepseek':
            api_key = Config.DEEPSEEK_API_KEY
        if not api_key:
                raise ValueError("DEEPSEEK_API_KEY environment variable not set")
            # Use thinking mode for in-depth analysis
            self.model = model or 'deepseek-reasoner'
            self.client = OpenAI(
                api_key=api_key,
                base_url=Config.DEEPSEEK_BASE_URL
            )
        else:  # openai
            api_key = Config.OPENAI_API_KEY
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        self.client = OpenAI(api_key=api_key)
        
        logger.info(f"SecondRoundClassifier initialized with {self.provider.upper()}: {self.model}")
    
    def _format_evidence_list(
        self, 
        evidence_segments: List[EnhancedEvidenceSegment]
    ) -> str:
        """
        Format evidence segments for the prompt.
        
        Args:
            evidence_segments: List of enhanced evidence segments
            
        Returns:
            Formatted string for prompt
        """
        formatted = []
        for i, seg in enumerate(evidence_segments, 1):
            section_label = f"[From {seg.section}"
            if seg.section_title:
                section_label += f": {seg.section_title}"
            section_label += f", Similarity: {seg.similarity_score:.3f}]"
            
            formatted.append(f"\n{i}. {section_label}\n{seg.text}")
        
        return "\n".join(formatted)
    
    def classify_with_context(
        self,
        citation_context: str,
        section: str,
        reference_citation: str,
        abstract: str,
        evidence_segments: List[EnhancedEvidenceSegment],
        first_round_category: str,
        first_round_confidence: float,
        first_round_justification: str
    ) -> SecondRoundClassification:
        """
        Perform second-round classification with enhanced evidence.
        
        Args:
            citation_context: The citation context text
            section: Section where citation appears
            reference_citation: Formatted reference (e.g., "Smith J et al. (2023)")
            abstract: Full abstract of reference article
            evidence_segments: List of enhanced evidence segments
            first_round_category: Category from first round
            first_round_confidence: Confidence from first round
            first_round_justification: Justification from first round
            
        Returns:
            SecondRoundClassification object
        """
        logger.info(
            f"Classifying with {len(evidence_segments)} evidence segments "
            f"(first round: {first_round_category})"
        )
        
        # Format evidence for prompt
        formatted_evidence = self._format_evidence_list(evidence_segments)
        
        # Truncate abstract if too long
        if len(abstract) > 1500:
            abstract = abstract[:1500] + "..."
        
        # Build prompt
        prompt = SECOND_ROUND_PROMPT_TEMPLATE.format(
            first_round_category=first_round_category,
            first_round_confidence=first_round_confidence,
            first_round_justification=first_round_justification,
            section=section,
            citation_context=citation_context,
            reference_citation=reference_citation,
            abstract_text=abstract or "(No abstract available)",
            formatted_evidence=formatted_evidence
        )
        
        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert scientific reviewer evaluating citation accuracy."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=750,  # Allow for detailed justification + user-friendly fields
                temperature=0.0  # Deterministic for consistent classification
            )
            
            # Parse response
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            # Extract data
            citation_type = result.get("citation_type", "UNKNOWN")
            category = result.get("category", first_round_category)
            confidence = float(result.get("confidence", 0.5))
            determination = result.get("determination", "CONFIRMED")
            detailed_explanation = result.get("detailed_explanation", "")
            justification = result.get("justification", "")
            user_overview = result.get("user_overview", "Second-round verification completed.")
            key_findings = result.get("key_findings", [])
            recommendation = result.get("recommendation", "NEEDS_REVIEW")
            
            # Validate determination
            if determination not in ["CONFIRMED", "CORRECTED"]:
                if category != first_round_category:
                    determination = "CORRECTED"
                else:
                    determination = "CONFIRMED"
            
            # Validate recommendation
            if recommendation not in ["ACCURATE", "NEEDS_REVIEW", "MISREPRESENTATION"]:
                # Infer from category
                if category == "SUPPORT":
                    recommendation = "ACCURATE"
                elif category in ["CONTRADICT", "MISQUOTE"]:
                    recommendation = "MISREPRESENTATION"
                else:
                    recommendation = "NEEDS_REVIEW"
            
            # Create classification object
            classification = SecondRoundClassification(
                citation_type=citation_type,
                category=category,
                confidence=confidence,
                determination=determination,
                detailed_explanation=detailed_explanation,
                justification=justification,
                user_overview=user_overview,
                key_findings=key_findings,
                recommendation=recommendation,
                classified_at=datetime.now().isoformat(),
                model_used=self.model,
                tokens_used=response.usage.total_tokens,
                evidence_count=len(evidence_segments),
                abstract_used=abstract,
                enhanced_evidence=evidence_segments,
                first_round_category=first_round_category,
                first_round_confidence=first_round_confidence
            )
            
            logger.info(
                f"Classification complete: {category} ({determination}, "
                f"confidence: {confidence:.2f}, tokens: {response.usage.total_tokens})"
            )
            
            return classification
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Response text: {result_text}")
            
            # Return fallback classification
            return SecondRoundClassification(
                category=first_round_category,
                confidence=first_round_confidence,
                determination="CONFIRMED",
                justification=f"EVAL_FAILED: Could not parse LLM response. {str(e)}",
                classified_at=datetime.now().isoformat(),
                model_used=self.model,
                tokens_used=0,
                evidence_count=len(evidence_segments),
                abstract_used=abstract,
                enhanced_evidence=evidence_segments,
                first_round_category=first_round_category,
                first_round_confidence=first_round_confidence
            )
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            
            # Return fallback classification
            return SecondRoundClassification(
                category=first_round_category,
                confidence=first_round_confidence,
                determination="CONFIRMED",
                justification=f"EVAL_FAILED: OpenAI API error. {str(e)}",
                classified_at=datetime.now().isoformat(),
                model_used=self.model,
                tokens_used=0,
                evidence_count=len(evidence_segments),
                abstract_used=abstract,
                enhanced_evidence=evidence_segments,
                first_round_category=first_round_category,
                first_round_confidence=first_round_confidence
            )
