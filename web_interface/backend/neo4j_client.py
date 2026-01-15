"""Neo4j client for fetching citation qualification data."""
import json
from typing import List, Dict, Optional
from neo4j import GraphDatabase


class Neo4jClient:
    """Client for querying Neo4j citation data."""
    
    def __init__(self, uri: str = "bolt://localhost:7687", 
                 user: str = "neo4j", 
                 password: str = "elifecitations2024"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        """Close the Neo4j driver."""
        self.driver.close()
    
    def _aggregate_second_round_data(self, contexts: List[Dict]) -> Optional[Dict]:
        """
        Aggregate second-round classifications across all contexts.
        
        Returns the most concerning classification using priority hierarchy:
        MISREPRESENTATION > NEEDS_REVIEW > ACCURATE
        
        Args:
            contexts: List of citation context dictionaries
            
        Returns:
            Dictionary with aggregated second-round data, or None if no second-round data exists
        """
        if not contexts:
            return None
        
        # Collect all second-round classifications
        second_round_contexts = []
        for ctx in contexts:
            if 'second_round' in ctx and ctx['second_round']:
                second_round_contexts.append({
                    'instance_id': ctx.get('instance_id'),
                    'section': ctx.get('section'),
                    'category': ctx['second_round'].get('category'),
                    'recommendation': ctx['second_round'].get('recommendation', 'NEEDS_REVIEW'),
                    'determination': ctx['second_round'].get('determination'),
                    'confidence': ctx['second_round'].get('confidence', 0.0),
                    'user_overview': ctx['second_round'].get('user_overview', '')
                })
        
        if not second_round_contexts:
            return None
        
        # Define priority order (higher number = more concerning)
        recommendation_priority = {
            'MISREPRESENTATION': 3,
            'NEEDS_REVIEW': 2,
            'ACCURATE': 1
        }
        
        # Find worst-case classification
        worst_context = max(
            second_round_contexts,
            key=lambda c: (
                recommendation_priority.get(c['recommendation'], 0),
                -c['confidence']  # Lower confidence = more concerning (secondary sort)
            )
        )
        
        # Count by recommendation
        accurate_count = sum(1 for c in second_round_contexts if c['recommendation'] == 'ACCURATE')
        needs_review_count = sum(1 for c in second_round_contexts if c['recommendation'] == 'NEEDS_REVIEW')
        misrepresentation_count = sum(1 for c in second_round_contexts if c['recommendation'] == 'MISREPRESENTATION')
        
        # Count by determination
        confirmed_count = sum(1 for c in second_round_contexts if c['determination'] == 'CONFIRMED')
        corrected_count = sum(1 for c in second_round_contexts if c['determination'] == 'CORRECTED')
        
        return {
            'has_second_round': True,
            'total_contexts': len(contexts),
            'contexts_with_second_round': len(second_round_contexts),
            
            # Worst case (most concerning)
            'worst_recommendation': worst_context['recommendation'],
            'worst_category': worst_context['category'],
            'worst_instance_id': worst_context['instance_id'],
            'worst_section': worst_context['section'],
            'worst_user_overview': worst_context['user_overview'],
            'worst_confidence': worst_context['confidence'],
            
            # Counts by recommendation
            'accurate_count': accurate_count,
            'needs_review_count': needs_review_count,
            'misrepresentation_count': misrepresentation_count,
            
            # Counts by determination
            'confirmed_count': confirmed_count,
            'corrected_count': corrected_count,
            
            # All contexts for detail view
            'all_second_round': second_round_contexts
        }
    
    def get_qualified_citations(self) -> List[Dict]:
        """
        Get all qualified citations with metadata and classifications.
        
        Returns:
            List of citation dictionaries with source/target metadata and classifications.
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (source:Article)-[c:CITES]->(target:Article)
                WHERE c.qualified = true
                RETURN 
                    source.article_id as source_id,
                    source.doi as source_doi,
                    source.title as source_title,
                    source.pub_year as source_year,
                    source.authors as source_authors,
                    target.article_id as target_id,
                    target.doi as target_doi,
                    target.title as target_title,
                    target.pub_year as target_year,
                    target.authors as target_authors,
                    c.reference_id as reference_id,
                    c.context_count as context_count,
                    c.qualified_at as qualified_at,
                    c.classified as classified,
                    c.citation_contexts_json as contexts_json
                ORDER BY c.qualified_at DESC
            """)
            
            citations = []
            for record in result:
                # Extract classification data from contexts
                classification = None
                second_round_classification = None
                second_round_determination = None
                second_round_recommendation = None
                manually_reviewed = False
                second_round_summary = None
                
                if record["contexts_json"]:
                    try:
                        contexts = json.loads(record["contexts_json"])
                        if contexts and len(contexts) > 0:
                            # Check if this citation has evidence
                            has_evidence = any(
                                ctx.get('evidence_segments') and len(ctx.get('evidence_segments', [])) > 0
                                for ctx in contexts
                            )
                            
                            if not has_evidence:
                                # Mark as INCOMPLETE_REFERENCE_DATA if no evidence found
                                classification = "INCOMPLETE_REFERENCE_DATA"
                            else:
                                # Use first context's classification as primary (backward compatibility)
                                first_ctx = contexts[0]
                                if 'classification' in first_ctx and first_ctx['classification']:
                                    classification = first_ctx['classification'].get('category')
                                    manually_reviewed = first_ctx['classification'].get('manually_reviewed', False)
                                
                                # NEW: Aggregate second-round data across ALL contexts
                                second_round_summary = self._aggregate_second_round_data(contexts)
                                
                                if second_round_summary:
                                    # Set backward-compatible fields to worst case
                                    second_round_classification = second_round_summary['worst_category']
                                    second_round_recommendation = second_round_summary['worst_recommendation']
                                    # Overall determination: CORRECTED if any were corrected
                                    second_round_determination = (
                                        'CORRECTED' if second_round_summary['corrected_count'] > 0 else 'CONFIRMED'
                                    )
                    except Exception as e:
                        print(f"Error parsing contexts: {e}")
                
                citation_data = {
                    "source_id": record["source_id"],
                    "source_doi": record["source_doi"],
                    "source_title": record["source_title"],
                    "source_year": record["source_year"],
                    "source_authors": record["source_authors"],
                    "target_id": record["target_id"],
                    "target_doi": record["target_doi"],
                    "target_title": record["target_title"],
                    "target_year": record["target_year"],
                    "target_authors": record["target_authors"],
                    "reference_id": record["reference_id"],
                    "context_count": record["context_count"],
                    "qualified_at": str(record["qualified_at"]) if record["qualified_at"] else None,
                    "classified": bool(record.get("classified")),
                    "classification": classification,
                    "second_round_classification": second_round_classification,
                    "second_round_determination": second_round_determination,
                    "second_round_recommendation": second_round_recommendation,
                    "manually_reviewed": manually_reviewed,
                    "second_round_summary": second_round_summary
                }
                
                citations.append(citation_data)
            
            return citations
    
    def get_citation_detail(self, source_id: str, target_id: str) -> Optional[Dict]:
        """
        Get detailed citation data including contexts and evidence.
        
        Args:
            source_id: Source article ID
            target_id: Target article ID
            
        Returns:
            Dictionary with full citation data including contexts and evidence segments.
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (source:Article)-[c:CITES]->(target:Article)
                WHERE source.article_id = $source_id 
                  AND target.article_id = $target_id
                  AND c.qualified = true
                RETURN 
                    source.article_id as source_id,
                    source.doi as source_doi,
                    source.title as source_title,
                    source.pub_date as source_date,
                    target.article_id as target_id,
                    target.doi as target_doi,
                    target.title as target_title,
                    target.pub_date as target_date,
                    c.reference_id as reference_id,
                    c.context_count as context_count,
                    c.citation_contexts_json as contexts_json,
                    c.qualified_at as qualified_at
                LIMIT 1
            """, source_id=source_id, target_id=target_id)
            
            record = result.single()
            if not record:
                return None
            
            # Parse the JSON string containing contexts and evidence
            contexts_data = []
            second_round_summary = None
            
            if record["contexts_json"]:
                try:
                    contexts_data = json.loads(record["contexts_json"])
                    # Generate second-round summary if contexts have second-round data
                    if contexts_data:
                        second_round_summary = self._aggregate_second_round_data(contexts_data)
                except json.JSONDecodeError:
                    contexts_data = []
            
            return {
                "source": {
                    "id": record["source_id"],
                    "doi": record["source_doi"],
                    "title": record["source_title"],
                    "date": record["source_date"]
                },
                "target": {
                    "id": record["target_id"],
                    "doi": record["target_doi"],
                    "title": record["target_title"],
                    "date": record["target_date"]
                },
                "reference_id": record["reference_id"],
                "context_count": record["context_count"],
                "contexts": contexts_data,
                "qualified_at": str(record["qualified_at"]) if record["qualified_at"] else None,
                "second_round_summary": second_round_summary
            }
    
    def get_stats(self) -> Dict:
        """Get overall statistics."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH ()-[c:CITES]->()
                WHERE c.qualified = true
                RETURN 
                    count(c) as qualified_citations,
                    sum(c.context_count) as total_contexts
            """)
            
            record = result.single()
            
            # Get classification stats
            class_result = session.run("""
                MATCH ()-[c:CITES]->()
                WHERE c.classified = true
                RETURN count(c) as classified_count
            """)
            class_record = class_result.single()
            
            return {
                "qualified_citations": record["qualified_citations"],
                "total_contexts": record["total_contexts"],
                "classified_citations": class_record["classified_count"] if class_record else 0
            }
    
    def update_review_status(
        self,
        source_id: str,
        target_id: str,
        reviewed: bool
    ) -> bool:
        """Update manual review status for a citation."""
        with self.driver.session() as session:
            # Load current contexts
            result = session.run("""
                MATCH (source:Article {article_id: $source_id})
                      -[c:CITES]->
                      (target:Article {article_id: $target_id})
                RETURN c.citation_contexts_json as contexts_json
            """, source_id=source_id, target_id=target_id)
            
            record = result.single()
            if not record or not record['contexts_json']:
                return False
            
            # Parse and update
            contexts = json.loads(record['contexts_json'])
            for ctx in contexts:
                if 'classification' not in ctx:
                    ctx['classification'] = {}
                ctx['classification']['manually_reviewed'] = reviewed
            
            # Save back
            session.run("""
                MATCH (source:Article {article_id: $source_id})
                      -[c:CITES]->
                      (target:Article {article_id: $target_id})
                SET c.citation_contexts_json = $contexts_json
            """, 
                source_id=source_id,
                target_id=target_id,
                contexts_json=json.dumps(contexts)
            )
            
            return True
    
    def update_user_classification(
        self,
        source_id: str,
        target_id: str,
        instance_id: int,
        user_classification: str
    ) -> bool:
        """Update user's classification override for a specific context."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (source:Article {article_id: $source_id})
                      -[c:CITES]->
                      (target:Article {article_id: $target_id})
                RETURN c.citation_contexts_json as contexts_json
            """, source_id=source_id, target_id=target_id)
            
            record = result.single()
            if not record or not record['contexts_json']:
                return False
            
            contexts = json.loads(record['contexts_json'])
            for ctx in contexts:
                if ctx.get('instance_id') == instance_id:
                    if 'classification' not in ctx:
                        ctx['classification'] = {}
                    ctx['classification']['user_classification'] = user_classification
                    break
            
            session.run("""
                MATCH (source:Article {article_id: $source_id})
                      -[c:CITES]->
                      (target:Article {article_id: $target_id})
                SET c.citation_contexts_json = $contexts_json
            """,
                source_id=source_id,
                target_id=target_id,
                contexts_json=json.dumps(contexts)
            )
            
            return True
    
    def update_user_comment(
        self,
        source_id: str,
        target_id: str,
        instance_id: int,
        comment: str
    ) -> bool:
        """Update user's comment for a specific context."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (source:Article {article_id: $source_id})
                      -[c:CITES]->
                      (target:Article {article_id: $target_id})
                RETURN c.citation_contexts_json as contexts_json
            """, source_id=source_id, target_id=target_id)
            
            record = result.single()
            if not record or not record['contexts_json']:
                return False
            
            contexts = json.loads(record['contexts_json'])
            for ctx in contexts:
                if ctx.get('instance_id') == instance_id:
                    if 'classification' not in ctx:
                        ctx['classification'] = {}
                    ctx['classification']['user_comment'] = comment
                    break
            
            session.run("""
                MATCH (source:Article {article_id: $source_id})
                      -[c:CITES]->
                      (target:Article {article_id: $target_id})
                SET c.citation_contexts_json = $contexts_json
            """,
                source_id=source_id,
                target_id=target_id,
                contexts_json=json.dumps(contexts)
            )
            
            return True
    
    def get_problematic_papers(self) -> List[Dict]:
        """
        Get list of papers with multiple problematic citations.
        
        Returns:
            List of papers sorted by number of problematic citations, 
            including Workflow 5 impact assessment status.
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (source:Article)-[c:CITES]->(target:Article)
                WHERE c.qualified = true AND c.citation_contexts_json IS NOT NULL
                RETURN source.article_id as article_id,
                       source.title as title,
                       source.doi as doi,
                       source.authors as authors,
                       source.impact_classification as impact_classification,
                       c.citation_contexts_json as contexts_json
            """)
            
            # Count problematic citations per paper
            from collections import Counter
            problematic_counts = Counter()
            paper_details = {}
            
            for record in result:
                article_id = record['article_id']
                contexts = json.loads(record['contexts_json'])
                
                # Count NOT_SUBSTANTIATE, CONTRADICT, MISQUOTE
                problematic = 0
                for context in contexts:
                    if context.get('classification'):
                        classif = context['classification']
                        if isinstance(classif, dict):
                            category = classif.get('category', '')
                            if category in ['NOT_SUBSTANTIATE', 'CONTRADICT', 'MISQUOTE']:
                                problematic += 1
                
                if problematic > 0:
                    problematic_counts[article_id] += problematic
                    if article_id not in paper_details:
                        paper_details[article_id] = {
                            'article_id': article_id,
                            'title': record['title'],
                            'doi': record['doi'],
                            'authors': record['authors'][:3] if record['authors'] else [],  # First 3 authors
                            'problematic_count': 0,
                            'impact_assessment': record.get('impact_classification') or 'NOT_PERFORMED'
                        }
                    paper_details[article_id]['problematic_count'] += problematic
            
            # Filter for repeat offenders (≥2 problematic citations) and sort
            problematic_papers = [
                paper_details[pid] 
                for pid, count in problematic_counts.items() 
                if count >= 2
            ]
            
            # Sort by impact assessment (more damning first), then by problematic count
            impact_priority = {
                'CRITICAL_CONCERN': 0,
                'MODERATE_CONCERN': 1,
                'MINOR_CONCERN': 2,
                'FALSE_ALARM': 3,
                'NOT_PERFORMED': 4
            }
            
            problematic_papers.sort(
                key=lambda x: (
                    impact_priority.get(x['impact_assessment'], 5),  # Unknown assessments go last
                    -x['problematic_count']  # Higher problematic count first within category
                )
            )
            
            return problematic_papers
    
    # ============================================================================
    # Workflow 5: Impact Assessment Methods
    # ============================================================================
    
    def get_problematic_paper_detail(self, article_id: str) -> Optional[Dict]:
        """
        Get detailed information about a problematic paper.
        
        Args:
            article_id: Article ID of the problematic citing paper
        
        Returns:
            Dict with paper metadata, all citations, and impact analysis (if available)
        """
        with self.driver.session() as session:
            # Get paper metadata
            result = session.run("""
                MATCH (a:Article {article_id: $article_id})
                RETURN a.title as title,
                       a.doi as doi,
                       a.authors as authors,
                       a.pub_year as pub_year,
                       a.impact_analysis_json as impact_analysis,
                       a.impact_classification as impact_classification,
                       a.analyzed_at as analyzed_at
            """, article_id=article_id)
            
            record = result.single()
            if not record:
                return None
            
            paper_metadata = {
                'article_id': article_id,
                'title': record['title'],
                'doi': record['doi'],
                'authors': record['authors'] or [],
                'pub_year': record['pub_year'],
                'impact_analysis': json.loads(record['impact_analysis']) if record['impact_analysis'] else None,
                'impact_classification': record['impact_classification'],
                'analyzed_at': record['analyzed_at']
            }
            
            # Enrich severity assessment with section information
            if paper_metadata['impact_analysis']:
                self._enrich_severity_assessment(paper_metadata['impact_analysis'])
            
            # Get all problematic citations
            result = session.run("""
                MATCH (source:Article {article_id: $article_id})-[c:CITES]->(target:Article)
                WHERE c.qualified = true
                RETURN target.article_id as target_id,
                       target.title as target_title,
                       target.doi as target_doi,
                       target.authors as target_authors,
                       target.pub_year as target_year,
                       c.citation_contexts_json as contexts_json,
                       c.context_count as context_count
                ORDER BY target.article_id
            """, article_id=article_id)
            
            problematic_citations = []
            
            for record in result:
                contexts = json.loads(record['contexts_json']) if record['contexts_json'] else []
                
                # Extract problematic contexts and flatten them
                for ctx in contexts:
                    classification_data = ctx.get('classification', {})
                    classification = classification_data.get('category', 'UNKNOWN')
                    
                    # Only include problematic classifications
                    if classification in ['NOT_SUBSTANTIATE', 'CONTRADICT', 'OVERSIMPLIFY', 'MISQUOTE']:
                        problematic_citations.append({
                            'target_id': record['target_id'],
                            'target_title': record['target_title'],
                            'target_doi': record['target_doi'],
                            'target_authors': record['target_authors'],
                            'target_year': record['target_year'],
                            'classification': classification,
                            'context': ctx.get('context_text', 'No context available'),
                            'justification': classification_data.get('justification', 'No justification provided'),
                            'second_round': ctx.get('second_round', {})
                        })
            
            paper_metadata['problematic_citations'] = problematic_citations
            
            return paper_metadata
    
    def store_impact_analysis(
        self,
        article_id: str,
        analysis: Dict
    ) -> bool:
        """
        Store Workflow 5 impact analysis results in Neo4j.
        
        Args:
            article_id: Article ID
            analysis: ProblematicPaperAnalysis dict
        
        Returns:
            True if successful
        """
        with self.driver.session() as session:
            from datetime import datetime
            
            session.run("""
                MATCH (a:Article {article_id: $article_id})
                SET a.impact_analysis_json = $analysis_json,
                    a.impact_classification = $classification,
                    a.analyzed_at = datetime($timestamp)
            """,
                article_id=article_id,
                analysis_json=json.dumps(analysis),
                classification=analysis.get('overall_classification', 'UNKNOWN'),
                timestamp=datetime.now().isoformat()
            )
            
            return True
    
    def _normalize_section_name(self, section_title: str) -> str:
        """Normalize section titles to standard categories (Introduction, Methods, Results, Discussion)."""
        if not section_title:
            return 'Unknown'
        
        section_lower = section_title.lower().strip()
        
        # Check for explicit main section names (case-insensitive exact match first)
        main_sections = {
            'introduction': 'Introduction',
            'methods': 'Methods',
            'materials and methods': 'Methods',
            'results': 'Results',
            'results and discussion': 'Results',  # Often combined
            'discussion': 'Discussion',
            'conclusions': 'Discussion',
            'abstract': 'Abstract'
        }
        
        # Exact match first
        if section_lower in main_sections:
            return main_sections[section_lower]
        
        # Check for main section as prefix (e.g., "Methods (subsection)" or "Methods: details")
        for key, value in main_sections.items():
            if section_lower.startswith(key + ' (') or section_lower.startswith(key + ':') or section_lower.startswith(key + ' -'):
                return value
        
        # Map to standard sections by keyword matching (broader patterns)
        if any(kw in section_lower for kw in ['introduction', 'background', 'overview']):
            return 'Introduction'
        elif any(kw in section_lower for kw in ['method', 'material', 'experimental', 'procedure', 'approach', 'technique']):
            return 'Methods'
        elif any(kw in section_lower for kw in ['result', 'finding', 'observation', 'data', 'analysis', 'measurement']):
            return 'Results'
        elif any(kw in section_lower for kw in ['discussion', 'conclusion', 'implication', 'interpretation', 'summary']):
            return 'Discussion'
        elif 'abstract' in section_lower:
            return 'Abstract'
        else:
            # Unable to determine - return Unknown
            return 'Unknown'
    
    def _enrich_severity_assessment(self, impact_analysis: dict) -> None:
        """
        Enrich severity assessment with section information by mapping citation indices
        to their sections from phase_a_assessments.
        
        Note: The severity assessment uses 1-based indices to reference citations
        in the phase_a_assessments array (citation #1 = index 0, etc.)
        
        Modifies the impact_analysis dict in place.
        """
        if not impact_analysis:
            return
        
        # Get phase_a_assessments
        phase_a = impact_analysis.get('phase_a_assessments', [])
        if not phase_a:
            return
        
        # Build mapping of citation number (1-based) -> normalized section
        # The LLM references citations by their position in the array (1, 2, 3, ...)
        citation_sections = {}
        for idx, assessment in enumerate(phase_a):
            citation_number = idx + 1  # Convert 0-based index to 1-based number
            raw_section = assessment.get('citation_role', {}).get('section', 'Unknown')
            # Normalize to main sections (Introduction, Methods, Results, Discussion)
            normalized_section = self._normalize_section_name(raw_section)
            citation_sections[citation_number] = normalized_section
        
        # Enrich severity assessment
        phase_b = impact_analysis.get('phase_b_analysis', {})
        pattern_analysis = phase_b.get('pattern_analysis', {})
        severity = pattern_analysis.get('severity_assessment', {})
        
        if severity:
            # Enrich each severity list with section information
            for severity_level in ['high_impact_citations', 'moderate_impact_citations', 'low_impact_citations']:
                if severity_level in severity:
                    citation_numbers = severity[severity_level]
                    if isinstance(citation_numbers, list):
                        # Convert from list of numbers to list of objects with number and normalized section
                        severity[severity_level] = [
                            {
                                'citation_id': num,
                                'section': citation_sections.get(num, 'Unknown')
                            }
                            for num in citation_numbers
                        ]
    
    def get_papers_needing_analysis(self, limit: int = 10) -> List[str]:
        """
        Get article IDs of problematic papers that don't have impact analysis yet.
        
        Args:
            limit: Maximum number of article IDs to return
        
        Returns:
            List of article IDs
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (a:Article)
                WHERE a.impact_analysis_json IS NULL
                  AND EXISTS {
                    MATCH (a)-[c:CITES]->()
                    WHERE c.qualified = true AND c.citation_contexts_json IS NOT NULL
                    WITH c, c.citation_contexts_json as contexts_json
                    WITH json.parse(contexts_json) as contexts
                    UNWIND contexts as context
                    WHERE context.classification.category IN ['NOT_SUBSTANTIATE', 'CONTRADICT', 'OVERSIMPLIFY', 'MISQUOTE']
                    RETURN count(context) as problematic_count
                    WHERE problematic_count >= 2
                  }
                RETURN a.article_id as article_id
                LIMIT $limit
            """, limit=limit)
            
            return [record['article_id'] for record in result]
