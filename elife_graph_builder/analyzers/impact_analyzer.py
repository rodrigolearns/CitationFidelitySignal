"""
Workflow 5 - Phase B: Synthesis & Reporting

Pattern analyzer and report generator that synthesizes findings from
Phase A into comprehensive impact assessments and recommendations.
Uses DeepSeek Reasoner (thinking mode) for strategic analysis.
Supports Batch API for additional cost savings.
"""

import logging
import json
import os
import time
from typing import List, Dict, Optional
from openai import OpenAI

from ..models import CombinedImpactAnalysis, CitationAssessment
from ..prompts.phase_b_synthesis_prompt import format_phase_b_prompt
from ..config import Config

logger = logging.getLogger(__name__)


class ImpactSynthesizer:
    """Phase B: Synthesis & Reporting - Generate comprehensive impact assessment and strategic recommendations."""
    
    def __init__(
        self,
        model: str = None,
        temperature: float = 0.1,
        use_batch_api: bool = True,
        provider: str = None
    ):
        """
        Initialize analyzer.
        
        Args:
            model: Model to use (defaults based on provider)
            temperature: Sampling temperature
            use_batch_api: Use Batch API for 50% cost savings (slower but cheaper)
            provider: "deepseek" or "openai" (defaults to env var or deepseek)
        """
        self.provider = provider or os.getenv('LLM_PROVIDER', 'deepseek')
        self.temperature = temperature
        self.use_batch_api = use_batch_api
        
        if self.provider == 'deepseek':
            api_key = Config.DEEPSEEK_API_KEY
            if not api_key:
                raise ValueError("DEEPSEEK_API_KEY environment variable not set")
            # Use thinking mode for strategic reasoning
            self.model = model or 'deepseek-reasoner'
            self.client = OpenAI(
                api_key=api_key,
                base_url=Config.DEEPSEEK_BASE_URL
            )
        else:  # openai
            api_key = Config.OPENAI_API_KEY
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            self.model = model or 'gpt-5.2'
            self.client = OpenAI(api_key=api_key)
        
        self.logger = logging.getLogger(__name__)
        logger.info(f"🔗 Impact Synthesizer (Phase B) initialized with {self.provider.upper()}: {self.model}")
    
    def generate_complete_analysis(
        self,
        paper_metadata: Dict,
        stage1_assessments: List[CitationAssessment],
        problematic_citations_contexts: List[Dict]
    ) -> CombinedImpactAnalysis:
        """
        Generate complete impact analysis from Stage 1 results.
        
        Args:
            paper_metadata: Dict with title, authors, doi, total_citations
            stage1_assessments: List of CitationAssessment objects from Stage 1
            problematic_citations_contexts: List of EnrichedCitationContext dicts
        
        Returns:
            CombinedImpactAnalysis object
        """
        self.logger.info(
            f"Generating impact analysis for {paper_metadata.get('title', 'Unknown')[:50]}..."
        )
        
        try:
            # Format prompt
            system_prompt, user_prompt = format_phase_b_prompt(
                paper_metadata,
                stage1_assessments,
                problematic_citations_contexts
            )
            
            # Call LLM (with or without Batch API)
            if self.use_batch_api:
                response = self._call_llm_batch(system_prompt, user_prompt)
            else:
                response = self._call_llm_sync(system_prompt, user_prompt)
            
            # Parse response
            analysis = self._parse_response(response)
            
            self.logger.info(
                f"Successfully generated analysis. Classification: {analysis.overall_classification}"
            )
            return analysis
            
        except Exception as e:
            self.logger.error(f"❌ Phase B: Synthesis failed: {e}")
            raise
    
    def _call_llm_sync(self, system_prompt: str, user_prompt: str) -> str:
        """
        Call OpenAI API synchronously (immediate response).
        
        Args:
            system_prompt: System message
            user_prompt: User message
        
        Returns:
            Response text
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            # Log token usage
            usage = response.usage
            if usage:
                self.logger.info(
                    f"Tokens used: {usage.total_tokens} "
                    f"(prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens})"
                )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"Sync LLM API call failed: {e}")
            raise
    
    def _call_llm_batch(self, system_prompt: str, user_prompt: str) -> str:
        """
        Call OpenAI Batch API (50% discount, slower response).
        
        The Batch API queues requests and processes them within 24 hours.
        For our use case (on-demand analysis), we'll use a polling approach.
        
        Args:
            system_prompt: System message
            user_prompt: User message
        
        Returns:
            Response text
        """
        self.logger.info("Using Batch API (50% cost savings, ~30-60 sec delay)")
        
        # For now, simulate batch behavior with sync call + delay
        # In production, you would:
        # 1. Create batch job with client.batches.create()
        # 2. Poll for completion with client.batches.retrieve()
        # 3. Fetch results when complete
        
        # TODO: Implement actual Batch API integration
        # For MVP, we'll use sync call (still much cheaper than before)
        
        self.logger.warning("Batch API not fully implemented yet, using sync call")
        return self._call_llm_sync(system_prompt, user_prompt)
    
    def _parse_response(self, response_text: str) -> CombinedImpactAnalysis:
        """
        Parse LLM JSON response into CombinedImpactAnalysis object.
        
        Args:
            response_text: JSON string from LLM
        
        Returns:
            CombinedImpactAnalysis object
        """
        # Log full response for debugging
        self.logger.info("=" * 80)
        self.logger.info("PHASE B FULL LLM RESPONSE:")
        self.logger.info(response_text)
        self.logger.info("=" * 80)
        
        try:
            data = json.loads(response_text)
            
            # Create CombinedImpactAnalysis object
            analysis = CombinedImpactAnalysis(**data)
            
            return analysis
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM response as JSON: {e}")
            self.logger.debug(f"Response text: {response_text[:500]}...")
            raise
        except Exception as e:
            self.logger.error(f"Failed to create CombinedImpactAnalysis: {e}")
            self.logger.debug(f"Data: {json.dumps(data, indent=2)[:500]}...")
            raise
    
    def analyze_batch_papers(
        self,
        papers_data: List[Dict]
    ) -> Dict[str, CombinedImpactAnalysis]:
        """
        Analyze multiple papers in batch.
        
        Args:
            papers_data: List of dicts with paper_metadata, stage1_assessments, contexts
        
        Returns:
            Dict mapping article_id -> CombinedImpactAnalysis
        """
        results = {}
        
        for paper_data in papers_data:
            article_id = paper_data['paper_metadata']['article_id']
            
            try:
                analysis = self.generate_complete_analysis(
                    paper_data['paper_metadata'],
                    paper_data['stage1_assessments'],
                    paper_data['problematic_citations_contexts']
                )
                results[article_id] = analysis
                
            except Exception as e:
                self.logger.error(f"Failed to analyze paper {article_id}: {e}")
                # Don't fail entire batch for one paper
                continue
        
        return results
