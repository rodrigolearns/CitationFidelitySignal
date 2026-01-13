"""Track processing progress for resumable pipeline."""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Set


class ProgressTracker:
    """
    Tracks which articles have been processed.
    
    Orders articles by publication date (newest first).
    Allows resuming with "continue processing N more".
    """
    
    def __init__(self, checkpoint_file: Path = Path("data/progress.json")):
        self.checkpoint_file = Path(checkpoint_file)
        self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load or initialize
        if self.checkpoint_file.exists():
            data = json.loads(self.checkpoint_file.read_text())
            self.processed_ids: Set[str] = set(data.get('processed_ids', []))
            self.total_processed: int = data.get('total_processed', 0)
            self.last_date: Optional[str] = data.get('last_date')
            self.oldest_date: Optional[str] = data.get('oldest_date')
            self.last_api_page: int = data.get('last_api_page', 1)  # Track API pagination
        else:
            self.processed_ids = set()
            self.total_processed = 0
            self.last_date = None
            self.oldest_date = None
            self.last_api_page = 1
    
    def mark_processed(self, article_id: str, pub_date: str):
        """Mark an article as processed."""
        if article_id not in self.processed_ids:
            self.processed_ids.add(article_id)
            self.total_processed += 1
            
            # Track date range
            if self.last_date is None or pub_date > self.last_date:
                self.last_date = pub_date
            if self.oldest_date is None or pub_date < self.oldest_date:
                self.oldest_date = pub_date
    
    def is_processed(self, article_id: str) -> bool:
        """Check if article already processed."""
        return article_id in self.processed_ids
    
    def save(self):
        """Save progress to checkpoint file."""
        data = {
            'processed_ids': list(self.processed_ids),
            'total_processed': self.total_processed,
            'last_date': self.last_date,
            'oldest_date': self.oldest_date,
            'last_api_page': self.last_api_page,
            'updated_at': datetime.now().isoformat()
        }
        self.checkpoint_file.write_text(json.dumps(data, indent=2))
    
    def get_status(self) -> dict:
        """Get current progress status."""
        return {
            'total_processed': self.total_processed,
            'newest_date': self.last_date,
            'oldest_date': self.oldest_date,
            'unique_articles': len(self.processed_ids)
        }
    
    def reset(self):
        """Clear all progress."""
        self.processed_ids = set()
        self.total_processed = 0
        self.last_date = None
        self.oldest_date = None
        self.last_api_page = 1
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
    
    def advance_page(self):
        """Move to next API page."""
        self.last_api_page += 1
