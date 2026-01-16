"""
NeoWorkflow 5: Reference-Centric Impact Analysis

This is a complete redesign of impact assessment that:
1. Groups citations by reference paper (not individual citations)
2. Analyzes all mentions (suspicious + supporting) together for each reference
3. Uses full paper text for deep analysis
4. Provides specific, actionable impact statements (not vague trust ratings)
5. Stores results separately from classic Workflow 5 for comparison
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from openai import OpenAI

from elife_graph_builder.config import Config

logger = logging.getLogger(__name__)


class NeoImpactAnalyzer:
    """
    Reference-centric impact analyzer for NeoWorkflow 5.
    
    Phase A: For each reference paper, analyze ALL citations (suspicious + support)
             together to understand patterns of use/misuse.
    
    Phase B: Synthesize all reference-specific analyses into cumulative assessment
             focusing on what is wrong (not vague trust ratings).
    """
    
    def __init__(self, provider: str = 'deepseek', model: Optional[str] = None):
        """
        Initialize the analyzer.
        
        Args:
            provider: 'deepseek' or 'openai'
            model: Model name (defaults: deepseek-reasoner, gpt-4o)
        """
        self.provider = provider
        
        if provider == 'deepseek':
            api_key = Config.DEEPSEEK_API_KEY
            if not api_key:
                raise ValueError("DEEPSEEK_API_KEY environment variable not set")
            self.model = model or 'deepseek-reasoner'
            self.client = OpenAI(
                api_key=api_key,
                base_url=Config.DEEPSEEK_BASE_URL
            )
        else:  # openai
            api_key = Config.OPENAI_API_KEY
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            self.model = model or 'gpt-4o'
            self.client = OpenAI(api_key=api_key)
        
        logger.info(f"NeoImpactAnalyzer initialized with {provider}/{self.model}")
    
    def group_citations_by_reference(
        self, 
        citing_paper_id: str,
        all_contexts: List[Dict]
    ) -> Dict[str, Dict]:
        """
        Group all citation contexts by their reference paper.
        
        Returns:
            {
                'ref_paper_id_1': {
                    'suspicious': [context1, context2, ...],
                    'supporting': [context3, context4, ...],
                    'all_contexts': [all contexts],
                    'metadata': {...}
                },
                ...
            }
        """
        grouped = defaultdict(lambda: {
            'suspicious': [],
            'supporting': [],
            'all_contexts': [],
            'metadata': {}
        })
        
        for context in all_contexts:
            ref_id = context['target_article_id']
            grouped[ref_id]['all_contexts'].append(context)
            
            # Classify as suspicious or supporting based on classification
            if context['classification'] in ['HIGH_CONCERN', 'MODERATE_CONCERN', 'MINOR_CONCERN']:
                grouped[ref_id]['suspicious'].append(context)
            else:
                grouped[ref_id]['supporting'].append(context)
        
        return dict(grouped)
    
    def analyze_reference_usage(
        self,
        citing_paper_id: str,
        citing_paper_text: str,
        ref_paper_id: str,
        ref_paper_text: str,
        suspicious_contexts: List[Dict],
        supporting_contexts: List[Dict]
    ) -> Dict:
        """
        Phase A: Analyze how the citing paper uses/misuses a single reference paper.
        
        This is the core of NeoWorkflow 5. We analyze ALL mentions together
        (suspicious + supporting) to understand the pattern of citation behavior.
        
        Args:
            citing_paper_id: ID of the citing paper
            citing_paper_text: Full text of citing paper
            ref_paper_id: ID of the reference paper being analyzed
            ref_paper_text: Full text of reference paper
            suspicious_contexts: List of suspicious citation contexts
            supporting_contexts: List of supporting citation contexts
        
        Returns:
            {
                'reference_paper_id': str,
                'suspicious_count': int,
                'supporting_count': int,
                'color_rating': str,  # RED, ORANGE, YELLOW, GREEN
                'impact_statement': str,  # What's wrong/cherry-picked/misunderstood
                'specific_issues': [str],  # Bulleted list of specific problems
                'consequences': str,  # What parts of citing paper are affected
                'sections_affected': [str]  # Which sections rely on this reference
            }
        """
        from elife_graph_builder.prompts.neo_phase_a_prompt import format_phase_a_prompt
        
        logger.info(f"Phase A: Analyzing reference {ref_paper_id} "
                   f"({len(suspicious_contexts)} suspicious, {len(supporting_contexts)} supporting)")
        
        # Format the prompt with all data
        prompt = format_phase_a_prompt(
            citing_paper_text=citing_paper_text,
            ref_paper_text=ref_paper_text,
            suspicious_contexts=suspicious_contexts,
            supporting_contexts=supporting_contexts
        )
        
        # Call LLM
        response = self._call_llm(prompt)
        
        # Parse response
        result = self._parse_phase_a_response(response, ref_paper_id, suspicious_contexts, supporting_contexts)
        
        return result
    
    def synthesize_cumulative_impact(
        self,
        citing_paper_id: str,
        citing_paper_metadata: Dict,
        reference_analyses: List[Dict]
    ) -> Dict:
        """
        Phase B: Synthesize all reference-specific analyses into cumulative assessment.
        
        This aggregates all the mini-reports from Phase A and provides:
        1. List of all accumulated caveats
        2. Combined impact (not vague trust rating)
        3. Specific, actionable recommendations
        
        Args:
            citing_paper_id: ID of the citing paper
            citing_paper_metadata: Title, authors, etc.
            reference_analyses: List of Phase A results (one per reference)
        
        Returns:
            {
                'overall_color': str,  # RED, ORANGE, YELLOW, GREEN
                'accumulated_caveats': [str],  # All issues combined
                'sections_with_issues': {  # Grouped by section
                    'Introduction': [issues],
                    'Methods': [issues],
                    ...
                },
                'recommendations_for_reviewers': [str],
                'recommendations_for_readers': [str],
                'executive_summary': str  # Clear, specific, actionable
            }
        """
        from elife_graph_builder.prompts.neo_phase_b_prompt import format_phase_b_prompt
        
        logger.info(f"Phase B: Synthesizing cumulative impact for {citing_paper_id} "
                   f"from {len(reference_analyses)} reference analyses")
        
        # Format the prompt
        prompt = format_phase_b_prompt(
            citing_paper_metadata=citing_paper_metadata,
            reference_analyses=reference_analyses
        )
        
        # Call LLM
        response = self._call_llm(prompt)
        
        # Parse response
        result = self._parse_phase_b_response(response, reference_analyses)
        
        return result
    
    def run_neo_analysis(
        self,
        citing_paper_id: str,
        citing_paper_path: Path,
        all_contexts: List[Dict]
    ) -> Dict:
        """
        Run complete NeoWorkflow 5 analysis on a paper.
        
        Args:
            citing_paper_id: Article ID of the citing paper
            citing_paper_path: Path to citing paper XML
            all_contexts: All citation contexts (suspicious + support)
        
        Returns:
            Complete NEO analysis result with reference_analyses and synthesis
        """
        logger.info(f"Starting NeoWorkflow 5 for paper {citing_paper_id}")
        logger.info(f"Total contexts: {len(all_contexts)}")
        
        # Load citing paper text
        citing_paper_text = self._load_paper_text(citing_paper_path)
        
        # Group by reference
        grouped = self.group_citations_by_reference(citing_paper_id, all_contexts)
        logger.info(f"Grouped into {len(grouped)} reference papers")
        
        # Phase A: Analyze each reference
        reference_analyses = []
        for ref_id, ref_data in grouped.items():
            suspicious = ref_data['suspicious']
            supporting = ref_data['supporting']
            
            logger.info(f"Processing reference {ref_id}: "
                       f"{len(suspicious)} suspicious, {len(supporting)} supporting")
            
            # Find reference paper XML
            ref_paper_path = self._find_reference_paper(ref_id)
            if not ref_paper_path:
                logger.warning(f"Could not find XML for reference {ref_id}, skipping")
                continue
            
            ref_paper_text = self._load_paper_text(ref_paper_path)
            
            # Analyze this reference
            analysis = self.analyze_reference_usage(
                citing_paper_id=citing_paper_id,
                citing_paper_text=citing_paper_text,
                ref_paper_id=ref_id,
                ref_paper_text=ref_paper_text,
                suspicious_contexts=suspicious,
                supporting_contexts=supporting
            )
            
            reference_analyses.append(analysis)
        
        # Phase B: Synthesize
        citing_metadata = {
            'article_id': citing_paper_id,
            'title': 'Title TBD',  # Will be fetched from Neo4j
            'authors': []
        }
        
        synthesis = self.synthesize_cumulative_impact(
            citing_paper_id=citing_paper_id,
            citing_paper_metadata=citing_metadata,
            reference_analyses=reference_analyses
        )
        
        # Combine results
        result = {
            'citing_paper_id': citing_paper_id,
            'reference_analyses': reference_analyses,
            'synthesis': synthesis,
            'metadata': {
                'total_references_analyzed': len(reference_analyses),
                'total_suspicious_citations': sum(len(r['suspicious']) for r in grouped.values()),
                'total_supporting_citations': sum(len(r['supporting']) for r in grouped.values())
            }
        }
        
        logger.info(f"NeoWorkflow 5 complete for {citing_paper_id}")
        return result
    
    def _call_llm(self, prompt: str) -> str:
        """Call the LLM with the given prompt."""
        messages = [{"role": "user", "content": prompt}]
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=4000
        )
        
        return response.choices[0].message.content
    
    def _parse_phase_a_response(
        self, 
        response: str, 
        ref_paper_id: str,
        suspicious_contexts: List[Dict],
        supporting_contexts: List[Dict]
    ) -> Dict:
        """Parse Phase A LLM response into structured format."""
        
        json_str = None
        
        # Try 1: Extract JSON from markdown code blocks
        if '```json' in response:
            start_marker = '```json'
            end_marker = '```'
            
            start_idx = response.find(start_marker)
            if start_idx != -1:
                start_idx += len(start_marker)
                end_idx = response.find(end_marker, start_idx)
                
                if end_idx != -1:
                    json_str = response[start_idx:end_idx].strip()
        
        # Try 2: Try parsing the response directly as JSON (no markdown)
        if not json_str:
            json_str = response.strip()
        
        # Attempt to parse
        if json_str:
            try:
                parsed = json.loads(json_str)
                # Add required fields
                parsed['reference_paper_id'] = ref_paper_id
                parsed['suspicious_count'] = len(suspicious_contexts)
                parsed['supporting_count'] = len(supporting_contexts)
                logger.info(f"✓ Successfully parsed JSON for {ref_paper_id}")
                return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON for {ref_paper_id}: {e}")
                logger.debug(f"Attempted to parse: {json_str[:200]}...")
        
        # Fallback: return template with FULL raw response (for debugging)
        logger.warning(f"No valid JSON found in response for {ref_paper_id}, using fallback")
        return {
            'reference_paper_id': ref_paper_id,
            'suspicious_count': len(suspicious_contexts),
            'supporting_count': len(supporting_contexts),
            'color_rating': 'MINOR_CONCERN',
            'impact_statement': response,  # Store FULL response for debugging
            'specific_issues': [],
            'consequences': '',
            'sections_affected': []
        }
    
    def _parse_phase_b_response(self, response: str, reference_analyses: List[Dict]) -> Dict:
        """Parse Phase B LLM response into structured format."""
        
        json_str = None
        
        # Try 1: Extract JSON from markdown code blocks
        if '```json' in response:
            start_marker = '```json'
            end_marker = '```'
            
            start_idx = response.find(start_marker)
            if start_idx != -1:
                start_idx += len(start_marker)
                end_idx = response.find(end_marker, start_idx)
                
                if end_idx != -1:
                    json_str = response[start_idx:end_idx].strip()
        
        # Try 2: Try parsing the response directly as JSON (no markdown)
        if not json_str:
            json_str = response.strip()
        
        # Attempt to parse
        if json_str:
            try:
                parsed = json.loads(json_str)
                logger.info("✓ Successfully parsed Phase B JSON")
                return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse Phase B JSON: {e}")
                logger.debug(f"Attempted to parse: {json_str[:200]}...")
        
        # Fallback: return template with FULL raw response (for debugging)
        logger.warning("No valid JSON found in Phase B response, using fallback")
        return {
            'overall_classification': 'MINOR_CONCERN',
            'accumulated_caveats': [],
            'sections_with_issues': {},
            'recommendations_for_reviewers': [],
            'recommendations_for_readers': [],
            'executive_summary': response  # Store FULL response for debugging
        }
    
    def _load_paper_text(self, xml_path: Path) -> str:
        """Load full text from XML paper."""
        # TODO: Implement proper XML text extraction
        # For now, read raw XML
        try:
            return xml_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Error loading {xml_path}: {e}")
            return ""
    
    def _find_reference_paper(self, ref_id: str) -> Optional[Path]:
        """Find the XML file for a reference paper."""
        xml_dir = Path("data/samples")
        
        # Try direct match
        direct = xml_dir / f"elife-{ref_id}.xml"
        if direct.exists():
            return direct
        
        # Try versioned
        for xml_file in xml_dir.glob(f"elife-{ref_id}-v*.xml"):
            return xml_file
        
        return None
