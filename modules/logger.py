"""Logging module for exam question generator."""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def setup_logging(log_file: str = "question_gen.log", level: int = logging.INFO) -> logging.Logger:
    """Setup logging configuration with console and file handlers."""
    logger = logging.getLogger("QuestionGenerator")
    logger.setLevel(level)
    
    if logger.handlers:
        return logger
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


class QuestionGeneratorError(Exception):
    """Base exception for question generator."""
    pass


class APIError(QuestionGeneratorError):
    """Raised when API call fails."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.status_code = status_code
        super().__init__(message)


class ValidationError(QuestionGeneratorError):
    """Raised when data validation fails."""
    pass


class TemplateError(QuestionGeneratorError):
    """Raised when template processing fails."""
    pass