"""
Centralized logging configuration with file output.

Usage in scripts:
    from elife_graph_builder.utils.logging_config import setup_logging
    setup_logging('script_name')
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(script_name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Configure logging to write to both console and file.
    
    Args:
        script_name: Name of the script (used for log filename)
        level: Logging level (default: INFO)
        
    Returns:
        Logger instance
    """
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Create log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d")
    log_file = logs_dir / f"{script_name}_{timestamp}.log"
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Format for logs
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Log the start
    logger = logging.getLogger(script_name)
    logger.info(f"=" * 70)
    logger.info(f"Logging initialized: {script_name}")
    logger.info(f"Log file: {log_file}")
    logger.info(f"=" * 70)
    
    return logger
