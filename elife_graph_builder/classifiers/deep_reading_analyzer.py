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
        print("=" * 80)
        print(f"SENDING TO LLM:")
        print(f"Model: {self.model}")
        print(f"Provider: {self.provider}")
        print(f"System prompt length: {len(system_prompt)} chars")
        print(f"User prompt length: {len(user_prompt)} chars")
        print(f"First 500 chars of user prompt:")
        print(user_prompt[:500])
        print("=" * 80)
        
        try:
            print(f"📞 Calling {self.model} API...")
            
            # Set max_tokens based on provider
            # DeepSeek default is 4096, but we need more for 10+ citations
            max_tokens = 8192 if self.provider == 'deepseek' else 16384
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=max_tokens
                # Note: Not specifying response_format to allow JSON arrays
            )
            
            print("✅ API call successful")
            
            # Log token usage
            usage = response.usage
            if usage:
                print(
                    f"Tokens used: {usage.total_tokens} "
                    f"(prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens})"
                )
                
                # Log cache hit info if available
                if hasattr(usage, 'prompt_tokens_details'):
                    cache_info = usage.prompt_tokens_details
                    if hasattr(cache_info, 'cached_tokens'):
                        print(f"Cached tokens: {cache_info.cached_tokens}")
            
            content = response.choices[0].message.content
            print(f"📝 Response content type: {type(content)}")
            print(f"📝 Response length: {len(content) if content else 0} chars")
            if content:
                print(f"📝 First 200 chars of response: {content[:200]}")
            else:
                print("📝 CONTENT IS NONE OR EMPTY!")
            
            return content
            
        except Exception as e:
            self.logger.error(f"LLM API call failed: {e}")
            raise
    
    def _repair_json(self, broken_json: str, max_attempts: int = 3) -> str:
        """
        Attempt to repair malformed JSON using LLM.
        
        Args:
            broken_json: The malformed JSON string
            max_attempts: Maximum repair attempts
            
        Returns:
            Repaired JSON string
        """
        for attempt in range(1, max_attempts + 1):
            print(f"🔧 JSON repair attempt {attempt}/{max_attempts}...")
            
            repair_prompt = f"""You are a JSON repair expert. Fix the following malformed JSON array and return ONLY the valid JSON, nothing else.

Rules:
1. Complete any truncated objects
2. Close all unclosed brackets/braces
3. Fix any syntax errors
4. Preserve all existing data
5. Return ONLY valid JSON array, no markdown, no explanations

Malformed JSON:
{broken_json}

Return the corrected JSON:"""
            
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a JSON repair specialist. Return only valid JSON."},
                        {"role": "user", "content": repair_prompt}
                    ],
                    temperature=0.0,  # Use 0 for deterministic repairs
                    max_tokens=12288  # Allow for large responses
                )
                
                repaired = response.choices[0].message.content.strip()
                
                # Strip markdown if present
                if repaired.startswith('```'):
                    start = repaired.find('\n')
                    end = repaired.rfind('```')
                    if start != -1 and end != -1:
                        repaired = repaired[start+1:end].strip()
                
                # Test if it's valid JSON
                json.loads(repaired)
                print(f"✅ Repair successful on attempt {attempt}")
                return repaired
                
            except Exception as e:
                print(f"❌ Attempt {attempt} failed: {e}")
                if attempt == max_attempts:
                    raise
                continue
        
        raise ValueError("Failed to repair JSON after all attempts")
    
    def _parse_response(self, response_text: str) -> List[CitationAssessment]:
        """
        Parse LLM JSON response into CitationAssessment objects.
        
        Args:
            response_text: JSON string from LLM
        
        Returns:
            List of CitationAssessment objects
        """
        # Check for None response (API call issue)
        if response_text is None:
            error_msg = (
                "❌ LLM API returned None (no content).\n"
                "Possible causes:\n"
                "  1. API call failed silently\n"
                "  2. response.choices[0].message.content was None\n"
                "  3. Model refused to respond\n"
                "Check API logs and model settings."
            )
            print(error_msg)
            raise ValueError(error_msg)
        
        # ALWAYS log the full response for debugging (using print for visibility)
        print("=" * 80)
        print("FULL LLM RESPONSE:")
        print(f"Response type: {type(response_text)}")
        print(f"Response length: {len(response_text) if response_text else 0} chars")
        if response_text:
            print(f"First 500 chars: {response_text[:500]}")
            if len(response_text) > 500:
                print(f"... ({len(response_text) - 500} more chars)")
                print(f"Last 500 chars: {response_text[-500:]}")
        else:
            print("EMPTY RESPONSE!")
        print("=" * 80)
        
        # Check for empty response
        if not response_text or not response_text.strip():
            error_msg = (
                "❌ LLM returned empty response. Possible causes:\n"
                "  1. API key is invalid or missing\n"
                "  2. Model name is incorrect (check LLM_PROVIDER and model)\n"
                "  3. Request was rejected by the API\n"
                "  4. Network timeout or connection error\n"
                "  5. Context window exceeded"
            )
            self.logger.error(error_msg)
            raise ValueError("Empty LLM response")
        
        # Strip markdown code blocks if present (DeepSeek often wraps JSON in ```json...```)
        response_text = response_text.strip()
        if response_text.startswith('```'):
            # Find the first newline after opening fence
            start = response_text.find('\n')
            # Find the closing fence
            end = response_text.rfind('```')
            if start != -1 and end != -1 and end > start:
                response_text = response_text[start+1:end].strip()
                self.logger.info("Stripped markdown code fences from response")
        
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
                
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing failed: {e}")
            print(f"Attempting to repair JSON with LLM...")
            
            # Try to repair the JSON using a lightweight LLM call
            try:
                repaired_text = self._repair_json(response_text, max_attempts=3)
                data = json.loads(repaired_text)
                print("✅ JSON repair successful!")
                
                # Handle both array and object with array field
                if isinstance(data, dict) and 'citations' in data:
                    citations_data = data['citations']
                elif isinstance(data, list):
                    citations_data = data
                else:
                    raise ValueError(f"Repaired JSON has unexpected format: {type(data)}")
                    
            except Exception as repair_error:
                print(f"❌ JSON repair failed: {repair_error}")
                # Provide detailed error with actual response
                error_msg = (
                    f"Failed to parse LLM response as JSON.\n"
                    f"Original error: {e}\n"
                    f"Repair error: {repair_error}\n"
                    f"Response length: {len(response_text)} chars\n"
                    f"First 1000 chars:\n{response_text[:1000]}\n"
                    f"Last 1000 chars:\n{response_text[-1000:]}"
                )
                raise ValueError(error_msg)
        
        # Convert to CitationAssessment objects (runs after successful JSON parsing)
        assessments = []
        for citation_data in citations_data:
            try:
                assessment = CitationAssessment(**citation_data)
                assessments.append(assessment)
            except Exception as e:
                print(f"⚠️ Failed to parse citation assessment: {e}")
                print(f"Problematic data: {citation_data}")
                self.logger.warning(f"Failed to parse citation assessment: {e}")
                self.logger.debug(f"Problematic data: {citation_data}")
        
        if not assessments:
            error_msg = (
                f"Failed to create any CitationAssessment objects.\n"
                f"Parsed {len(citations_data)} items from JSON, but all failed validation.\n"
                f"Response length: {len(response_text)} chars\n"
                f"First citation data: {citations_data[0] if citations_data else 'N/A'}"
            )
            raise ValueError(error_msg)
        
        return assessments
    
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
