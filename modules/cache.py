"""Cache module for question persistence and resume capability."""
import json
import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

try:
    import pandas as pd
except ImportError:
    pd = None

from .logger import setup_logging

logger = setup_logging()


class QuestionCache:
    """Cache manager for question persistence."""
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self._ensure_safe_path()
    
    def _ensure_safe_path(self):
        """Ensure cache directory is within safe bounds."""
        try:
            self.cache_dir = self.cache_dir.resolve()
            if not str(self.cache_dir).startswith(str(Path.cwd())):
                raise ValueError("Cache directory must be within current directory")
        except Exception:
            self.cache_dir = Path(".cache").resolve()
            self.cache_dir.mkdir(exist_ok=True)
    
    def save_questions(self, questions: List[Dict], 
                      filename: str = "questions_cache.json") -> bool:
        """
        Save questions to cache file.
        
        Args:
            questions: List of question dictionaries
            filename: Cache filename
            
        Returns:
            True if successful
        """
        try:
            cache_path = self.cache_dir / filename
            
            data = {
                "timestamp": datetime.now().isoformat(),
                "version": "1.0",
                "count": len(questions),
                "questions": questions
            }
            
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Saved {len(questions)} questions to {cache_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
            return False
    
    def load_questions(self, filename: str = "questions_cache.json") -> Optional[List[Dict]]:
        """
        Load questions from cache file.
        
        Args:
            filename: Cache filename
            
        Returns:
            List of questions or None if not found
        """
        try:
            cache_path = self.cache_dir / filename
            
            if not cache_path.exists():
                logger.debug(f"Cache file not found: {cache_path}")
                return None
            
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            questions = data.get("questions", [])
            logger.info(f"Loaded {len(questions)} questions from cache")
            return questions
            
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
            return None
    
    def save_chunks(self, chunks: List[str], 
                   filename: str = "chunks_cache.json") -> bool:
        """Save chunks to cache."""
        try:
            cache_path = self.cache_dir / filename
            
            data = {
                "timestamp": datetime.now().isoformat(),
                "count": len(chunks),
                "chunks": chunks
            }
            
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            
            logger.info(f"Saved {len(chunks)} chunks to cache")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save chunks: {e}")
            return False
    
    def load_chunks(self, filename: str = "chunks_cache.json") -> Optional[List[str]]:
        """Load chunks from cache."""
        try:
            cache_path = self.cache_dir / filename
            
            if not cache_path.exists():
                return None
            
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            chunks = data.get("chunks", [])
            logger.info(f"Loaded {len(chunks)} chunks from cache")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to load chunks: {e}")
            return None
    
    def save_checkpoint(self, data: Dict, checkpoint_name: str) -> bool:
        """Save a checkpoint for resume capability."""
        return self.save_questions(data, f"checkpoint_{checkpoint_name}.json")
    
    def load_checkpoint(self, checkpoint_name: str) -> Optional[Dict]:
        """Load a checkpoint."""
        questions = self.load_questions(f"checkpoint_{checkpoint_name}.json")
        return {"questions": questions} if questions else None
    
    def save_to_excel(self, questions: List[Dict], filename: str) -> bool:
        """Save questions directly to Excel."""
        if pd is None:
            logger.error("pandas not available for Excel export")
            return False
        
        try:
            df = pd.DataFrame(questions)
            output_path = self.cache_dir / filename
            df.to_excel(output_path, index=False)
            logger.info(f"Saved questions to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save Excel: {e}")
            return False
    
    def load_from_excel(self, filename: str) -> Optional[List[Dict]]:
        """Load questions directly from Excel."""
        if pd is None:
            logger.error("pandas not available for Excel import")
            return None
        
        try:
            input_path = self.cache_dir / filename
            if not input_path.exists():
                return None
            
            df = pd.read_excel(input_path)
            questions = df.to_dict("records")
            logger.info(f"Loaded {len(questions)} questions from Excel")
            return questions
        except Exception as e:
            logger.error(f"Failed to load Excel: {e}")
            return None
    
    def list_cache_files(self) -> List[str]:
        """List all cache files."""
        try:
            return [f.name for f in self.cache_dir.glob("*.json")]
        except Exception:
            return []
    
    def clear_cache(self, pattern: str = "*.json") -> int:
        """Clear cache files matching pattern."""
        count = 0
        try:
            for f in self.cache_dir.glob(pattern):
                f.unlink()
                count += 1
            logger.info(f"Cleared {count} cache files")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
        return count
    
    def get_cache_status(self) -> Dict:
        """Get cache status information."""
        cache_files = self.list_cache_files()
        
        total_questions = 0
        for filename in cache_files:
            data = self.load_questions(filename)
            if data:
                total_questions += len(data)
        
        return {
            "cache_dir": str(self.cache_dir),
            "files": cache_files,
            "file_count": len(cache_files),
            "total_questions": total_questions
        }


def save_intermediate(questions: List[Dict], step: str, cache_dir: str = ".cache"):
    """Save intermediate results during processing."""
    cache = QuestionCache(cache_dir)
    filename = f"step_{step}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    cache.save_questions(questions, filename)


def load_intermediate(step: str, cache_dir: str = ".cache") -> Optional[List[Dict]]:
    """Load intermediate results."""
    cache = QuestionCache(cache_dir)
    pattern = f"step_{step}_*.json"
    
    files = list(cache.cache_dir.glob(pattern))
    if files:
        latest = max(files, key=lambda f: f.stat().st_mtime)
        return cache.load_questions(latest.name)
    
    return None