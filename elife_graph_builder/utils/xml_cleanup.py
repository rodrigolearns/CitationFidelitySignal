"""Utilities for cleaning up XML files after processing."""

import logging
from pathlib import Path
from typing import List, Set

logger = logging.getLogger(__name__)


def get_articles_without_elife_citations(neo4j_importer) -> Set[str]:
    """
    Get CITING article IDs that have no outgoing CITES edges to other eLife papers.
    
    IMPORTANT: This should ONLY return articles that were meant to be citing articles
    (downloaded from the API) but turned out not to cite any eLife papers.
    
    It should NOT return referenced articles (those cited BY other articles),
    because we need those XMLs for evidence extraction in Parts 2 & 3.
    
    Args:
        neo4j_importer: Neo4jImporter instance with active connection
        
    Returns:
        Set of article IDs with no eLife citations AND no incoming citations
    """
    query = """
    MATCH (a:Article)
    WHERE NOT (a)-[:CITES]->(:Article)
      AND NOT (a)<-[:CITES]-(:Article)
    RETURN a.article_id as article_id
    """
    
    with neo4j_importer.driver.session() as session:
        result = session.run(query)
        return {record['article_id'] for record in result}


def get_all_processed_articles(neo4j_importer) -> Set[str]:
    """
    Get all article IDs in the database.
    
    Args:
        neo4j_importer: Neo4jImporter instance with active connection
        
    Returns:
        Set of all article IDs
    """
    query = """
    MATCH (a:Article)
    RETURN a.article_id as article_id
    """
    
    with neo4j_importer.driver.session() as session:
        result = session.run(query)
        return {record['article_id'] for record in result}


def delete_xml_files(article_ids: Set[str], samples_dir: Path) -> int:
    """
    Delete XML files for specified article IDs.
    
    Args:
        article_ids: Set of article IDs to delete
        samples_dir: Directory containing XML files
        
    Returns:
        Number of files deleted
    """
    if not article_ids:
        logger.info("No XML files to delete")
        return 0
    
    samples_dir = Path(samples_dir)
    deleted_count = 0
    
    for article_id in article_ids:
        # Check for files matching elife-{article_id}-v*.xml pattern
        pattern = f"elife-{article_id}-v*.xml"
        matching_files = list(samples_dir.glob(pattern))
        
        for xml_file in matching_files:
            try:
                xml_file.unlink()
                deleted_count += 1
                logger.debug(f"Deleted: {xml_file.name}")
            except Exception as e:
                logger.warning(f"Failed to delete {xml_file.name}: {e}")
    
    return deleted_count


def cleanup_non_citing_articles(neo4j_importer, samples_dir: Path) -> int:
    """
    Phase 1 cleanup: Remove XMLs for articles that don't cite any eLife papers.
    
    Args:
        neo4j_importer: Neo4jImporter instance
        samples_dir: Directory containing XML files
        
    Returns:
        Number of files deleted
    """
    logger.info("🧹 Phase 1 Cleanup: Identifying articles without eLife citations...")
    
    non_citing = get_articles_without_elife_citations(neo4j_importer)
    
    if not non_citing:
        logger.info("✓ All articles cite at least one eLife paper - no cleanup needed")
        return 0
    
    logger.info(f"Found {len(non_citing)} articles without eLife citations")
    deleted = delete_xml_files(non_citing, samples_dir)
    
    logger.info(f"✅ Phase 1 Cleanup: Deleted {deleted} XML files")
    return deleted


def cleanup_all_xmls(samples_dir: Path) -> int:
    """
    Phase 3 cleanup: Remove ALL XML files after final determination.
    
    Args:
        samples_dir: Directory containing XML files
        
    Returns:
        Number of files deleted
    """
    logger.info("🧹 Phase 3 Cleanup: Removing all XML files...")
    
    samples_dir = Path(samples_dir)
    xml_files = list(samples_dir.glob("elife-*.xml"))
    
    if not xml_files:
        logger.info("✓ No XML files to clean up")
        return 0
    
    deleted_count = 0
    for xml_file in xml_files:
        try:
            xml_file.unlink()
            deleted_count += 1
        except Exception as e:
            logger.warning(f"Failed to delete {xml_file.name}: {e}")
    
    logger.info(f"✅ Phase 3 Cleanup: Deleted {deleted_count} XML files")
    return deleted_count
