"""
Workflow 5 - Phase A: Citation Analysis

Deep reading analyzer that performs comprehensive assessment of
problematic citations by reading full paper texts.
Uses DeepSeek Chat for cost-optimized deep analysis.
"""

import logging
import json
import os
from typing import List, Dict, Optional
from openai import OpenAI

from ..models import CitationAssessment
from ..prompts.phase_a_citation_analysis_prompt import format_phase_a_prompt
from ..config import Config

logger = logging.getLogger(__name__)


class CitationAnalyzer:
    """Perform Phase A: Citation Analysis - Deep reading of full papers to assess miscitations."""
    
    def __init__(
        self,
        model: str = None,
        temperature: float = 0.1,
        use_caching: bool = True,
        provider: str = None
    ):
        """
        Initialize analyzer.
        
        Args:
            model: Model to use (defaults based on provider)
            temperature: Sampling temperature (lower = more focused)
            use_caching: Whether to use prompt caching (90% discount)
            provider: "deepseek" or "openai" (defaults to env var or deepseek)
        """
        self.provider = provider or os.getenv('LLM_PROVIDER', 'deepseek')
        self.temperature = temperature
        self.use_caching = use_caching
        
        if self.provider == 'deepseek':
            api_key = Config.DEEPSEEK_API_KEY
            if not api_key:
                raise ValueError("DEEPSEEK_API_KEY environment variable not set")
            self.model = model or 'deepseek-chat'
            self.client = OpenAI(
                api_key=api_key,
                base_url=Config.DEEPSEEK_BASE_URL
            )
            # DeepSeek context limit
            self.max_context_tokens = 120000  # 120K to be safe (actual limit is 131K)
        else:  # openai
            api_key = Config.OPENAI_API_KEY
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            self.model = model or 'gpt-5.2'
            self.client = OpenAI(api_key=api_key)
            # GPT-5.2 has much larger context
            self.max_context_tokens = 200000  # 200K tokens
        
        self.logger = logging.getLogger(__name__)
        logger.info(f"📖 Citation Analyzer (Phase A) initialized with {self.provider.upper()}: {self.model}")
    
    def analyze(
        self,
        citing_paper: Dict,
        problematic_citations: List[Dict],
        reference_papers: Dict[str, Dict]
    ) -> List[CitationAssessment]:
        """
        Perform deep reading analysis on problematic citations.
        Automatically batches if content exceeds context limit.
        
        Args:
            citing_paper: Dict with title, authors, doi, sections
            problematic_citations: List of EnrichedCitationContext dicts
            reference_papers: Dict mapping article_id -> {title, sections}
        
        Returns:
            List of CitationAssessment objects
        """
        self.logger.info(f"📖 Phase A: Analyzing {len(problematic_citations)} citations with full paper context...")
        
        try:
            # Format prompt to estimate size
            system_prompt, user_prompt = format_phase_a_prompt(
                citing_paper,
                problematic_citations,
                reference_papers
            )
            
            # Estimate tokens (rough: 1 token ≈ 4 chars)
            estimated_tokens = (len(system_prompt) + len(user_prompt)) // 4
            
            # Check if batching is needed
            if estimated_tokens > self.max_context_tokens:
                self.logger.warning(
                    f"⚠️  Content too large ({estimated_tokens:,} tokens > {self.max_context_tokens:,} limit). "
                    f"Splitting into batches..."
                )
                return self._analyze_in_batches(citing_paper, problematic_citations, reference_papers)
            
            # Process normally if within limit
            response = self._call_llm(system_prompt, user_prompt)
            assessments = self._parse_response(response)
            
            self.logger.info(f"✅ Successfully analyzed {len(assessments)} citations")
            return assessments
            
        except Exception as e:
            self.logger.error(f"❌ Phase A: Citation analysis failed: {e}")
            raise
    
    def _analyze_in_batches(
        self,
        citing_paper: Dict,
        problematic_citations: List[Dict],
        reference_papers: Dict[str, Dict]
    ) -> List[CitationAssessment]:
        """
        Split citations into batches and analyze separately.
        
        Strategy: Split by number of citations, processing 3-5 at a time.
        This keeps each batch manageable while maintaining context.
        """
        batch_size = 3  # Conservative batch size for large papers
        all_assessments = []
        
        num_batches = (len(problematic_citations) + batch_size - 1) // batch_size
        self.logger.info(f"📦 Splitting {len(problematic_citations)} citations into {num_batches} batches")
        
        for i in range(0, len(problematic_citations), batch_size):
            batch_citations = problematic_citations[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            self.logger.info(f"📖 Processing batch {batch_num}/{num_batches} ({len(batch_citations)} citations)...")
            
            try:
                # Format prompt for this batch
                system_prompt, user_prompt = format_phase_a_prompt(
                    citing_paper,
                    batch_citations,
                    reference_papers
                )
                
                # Call LLM
                response = self._call_llm(system_prompt, user_prompt)
                
                # Parse response
                batch_assessments = self._parse_response(response)
                all_assessments.extend(batch_assessments)
                
                self.logger.info(f"✅ Batch {batch_num}/{num_batches} complete: {len(batch_assessments)} assessments")
                
            except Exception as e:
                self.logger.error(f"❌ Batch {batch_num}/{num_batches} failed: {e}")
                # Continue with other batches
                continue
        
        self.logger.info(f"✅ All batches complete: {len(all_assessments)} total assessments")
        return all_assessments
    
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
        Call OpenAI API with optional caching.
        
        Caching strategy:
        - System prompt: Cached (rarely changes)
        - Citing paper sections: Cached (same across all citations)
        - Reference papers: Not cached (changes per citation)
        """
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ]
        
        # Add cache control if supported (OpenAI's prompt caching)
        if self.use_caching:
            # Mark system prompt for caching
            messages[0]["cache_control"] = {"type": "ephemeral"}
            
            self.logger.debug("Prompt caching enabled for system prompt")
        
        # Log what we're sending
        self.logger.info("=" * 80)
        self.logger.info(f"SENDING TO LLM:")
        self.logger.info(f"System prompt length: {len(system_prompt)} chars")
        self.logger.info(f"User prompt length: {len(user_prompt)} chars")
        self.logger.info(f"First 1000 chars of user prompt:")
        self.logger.info(user_prompt[:1000])
        self.logger.info("=" * 80)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature
                # Note: Not specifying response_format to allow JSON arrays
            )
            
            # Log token usage
            usage = response.usage
            if usage:
                self.logger.info(
                    f"Tokens used: {usage.total_tokens} "
                    f"(prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens})"
                )
                
                # Log cache hit info if available
                if hasattr(usage, 'prompt_tokens_details'):
                    cache_info = usage.prompt_tokens_details
                    if hasattr(cache_info, 'cached_tokens'):
                        self.logger.info(f"Cached tokens: {cache_info.cached_tokens}")
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"LLM API call failed: {e}")
            raise
    
    def _parse_response(self, response_text: str) -> List[CitationAssessment]:
        """
        Parse LLM JSON response into CitationAssessment objects.
        
        Args:
            response_text: JSON string from LLM
        
        Returns:
            List of CitationAssessment objects
        """
        # ALWAYS log the full response for debugging
        self.logger.info("=" * 80)
        self.logger.info("FULL LLM RESPONSE:")
        self.logger.info(response_text)
        self.logger.info("=" * 80)
        
        try:
            # Parse JSON
            data = json.loads(response_text)
            
            # Handle both array and object with array field
            if isinstance(data, dict) and 'citations' in data:
                citations_data = data['citations']
            elif isinstance(data, list):
                citations_data = data
            else:
                self.logger.error(f"Unexpected response format. Type: {type(data)}")
                self.logger.error(f"Keys in dict: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
                self.logger.error(f"First 500 chars of response: {response_text[:500]}")
                raise ValueError(f"Unexpected response format: {type(data)}, keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
            
            # Convert to CitationAssessment objects
            assessments = []
            for citation_data in citations_data:
                try:
                    assessment = CitationAssessment(**citation_data)
                    assessments.append(assessment)
                except Exception as e:
                    self.logger.warning(f"Failed to parse citation assessment: {e}")
                    self.logger.debug(f"Problematic data: {citation_data}")
            
            return assessments
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM response as JSON: {e}")
            self.logger.debug(f"Response text: {response_text[:500]}...")
            raise
        except Exception as e:
            self.logger.error(f"Failed to parse response: {e}")
            raise
    
    def analyze_batch(
        self,
        papers_data: List[Dict]
    ) -> Dict[str, List[CitationAssessment]]:
        """
        Analyze multiple papers in batch.
        
        Args:
            papers_data: List of dicts with citing_paper, problematic_citations, reference_papers
        
        Returns:
            Dict mapping article_id -> List[CitationAssessment]
        """
        results = {}
        
        for paper_data in papers_data:
            article_id = paper_data['citing_paper']['article_id']
            
            try:
                assessments = self.analyze(
                    paper_data['citing_paper'],
                    paper_data['problematic_citations'],
                    paper_data['reference_papers']
                )
                results[article_id] = assessments
                
            except Exception as e:
                self.logger.error(f"Failed to analyze paper {article_id}: {e}")
                results[article_id] = []
        
        return results
