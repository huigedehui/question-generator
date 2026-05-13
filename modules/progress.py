"""Progress tracking module for question generation."""
from typing import Optional, Callable, Dict
from dataclasses import dataclass, field
from datetime import datetime
from .config import QuestionStats
from .logger import setup_logging

logger = setup_logging()


@dataclass
class GenerationProgress:
    """Progress tracking for question generation."""
    total_chunks: int = 0
    processed_chunks: int = 0
    total_questions: int = 0
    valid_questions: int = 0
    duplicate_questions: int = 0
    failed_chunks: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    def get_elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()
    
    def get_progress_percent(self) -> float:
        """Get progress percentage."""
        if self.total_chunks == 0:
            return 0.0
        return (self.processed_chunks / self.total_chunks) * 100
    
    def get_eta_seconds(self) -> Optional[float]:
        """Estimate seconds remaining."""
        if self.processed_chunks == 0:
            return None
        elapsed = self.get_elapsed_seconds()
        per_chunk = elapsed / self.processed_chunks
        remaining = self.total_chunks - self.processed_chunks
        return per_chunk * remaining
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "total_chunks": self.total_chunks,
            "processed_chunks": self.processed_chunks,
            "total_questions": self.total_questions,
            "valid_questions": self.valid_questions,
            "duplicate_questions": self.duplicate_questions,
            "failed_chunks": self.failed_chunks,
            "elapsed_seconds": self.get_elapsed_seconds(),
            "progress_percent": self.get_progress_percent()
        }


class ProgressTracker:
    """Track progress of question generation process."""
    
    def __init__(self, total_chunks: int, 
                 callback: Optional[Callable] = None,
                 update_interval: int = 10):
        self.progress = GenerationProgress(total_chunks=total_chunks)
        self.callback = callback
        self.update_interval = update_interval
        self.logger = logger
        
    def update(self, processed: int = 0, questions_generated: int = 0,
              valid_count: int = 0, duplicates: int = 0,
              failed: int = 0, message: str = ""):
        """Update progress."""
        self.progress.processed_chunks = processed
        self.progress.total_questions = questions_generated
        self.progress.valid_questions = valid_count
        self.progress.duplicate_questions = duplicates
        self.progress.failed_chunks = failed
        
        if processed % self.update_interval == 0 or message:
            self._log_progress(message)
            
        if self.callback:
            self.callback(self.progress)
    
    def _log_progress(self, message: str = ""):
        """Log current progress."""
        pct = self.progress.get_progress_percent()
        elapsed = self.progress.get_elapsed_seconds()
        eta = self.progress.get_eta_seconds()
        
        log_msg = f"Progress: {pct:.1f}% | {self.progress.processed_chunks}/{self.progress.total_chunks} chunks | "
        log_msg += f"Elapsed: {elapsed:.1f}s"
        
        if eta:
            log_msg += f" | ETA: {eta:.1f}s"
        
        if message:
            log_msg += f" | {message}"
        
        self.logger.info(log_msg)
    
    def complete(self):
        """Mark process as complete."""
        self.progress.end_time = datetime.now()
        self.logger.info(
            f"Generation complete: {self.progress.valid_questions} valid questions "
            f"in {self.progress.get_elapsed_seconds():.1f}s"
        )
    
    def get_stats(self) -> QuestionStats:
        """Get statistics object."""
        return QuestionStats(
            total_chunks=self.progress.total_chunks,
            processed_chunks=self.progress.processed_chunks,
            total_questions=self.progress.total_questions,
            valid_questions=self.progress.valid_questions,
            duplicate_questions=self.progress.duplicate_questions,
            failed_chunks=self.progress.failed_chunks
        )


def simple_progress_callback(progress: GenerationProgress):
    """Simple console progress callback."""
    pct = progress.get_progress_percent()
    print(f"\rProgress: {pct:.1f}% ({progress.processed_chunks}/{progress.total_chunks})", end="", flush=True)


def detailed_progress_callback(progress: GenerationProgress):
    """Detailed progress callback with statistics."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] "
          f"Processed {progress.processed_chunks}/{progress.total_chunks} chunks | "
          f"Questions: {progress.total_questions} total, {progress.valid_questions} valid | "
          f"Duplicates: {progress.duplicate_questions}")