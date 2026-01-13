"""Parallel parser for high-performance XML processing."""

from multiprocessing import Pool, cpu_count
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Tuple
import logging
from tqdm import tqdm

from .jats_parser import JATSParser
from ..models import ArticleMetadata, Reference, CitationAnchor

logger = logging.getLogger(__name__)


class ParallelParser:
    """
    High-performance parallel parser using multiprocessing.
    
    Uses all CPU cores to parse multiple articles simultaneously.
    """
    
    def __init__(self, num_workers: Optional[int] = None):
        """
        Initialize parallel parser.
        
        Args:
            num_workers: Number of worker processes (default: CPU count - 1)
        """
        if num_workers is None:
            self.num_workers = max(1, cpu_count() - 1)
        else:
            self.num_workers = num_workers
        
        logger.info(f"Parallel parser initialized with {self.num_workers} workers")
    
    def parse_batch_multiprocessing(
        self,
        xml_files: List[Path],
        show_progress: bool = True
    ) -> List[Tuple[ArticleMetadata, List[Reference], List[CitationAnchor]]]:
        """
        Parse multiple XML files using multiprocessing.
        
        Best for CPU-bound parsing operations.
        
        Args:
            xml_files: List of paths to XML files
            show_progress: Show progress bar
        
        Returns:
            List of (metadata, references, anchors) tuples
        """
        logger.info(f"Parsing {len(xml_files)} articles with {self.num_workers} processes...")
        
        # Create parser instance (will be recreated in each process)
        def parse_one(xml_path):
            parser = JATSParser()
            return parser.parse_file(xml_path)
        
        results = []
        
        with Pool(self.num_workers) as pool:
            # Use imap for progress tracking
            if show_progress:
                iterator = tqdm(
                    pool.imap(parse_one, xml_files, chunksize=10),
                    total=len(xml_files),
                    desc="Parsing",
                    unit="articles"
                )
            else:
                iterator = pool.imap(parse_one, xml_files, chunksize=10)
            
            for result in iterator:
                if result is not None:
                    results.append(result)
        
        success_rate = len(results) / len(xml_files) * 100 if xml_files else 0
        logger.info(f"✅ Parsed {len(results)}/{len(xml_files)} articles ({success_rate:.1f}% success)")
        
        return results
    
    def parse_batch_threading(
        self,
        xml_files: List[Path],
        show_progress: bool = True
    ) -> List[Tuple[ArticleMetadata, List[Reference], List[CitationAnchor]]]:
        """
        Parse multiple XML files using threading.
        
        Better for I/O-bound operations (reading files from disk).
        Often faster than multiprocessing for file I/O.
        
        Args:
            xml_files: List of paths to XML files
            show_progress: Show progress bar
        
        Returns:
            List of (metadata, references, anchors) tuples
        """
        logger.info(f"Parsing {len(xml_files)} articles with {self.num_workers * 2} threads...")
        
        parser = JATSParser()
        results = []
        
        with ThreadPoolExecutor(max_workers=self.num_workers * 2) as executor:
            # Submit all tasks
            future_to_path = {
                executor.submit(parser.parse_file, xml_path): xml_path
                for xml_path in xml_files
            }
            
            # Process completed tasks with progress bar
            if show_progress:
                iterator = tqdm(
                    as_completed(future_to_path),
                    total=len(xml_files),
                    desc="Parsing",
                    unit="articles"
                )
            else:
                iterator = as_completed(future_to_path)
            
            for future in iterator:
                try:
                    result = future.result()
                    if result is not None:
                        results.append(result)
                except Exception as e:
                    xml_path = future_to_path[future]
                    logger.error(f"Failed to parse {xml_path}: {e}")
        
        success_rate = len(results) / len(xml_files) * 100 if xml_files else 0
        logger.info(f"✅ Parsed {len(results)}/{len(xml_files)} articles ({success_rate:.1f}% success)")
        
        return results
    
    def parse_batch(
        self,
        xml_files: List[Path],
        method: str = "threading",
        show_progress: bool = True
    ) -> List[Tuple[ArticleMetadata, List[Reference], List[CitationAnchor]]]:
        """
        Parse batch with specified method.
        
        Args:
            xml_files: List of paths to XML files
            method: "threading" or "multiprocessing"
            show_progress: Show progress bar
        
        Returns:
            List of parsed results
        """
        if method == "multiprocessing":
            return self.parse_batch_multiprocessing(xml_files, show_progress)
        elif method == "threading":
            return self.parse_batch_threading(xml_files, show_progress)
        else:
            raise ValueError(f"Unknown method: {method}. Use 'threading' or 'multiprocessing'")


def parse_articles_parallel(
    xml_files: List[Path],
    num_workers: Optional[int] = None,
    method: str = "threading"
) -> List[Tuple[ArticleMetadata, List[Reference], List[CitationAnchor]]]:
    """
    Convenience function for parallel parsing.
    
    Args:
        xml_files: List of XML file paths
        num_workers: Number of workers (default: auto)
        method: "threading" or "multiprocessing"
    
    Returns:
        List of parsed articles
    """
    parser = ParallelParser(num_workers)
    return parser.parse_batch(xml_files, method=method)
