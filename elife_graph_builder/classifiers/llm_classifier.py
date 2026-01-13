"""LLM-based citation classifier using OpenAI."""

import os
import json
import logging
from typing import List, Optional, Dict
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

from ..models import CitationContext, CitationClassification, EvidenceSegment

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class LLMClassifier:
    """
    Classifies citation fidelity using OpenAI GPT models.
    
    Evaluates whether evidence from a reference paper supports
    a citation made in a citing paper.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = None,
        temperature: float = 0.0,
        max_tokens: int = 500
    ):
        """
        Initialize the LLM classifier.
        
        Args:
            api_key: OpenAI API key (defaults to env var)
            model: Model to use (defaults to env var or gpt-5-mini)
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens in response
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY in .env")
        
        self.model = model or os.getenv('OPENAI_MODEL', 'gpt-5-mini')
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.api_key)
        
        logger.info(f"✅ LLM Classifier initialized with model: {self.model}")
    
    def _build_prompt(
        self,
        citation_format: str,
        context_text: str,
        context_section: str,
        evidence_segments: List[EvidenceSegment]
    ) -> str:
        """
        Build the classification prompt.
        
        Args:
            citation_format: How citation appears in text (e.g., "Smith J et al., 2023")
            context_text: The 4-sentence citation context
            context_section: Section containing citation (e.g., "Introduction")
            evidence_segments: Retrieved evidence from reference paper
            
        Returns:
            Formatted prompt string
        """
        # Build evidence section (limit to top 3 segments, truncate to 300 words each)
        evidence_text = ""
        # Sort by similarity and take top 3
        top_segments = sorted(evidence_segments, key=lambda e: e.similarity_score, reverse=True)[:3]
        
        for i, seg in enumerate(top_segments, 1):
            # Truncate to 300 words to keep prompts manageable
            words = seg.text.split()
            truncated = ' '.join(words[:300])
            if len(words) > 300:
                truncated += "... [truncated]"
            
            evidence_text += f"""
Evidence {i} (similarity: {seg.similarity_score:.2f}, section: {seg.section}):
"{truncated}"
"""
        
        prompt = f"""You are a scientific citation accuracy evaluator. Your task is to determine whether evidence from a reference paper supports a citation made in a citing paper. IMPORTANT: The citation context below may reference multiple papers (e.g., "Smith, 2020; Jones, 2021"). You are evaluating ONLY the specific citation indicated. Other citations in the context are NOT relevant to your evaluation. Focus solely on whether THIS citation is supported by the provided evidence from its reference paper. The evidence segments were retrieved using semantic similarity and may or may not actually support the citation claim.

CLASSIFICATION CATEGORIES (choose exactly ONE):

SUPPORT
The evidence clearly and directly supports the claim made in the citation context. The findings, methods, or conclusions in the reference paper align with how they are represented in the citing paper. The citation accurately reflects what the reference paper states.

CONTRADICT
The evidence directly contradicts or opposes the claim made in the citation context. The reference paper's findings or conclusions are opposite to how they are presented in the citing paper.

NOT_SUBSTANTIATE
The evidence is topically related to the citation but does not actually support the specific claim being made. The reference paper may discuss the same subject area but doesn't provide evidence for the particular assertion in the citation context. This is distinct from CONTRADICT—the evidence doesn't oppose the claim, it simply doesn't prove it.

IRRELEVANT
The evidence has no meaningful connection to the citation context. The retrieved passages discuss unrelated topics, methods, or findings. This often occurs when similarity scores are low (<0.7) or when the semantic match is superficial rather than substantive.

OVERSIMPLIFY
The citation reduces complex, nuanced, or conditional findings from the reference paper into an overly simple or absolute statement. The reference paper may present caveats, limitations, or context that the citation omits, potentially misrepresenting the certainty or scope of the findings.

MISQUOTE
The citation misattributes findings, misquotes results, or incorrectly represents what the reference paper actually states. This includes citing wrong figures, incorrect statistical values, or attributing findings to the wrong study or authors.

INDIRECT
The citation treats the reference as a primary source when the reference paper itself cites another source for the claim. The reference paper is being used as an intermediary rather than the original source of the finding.

ETIQUETTE
The citation appears to be a courtesy or conventional citation without substantive connection to the claim. These are often citations to establish credibility, cite a field's foundational work, or acknowledge colleagues, but the reference paper doesn't actually provide evidence for the specific statement.

RESPONSE FORMAT:
{{
  "classification": "one of the 8 categories above",
  "confidence": 0.0-1.0,
  "justification": "2-3 sentences explaining your reasoning"
}}

EXAMPLE - OVERSIMPLIFY:
Cited as: Kumar S et al. (2020)
Citation Context (from citing paper):
Section: Introduction
Text: "Studies have demonstrated that intermittent fasting leads to weight loss (Kumar S et al., 2020)."

Evidence from Reference Paper:
Evidence 1 (similarity: 0.84, section: Results):
"Participants following intermittent fasting protocols lost an average of 3.2 kg over 12 weeks compared to 2.1 kg in the control group (p=0.03). However, when adjusted for caloric intake, the difference was not statistically significant (p=0.18)."

Evidence 2 (similarity: 0.79, section: Discussion):
"Our findings suggest that intermittent fasting may facilitate weight loss primarily through reduced caloric intake rather than through metabolic advantages. When caloric intake was matched between groups, the fasting advantage disappeared."

Classification:
{{
  "classification": "OVERSIMPLIFY",
  "confidence": 0.82,
  "justification": "The citation presents intermittent fasting as straightforwardly causing weight loss, but the reference paper shows this is only true when calorie-matched. The citation omits critical nuance about the mechanism and conditions under which the effect occurs."
}}

---

NOW EVALUATE THIS CITATION:

REFERENCE BEING EVALUATED:
Cited as: {citation_format}

CITATION CONTEXT (from citing paper):
Section: {context_section}
Text: "{context_text}"

EVIDENCE FROM REFERENCE PAPER:
{evidence_text}

Provide your classification in JSON format.
"""
        return prompt
    
    def classify_context(
        self,
        citation_format: str,
        context: CitationContext,
        reference_article_id: str
    ) -> CitationClassification:
        """
        Classify a single citation context.
        
        Args:
            citation_format: How citation appears (e.g., "Smith J et al., 2023")
            context: CitationContext object with text and evidence
            reference_article_id: ID of reference article (for logging)
            
        Returns:
            CitationClassification object
        """
        logger.info(
            f"Classifying citation context {context.instance_id}: "
            f"{context.source_article_id} → {reference_article_id}"
        )
        
        # Check we have evidence
        if not context.evidence_segments:
            logger.warning(f"No evidence segments for context {context.instance_id}")
            return CitationClassification(
                classification="IRRELEVANT",
                confidence=0.5,
                justification="No evidence segments available for evaluation.",
                classified_at=datetime.now().isoformat(),
                model_used=self.model,
                tokens_used=0
            )
        
        # Build prompt
        prompt = self._build_prompt(
            citation_format=citation_format,
            context_text=context.context_text,
            context_section=context.section,
            evidence_segments=context.evidence_segments
        )
        
        # Call OpenAI API
        try:
            # Build API parameters
            api_params = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_completion_tokens": self.max_tokens,
                "response_format": {"type": "json_object"}
            }
            
            # Only add temperature for models that support it
            if not self.model.startswith("gpt-5"):
                api_params["temperature"] = self.temperature
            
            response = self.client.chat.completions.create(**api_params)
            
            # Parse response
            result_text = response.choices[0].message.content
            
            # Validate response is not empty
            if not result_text or result_text.strip() == "":
                logger.error("Empty response from LLM")
                return CitationClassification(
                    classification="NOT_SUBSTANTIATE",
                    confidence=0.3,
                    justification="LLM returned empty response - unable to evaluate evidence quality.",
                    classified_at=datetime.now().isoformat(),
                    model_used=self.model,
                    tokens_used=response.usage.total_tokens if response.usage else 0
                )
            
            result = json.loads(result_text)
            
            # Extract token usage
            tokens_used = response.usage.total_tokens
            
            logger.info(
                f"✅ Classification: {result['classification']} "
                f"(confidence: {result['confidence']:.2f}, tokens: {tokens_used})"
            )
            
            return CitationClassification(
                classification=result['classification'],
                confidence=float(result['confidence']),
                justification=result['justification'],
                classified_at=datetime.now().isoformat(),
                model_used=self.model,
                tokens_used=tokens_used
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text: {response.choices[0].message.content}")
            raise
        
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
    
    def classify_batch(
        self,
        citation_format: str,
        contexts: List[CitationContext],
        reference_article_id: str
    ) -> List[CitationClassification]:
        """
        Classify multiple contexts for the same citation.
        
        Args:
            citation_format: How citation appears
            contexts: List of CitationContext objects
            reference_article_id: ID of reference article
            
        Returns:
            List of CitationClassification objects
        """
        logger.info(
            f"Classifying {len(contexts)} contexts for citation: "
            f"{citation_format}"
        )
        
        classifications = []
        total_tokens = 0
        
        for context in contexts:
            try:
                classification = self.classify_context(
                    citation_format=citation_format,
                    context=context,
                    reference_article_id=reference_article_id
                )
                classifications.append(classification)
                
                if classification.tokens_used:
                    total_tokens += classification.tokens_used
                    
            except Exception as e:
                logger.error(
                    f"Failed to classify context {context.instance_id}: {e}"
                )
                # Add error classification
                classifications.append(
                    CitationClassification(
                        classification="ERROR",
                        confidence=0.0,
                        justification=f"Classification failed: {str(e)}",
                        classified_at=datetime.now().isoformat(),
                        model_used=self.model
                    )
                )
        
        logger.info(
            f"✅ Batch complete: {len(classifications)} classifications, "
            f"{total_tokens} tokens"
        )
        
        return classifications
