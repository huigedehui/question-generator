"""Configuration module for exam question generator."""
import os
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class Config:
    """Main configuration class for the question generator."""
    
    api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    api_base: str = field(default_factory=lambda: os.getenv("API_BASE", "https://api.openai.com/v1"))
    model: str = "gpt-4o-mini"
    
    chunk_size: int = 800
    chunk_overlap: int = 100
    min_chunk_size: int = 200
    
    max_retries: int = 3
    timeout: int = 60
    backoff_factor: float = 2.0
    
    questions_per_batch: int = 5
    max_answer_length: int = 30
    max_analysis_length: int = 160
    
    template_path: str = "题库模板.xlsx"
    cache_dir: str = ".cache"
    log_file: str = "question_gen.log"
    
    sampling_config: Dict[str, int] = field(default_factory=lambda: {
        "单选": 150,
        "多选": 90,
        "判断": 90,
        "问答": 20
    })
    
    def validate(self) -> bool:
        """Validate configuration settings."""
        if not self.api_key:
            raise ValueError("API key is required. Set OPENAI_API_KEY environment variable.")
        if self.chunk_size < self.min_chunk_size:
            raise ValueError(f"chunk_size must be at least {self.min_chunk_size}")
        if self.max_retries < 1:
            raise ValueError("max_retries must be at least 1")
        return True


@dataclass
class QuestionStats:
    """Statistics for question generation."""
    total_chunks: int = 0
    processed_chunks: int = 0
    total_questions: int = 0
    valid_questions: int = 0
    duplicate_questions: int = 0
    failed_chunks: int = 0
    

DEFAULT_CONFIG = Config()