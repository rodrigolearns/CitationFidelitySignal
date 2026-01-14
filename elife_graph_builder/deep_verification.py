"""
Final Determination Pipeline for second-round citation classification.

Performs in-depth verification of suspicious citations using expanded evidence.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

from .classifiers.second_round_classifier import SecondRoundClassifier
from .retrievers.enhanced_retriever import EnhancedEvidenceRetriever
from .retrievers.type_aware_retriever import TypeAwareEnhancedRetriever
from .graph.neo4j_importer import StreamingNeo4jImporter
from .models import SecondRoundClassification
from .utils.logging_config import setup_logging

# Setup logging to both console and file
logger = setup_logging('final_determination')


# Categories that trigger second-round review
SUSPICIOUS_CATEGORIES = [
    'CONTRADICT',
    'NOT_SUBSTANTIATE',
    'OVERSIMPLIFY',
    'IRRELEVANT',
    'MISQUOTE'
]


class FinalDeterminationPipeline:
    """
    Orchestrates second-round classification for suspicious citations.
    
    Process:
    1. Fetch suspicious citations from Neo4j
    2. Load XML files for source and target articles
    3. Retrieve enhanced evidence (abstract + 15 segments)
    4. Classify with SecondRoundClassifier (GPT-4o)
    5. Store results in Neo4j
    """
    
    def __init__(
        self,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "elifecitations2024"
    ):
        """Initialize pipeline components."""
        self.neo4j = StreamingNeo4jImporter(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password
        )
        self.evidence_retriever = EnhancedEvidenceRetriever()
        self.type_aware_retriever = TypeAwareEnhancedRetriever()
        self.classifier = SecondRoundClassifier()
        
        logger.info("✅ FinalDeterminationPipeline initialized (with type-aware retrieval)")
    
    def _get_suspicious_citations(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Fetch citations that need second-round review from Neo4j.
        
        Args:
            limit: Maximum number to fetch
            
        Returns:
            List of citation dictionaries
        """
        query = """
            MATCH (source:Article)-[c:CITES]->(target:Article)
            WHERE c.qualified = true
              AND c.citation_contexts_json IS NOT NULL
              AND c.classified = true
            RETURN source.article_id as source_id,
                   target.article_id as target_id,
                   source.title as source_title,
                   target.title as target_title,
                   c.reference_id as reference_id,
                   c.citation_contexts_json as contexts_json
            ORDER BY source.pub_year DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        with self.neo4j.driver.session() as session:
            result = session.run(query)
            all_citations = [dict(record) for record in result]
        
        # Filter for suspicious categories only
        suspicious = []
        for citation in all_citations:
            try:
                contexts = json.loads(citation['contexts_json'])
                if contexts and len(contexts) > 0:
                    first_ctx = contexts[0]
                    
                    # Check if already has second_round
                    if first_ctx.get('second_round'):
                        logger.debug(f"Skipping {citation['source_id']}→{citation['target_id']} (already has second round)")
                        continue
                    
                    # Check if classified as suspicious
                    if 'classification' in first_ctx and first_ctx['classification']:
                        category = first_ctx['classification'].get('category')
                        if category in SUSPICIOUS_CATEGORIES:
                            suspicious.append(citation)
                        else:
                            logger.debug(f"Skipping {citation['source_id']}→{citation['target_id']} (category: {category})")
            except Exception as e:
                logger.error(f"Error parsing contexts for {citation.get('source_id')}: {e}")
        
        logger.info(f"Found {len(suspicious)} suspicious citations for second-round review")
        return suspicious
    
    def _get_article_xml(self, article_id: str) -> Optional[str]:
        """
        Load XML content for an article.
        
        Args:
            article_id: Article ID (e.g., "100851")
            
        Returns:
            XML content string, or None if not found
        """
        # Search in data/samples and data/raw_xml
        search_dirs = [
            Path("data/samples"),
            Path("data/raw_xml")
        ]
        
        for base_dir in search_dirs:
            if not base_dir.exists():
                continue
            
            # Try different version patterns
            for version in range(1, 10):  # Try versions 1-9
                xml_file = base_dir / f"elife-{article_id}-v{version}.xml"
                if xml_file.exists():
                    logger.debug(f"Found XML: {xml_file}")
                    return xml_file.read_text(encoding='utf-8')
            
            # Try without version
            xml_file = base_dir / f"elife-{article_id}.xml"
            if xml_file.exists():
                logger.debug(f"Found XML: {xml_file}")
                return xml_file.read_text(encoding='utf-8')
        
        logger.warning(f"XML not found for article {article_id}")
        return None
    
    def process_citation(
        self,
        source_id: str,
        target_id: str,
        reference_id: str,
        contexts_json_str: str
    ) -> bool:
        """
        Process a single suspicious citation with second-round classification.
        
        Args:
            source_id: Source article ID
            target_id: Target article ID
            reference_id: Reference ID
            contexts_json_str: JSON string of citation contexts
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"\n📦 Processing citation: {source_id} → {target_id}")
        
        try:
            # Parse contexts
            contexts = json.loads(contexts_json_str)
            if not contexts or len(contexts) == 0:
                logger.warning("No contexts found")
                return False
            
            # Load target article XML once for all contexts
            target_xml = self._get_article_xml(target_id)
            if not target_xml:
                logger.error(f"Could not load XML for target article {target_id}")
                return False
            
            # Process each context that needs second-round review
            contexts_processed = 0
            for ctx in contexts:
                # Check if has first-round classification
                if 'classification' not in ctx or not ctx['classification']:
                    logger.debug(f"Context {ctx.get('instance_id')} has no first-round classification")
                    continue
                
                # Check if already has second_round
                if ctx.get('second_round'):
                    logger.debug(f"Context {ctx.get('instance_id')} already has second round")
                    continue
                
                first_round = ctx['classification']
                first_category = first_round.get('category')
                first_confidence = first_round.get('confidence', 0.0)
                first_justification = first_round.get('justification', '')
                citation_type = first_round.get('citation_type', 'UNKNOWN')
                
                # Check if this is a suspicious category
                if first_category not in SUSPICIOUS_CATEGORIES:
                    logger.debug(f"Context {ctx.get('instance_id')} category {first_category} not suspicious")
                    continue
                
                logger.info(
                    f"   → Processing context {ctx.get('instance_id')} "
                    f"(Type: {citation_type}, Category: {first_category})"
                )
                
                # Retrieve enhanced evidence with type awareness
                logger.info("      • Retrieving enhanced evidence...")
                
                # Use type-aware retrieval if type is known
                if citation_type != 'UNKNOWN':
                    logger.info(f"      • Using type-aware retrieval for {citation_type}")
                    abstract, evidence_segments = self.type_aware_retriever.retrieve_with_abstract(
                        citation_context=ctx['context_text'],
                        reference_xml=target_xml,
                        citation_type=citation_type,
                        top_n=15,
                        min_similarity=0.5
                    )
                else:
                    # Fallback to standard retrieval
                    logger.warning("      • Using standard retrieval (citation_type=UNKNOWN)")
                    abstract, evidence_segments = self.evidence_retriever.retrieve_with_abstract(
                        citation_context=ctx['context_text'],
                        reference_xml=target_xml,
                        top_n=15,
                        min_similarity=0.5
                    )
                
                if not evidence_segments:
                    logger.warning("      • No evidence segments retrieved, skipping")
                    continue
                
                logger.info(f"      • Retrieved {len(evidence_segments)} evidence segments")
                
                # Assess evidence quality
                logger.info("      • Assessing evidence quality...")
                evidence_quality = self.evidence_retriever.assess_evidence_quality(
                    evidence_segments=evidence_segments,
                    citation_context=ctx['context_text']
                )
                logger.info(
                    f"      • Quality: {evidence_quality['quality_score']:.2f} "
                    f"({evidence_quality['confidence_level']})"
                )
                
                # Format reference citation (simplified for now)
                reference_citation = f"Article {target_id}"
                
                # Perform second-round classification
                logger.info("      • Classifying with GPT-4o...")
                second_round = self.classifier.classify_with_context(
                    citation_context=ctx['context_text'],
                    section=ctx.get('section', 'Unknown'),
                    reference_citation=reference_citation,
                    abstract=abstract,
                    evidence_segments=evidence_segments,
                    first_round_category=first_category,
                    first_round_confidence=first_confidence,
                    first_round_justification=first_justification
                )
                
                # Add evidence quality to second_round
                second_round.evidence_quality = evidence_quality
                
                # Add second_round to context
                ctx['second_round'] = second_round.dict()
                
                logger.info(
                    f"      ✅ {second_round.determination}: {second_round.category} "
                    f"(confidence: {second_round.confidence:.2f}, recommendation: {second_round.recommendation})"
                )
                
                contexts_processed += 1
            
            if contexts_processed == 0:
                logger.info("   → No contexts needed second-round processing")
                return False
            
            # Update Neo4j with updated contexts JSON
            logger.info(f"   → Storing {contexts_processed} second-round results in Neo4j...")
            contexts_json = json.dumps(contexts)
            
            with self.neo4j.driver.session() as session:
                session.run("""
                    MATCH (s:Article {article_id: $source_id})-[c:CITES]->(t:Article {article_id: $target_id})
                    WHERE c.reference_id = $ref_id
                    SET c.citation_contexts_json = $contexts_json,
                        c.second_round_classified = true
                """, source_id=source_id, target_id=target_id, ref_id=reference_id, contexts_json=contexts_json)
            
            logger.info(f"   ✅ Successfully processed {contexts_processed} contexts")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing citation: {e}", exc_info=True)
            return False
    
    def run(self, batch_size: int = 5):
        """
        Run the final determination pipeline.
        
        Args:
            batch_size: Number of citations to process in this batch
        """
        logger.info("\n" + "=" * 70)
        logger.info("🔬 FINAL FIDELITY DETERMINATION PIPELINE")
        logger.info("=" * 70)
        
        # Fetch suspicious citations
        citations = self._get_suspicious_citations(limit=batch_size)
        
        if not citations:
            logger.info("\n🎉 No suspicious citations found - all clear!")
            return
        
        logger.info(f"\n🚀 Processing {len(citations)} suspicious citations...\n")
        
        # Process each citation
        stats = {
            'processed': 0,
            'failed': 0,
            'confirmed': 0,
            'corrected': 0
        }
        
        for i, citation in enumerate(citations, 1):
            logger.info(f"\n[{i}/{len(citations)}]")
            
            success = self.process_citation(
                source_id=citation['source_id'],
                target_id=citation['target_id'],
                reference_id=citation['reference_id'],
                contexts_json_str=citation['contexts_json']
            )
            
            if success:
                stats['processed'] += 1
                # Parse to get determination
                try:
                    contexts = json.loads(citation['contexts_json'])
                    if contexts[0].get('second_round'):
                        determ = contexts[0]['second_round'].get('determination', 'CONFIRMED')
                        if determ == 'CONFIRMED':
                            stats['confirmed'] += 1
                        else:
                            stats['corrected'] += 1
                except:
                    pass
            else:
                stats['failed'] += 1
        
        # Final summary
        logger.info("\n" + "=" * 70)
        logger.info("🎉 FINAL DETERMINATION COMPLETE!")
        logger.info("=" * 70)
        logger.info(f"Total citations: {len(citations)}")
        logger.info(f"✅ Processed: {stats['processed']}")
        logger.info(f"❌ Failed: {stats['failed']}")
        logger.info(f"   ✓ Confirmed: {stats['confirmed']}")
        logger.info(f"   ⚠ Corrected: {stats['corrected']}")
        logger.info("=" * 70)
        
        if stats['corrected'] > 0:
            correction_rate = (stats['corrected'] / stats['processed']) * 100 if stats['processed'] > 0 else 0
            logger.info(f"\n📊 Correction Rate: {correction_rate:.1f}%")
            logger.info("(Indicates how often expanded evidence changed the classification)\n")
