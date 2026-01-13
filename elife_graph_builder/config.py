"""Configuration management for eLife Graph Builder."""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration."""
    
    # Project paths
    PROJECT_ROOT = Path(__file__).parent.parent
    DATA_DIR = PROJECT_ROOT / "data"
    RAW_XML_DIR = DATA_DIR / "raw_xml"
    SAMPLES_DIR = DATA_DIR / "samples"
    PROCESSED_DIR = DATA_DIR / "processed"
    LOGS_DIR = PROJECT_ROOT / "logs"
    
    # Neo4j configuration
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
    
    # eLife corpus configuration
    ELIFE_DOI_PREFIX = "10.7554/eLife."
    ELIFE_GITHUB_REPO = "https://github.com/elifesciences/elife-article-xml"
    
    # Processing configuration
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))
    CHECKPOINT_INTERVAL = int(os.getenv("CHECKPOINT_INTERVAL", "500"))
    
    @classmethod
    def ensure_directories(cls):
        """Create necessary directories if they don't exist."""
        for directory in [
            cls.DATA_DIR,
            cls.RAW_XML_DIR,
            cls.SAMPLES_DIR,
            cls.PROCESSED_DIR,
            cls.LOGS_DIR,
        ]:
            directory.mkdir(parents=True, exist_ok=True)
