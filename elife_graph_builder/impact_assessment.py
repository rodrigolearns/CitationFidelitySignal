"""
Workflow 5: Impact Assessment & Reporting

Orchestrates the comprehensive two-phase analysis process:

Phase A: Citation Analysis
- Deep reading of full papers (citing + references)
- Assessment of each miscitation's validity and impact

Phase B: Synthesis & Reporting
- Pattern detection across citations
- Comprehensive impact report generation
- Strategic recommendations for reviewers and readers
"""

import logging
from pathlib import Path
from typing import Optional, Dict, List

from .extractors.enhanced_context_extractor import EnhancedContextExtractor
from .matchers.relationship_matcher import RelationshipMatcher
from .classifiers.deep_reading_analyzer import CitationAnalyzer
from .analyzers.impact_analyzer import ImpactSynthesizer
from .graph.neo4j_importer import StreamingNeo4jImporter
from .models import ProblematicPaperAnalysis
from .config import Config

logger = logging.getLogger(__name__)


class ImpactAssessmentWorkflow:
    """Orchestrate Workflow 5: Impact Assessment & Reporting."""
    
    def __init__(
        self,
        use_batch_api: bool = True,
        samples_dir: Optional[Path] = None
    ):
        """
        Initialize workflow.
        
        Args:
            use_batch_api: Use Batch API for Phase B (50% cost savings)
            samples_dir: Directory containing XML files
        """
        self.samples_dir = samples_dir or Config.SAMPLES_DIR
        
        # Initialize components
        self.extractor = EnhancedContextExtractor()
        self.matcher = RelationshipMatcher()
        # Use provider defaults (deepseek-chat or gpt-5.2 based on LLM_PROVIDER env var)
        self.citation_analyzer = CitationAnalyzer(use_caching=True)
        self.impact_synthesizer = ImpactSynthesizer(use_batch_api=use_batch_api)
        self.neo4j = StreamingNeo4jImporter(
            Config.NEO4J_URI,
            Config.NEO4J_USER,
            Config.NEO4J_PASSWORD
        )
        
        # Set up logging with dedicated file
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
    
    def _setup_logging(self):
        """Set up dedicated log file for Workflow 5 that captures ALL components."""
        from datetime import datetime
        
        # Create logs directory if it doesn't exist
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"workflow5_impact_assessment_{timestamp}.log"
        
        # Configure file handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        # Get the ROOT logger for the entire elife_graph_builder package
        # This ensures ALL loggers in this package write to the file
        root_package_logger = logging.getLogger('elife_graph_builder')
        root_package_logger.addHandler(file_handler)
        root_package_logger.setLevel(logging.DEBUG)
        
        # Also add to this specific logger
        self.logger.addHandler(file_handler)
        self.logger.setLevel(logging.DEBUG)
        
        # Write initial log message
        self.logger.info("=" * 80)
        self.logger.info(f"📝 Workflow 5: Impact Assessment - Log Started")
        self.logger.info(f"Log file: {log_file}")
        self.logger.info("=" * 80)
        
        self.log_file = log_file
    
    def analyze_paper(self, article_id: str) -> ProblematicPaperAnalysis:
        """
        Run complete Workflow 5 analysis for a single paper.
        
        Args:
            article_id: Article ID of the problematic paper
        
        Returns:
            ProblematicPaperAnalysis object
        """
        self.logger.info(f"🎯 Workflow 5: Impact Assessment - Starting for article {article_id}")
        
        try:
            # Step 1: Gather enriched data
            data = self._gather_enriched_data(article_id)
            
            if not data:
                raise ValueError(f"Could not gather data for article {article_id}")
            
            # Step 2: Phase A - Citation Analysis
            self.logger.info("📖 Phase A: Citation Analysis - Reading full papers...")
            phase_a_assessments = self.citation_analyzer.analyze(
                data['citing_paper'],
                data['problematic_citations'],
                data['reference_papers']
            )
            
            # Step 3: Phase B - Synthesis & Reporting
            self.logger.info("🔗 Phase B: Synthesis & Reporting - Detecting patterns...")
            phase_b_analysis = self.impact_synthesizer.generate_complete_analysis(
                data['paper_metadata'],
                phase_a_assessments,
                data['problematic_citations']
            )
            
            # Step 4: Package results
            analysis = ProblematicPaperAnalysis(
                article_id=article_id,
                analysis_triggered_at=data['timestamp'],
                citing_paper_metadata=data['paper_metadata'],
                problematic_citations_count=len(data['problematic_citations']),
                total_citations_count=data['total_citations'],
                phase_a_assessments=phase_a_assessments,
                phase_b_analysis=phase_b_analysis,
                overall_classification=phase_b_analysis.overall_classification,
                report_generated_at=data['timestamp'],
                model_used="deepseek-chat/deepseek-reasoner"
            )
            
            # Step 5: Store in Neo4j
            self.logger.info("💾 Storing results in Neo4j...")
            self.neo4j.store_impact_analysis(article_id, analysis.dict())
            
            self.logger.info(f"✅ Workflow 5: Complete - Classification: {analysis.overall_classification}")
            return analysis
            
        except Exception as e:
            self.logger.error(f"Analysis failed for {article_id}: {e}")
            raise
    
    def _gather_enriched_data(self, article_id: str) -> Optional[Dict]:
        """
        Gather all enriched data needed for analysis.
        
        This extracts:
        - Citing paper metadata and relevant sections
        - All problematic citations with context and relationships
        - Reference papers with relevant sections
        
        Returns:
            Dict with all required data
        """
        from datetime import datetime
        
        self.logger.info(f"Gathering data for article {article_id}...")
        
        # Get citing paper XML
        citing_xml = self.samples_dir / f"elife-{article_id}.xml"
        if not citing_xml.exists():
            self.logger.error(f"XML not found: {citing_xml}")
            return None
        
        # Extract citing paper metadata
        citing_metadata = self._extract_paper_metadata(citing_xml)
        
        # Get problematic citations from Neo4j
        problematic_citations = self._get_problematic_citations(article_id)
        
        if not problematic_citations:
            self.logger.warning(f"No problematic citations found for {article_id}")
            return None
        
        # Enrich citation contexts with locations and relationships
        enriched_citations = []
        for citation in problematic_citations:
            enriched = self._enrich_citation_context(citation, citing_xml, citing_metadata)
            if enriched:
                enriched_citations.append(enriched)
        
        # Extract relevant sections from all reference papers
        reference_papers = {}
        for citation in enriched_citations:
            ref_id = citation['target_article_id']
            if ref_id not in reference_papers:
                ref_xml = self.samples_dir / f"elife-{ref_id}.xml"
                if ref_xml.exists():
                    ref_metadata = self._extract_paper_metadata(ref_xml)
                    
                    # Extract only relevant sections (KEY optimization!)
                    # Get citation type from either classification or second_round
                    citation_type = 'UNKNOWN'
                    if 'classification' in citation:
                        citation_type = citation['classification'].get('citation_type', 'UNKNOWN')
                    elif 'second_round' in citation:
                        citation_type = citation['second_round'].get('citation_type', 'UNKNOWN')
                    
                    relevant_sections = self.extractor.extract_relevant_sections(
                        ref_xml,
                        citation['section'],
                        citation_type
                    )
                    
                    reference_papers[ref_id] = {
                        'title': ref_metadata['title'],
                        'sections': relevant_sections
                    }
        
        return {
            'citing_paper': {
                'article_id': article_id,
                'title': citing_metadata['title'],
                'authors': [a['name'] for a in citing_metadata['authors']],
                'doi': citing_metadata.get('doi', ''),
                'sections': self.extractor.extract_full_sections(citing_xml)
            },
            'paper_metadata': {
                'article_id': article_id,
                'title': citing_metadata['title'],
                'authors': [a['name'] for a in citing_metadata['authors']],
                'doi': citing_metadata.get('doi', ''),
                'total_citations': len(problematic_citations)
            },
            'problematic_citations': enriched_citations,
            'reference_papers': reference_papers,
            'total_citations': len(problematic_citations),
            'timestamp': datetime.now().isoformat()
        }
    
    def _extract_paper_metadata(self, xml_path: Path) -> Dict:
        """Extract paper metadata from XML."""
        authors = self.extractor.extract_authors_with_affiliations(xml_path)
        sections = self.extractor.extract_full_sections(xml_path)
        
        return {
            'title': sections.get('Abstract', '')[:100],  # Placeholder
            'authors': authors,
            'doi': '',  # TODO: Extract from XML
            'sections': sections
        }
    
    def _get_problematic_citations(self, article_id: str) -> List[Dict]:
        """Get problematic citations from Neo4j."""
        with self.neo4j.driver.session() as session:
            result = session.run("""
                MATCH (source:Article {article_id: $article_id})-[c:CITES]->(target:Article)
                WHERE c.qualified = true AND c.citation_contexts_json IS NOT NULL
                RETURN target.article_id as target_id,
                       c.citation_contexts_json as contexts_json
            """, article_id=article_id)
            
            problematic = []
            import json
            
            for record in result:
                contexts = json.loads(record['contexts_json'])
                for ctx in contexts:
                    if ctx.get('classification', {}).get('category') in [
                        'NOT_SUBSTANTIATE', 'CONTRADICT', 'OVERSIMPLIFY', 'MISQUOTE'
                    ]:
                        ctx['target_article_id'] = record['target_id']
                        problematic.append(ctx)
            
            return problematic
    
    def _enrich_citation_context(
        self,
        citation: Dict,
        citing_xml: Path,
        citing_metadata: Dict
    ) -> Optional[Dict]:
        """Enrich citation with location and relationship data."""
        # Get citation location (ref_id might be empty, use section as fallback)
        ref_id = citation.get('ref_id', '')
        location = None
        
        if ref_id:
            location = self.extractor.get_citation_location(citing_xml, ref_id)
        
        if not location:
            # If no location found, use section from citation context
            self.logger.warning(f"Could not find detailed location for citation, using section from context")
            location = {
                'section': citation.get('section', 'Unknown'),
                'paragraph_number': 0
            }
        
        # Get reference paper metadata for relationship matching
        ref_id = citation['target_article_id']
        ref_xml = self.samples_dir / f"elife-{ref_id}.xml"
        
        shared_authors = []
        shared_affiliations = []
        is_self_citation = False
        is_same_institution = False
        
        if ref_xml.exists():
            ref_authors = self.extractor.extract_authors_with_affiliations(ref_xml)
            
            # Check relationships
            is_self_citation, shared_authors = self.matcher.is_self_citation(
                citing_metadata['authors'],
                ref_authors
            )
            
            is_same_institution, shared_affiliations = self.matcher.is_same_institution(
                citing_metadata['authors'],
                ref_authors
            )
        
        # Extract full paragraph and surrounding context from citing XML
        full_paragraph = ""
        surrounding_context = ""
        
        try:
            # Get all text from the section where citation appears
            citing_sections = self.extractor.extract_full_sections(citing_xml)
            section_text = citing_sections.get(location['section'], '')
            
            if section_text:
                # For now, use the first ~1000 chars from the section as "full paragraph"
                # and ~2000 chars as "surrounding context"
                # TODO: Improve this to extract actual paragraphs using paragraph_number
                full_paragraph = section_text[:1000]
                surrounding_context = section_text[:2000]
        except Exception as e:
            self.logger.warning(f"Could not extract full paragraph: {e}")
            # Fallback to context_text
            full_paragraph = citation.get('context_text', '')
            surrounding_context = citation.get('context_text', '')
        
        # Combine all enriched data
        enriched = {
            **citation,
            **location,
            'full_paragraph': full_paragraph,
            'surrounding_context': surrounding_context,
            'shared_authors': shared_authors,
            'shared_affiliations': shared_affiliations,
            'is_self_citation': is_self_citation,
            'is_same_institution': is_same_institution,
            'citation_age_years': 0.0  # TODO: Calculate from publication dates
        }
        
        return enriched
    
    def close(self):
        """Close connections."""
        self.neo4j.close()
