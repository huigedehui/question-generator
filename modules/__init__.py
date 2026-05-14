"""AI Question Generator - 自动从文档生成考试题库"""

__version__ = "1.0.0"
__author__ = "Question Generator Team"
__description__ = "AI-powered exam question generator from Word documents"

from .config import Config, DEFAULT_CONFIG, QuestionStats
from .logger import setup_logging, QuestionGeneratorError, APIError, ValidationError, TemplateError
from .document import load_word_docs, load_word_document, semantic_chunk_text
from .ai_client import APIClient, call_ai_generate, batch_generate_questions, strip_markdown_fences, generate_question_prompt
from .validator import QuestionValidator, clean_questions, check_option_balance
from .sampler import QuestionSampler, sample_questions, sample_by_source
from .exporter import export_to_excel, map_question_to_template
from .progress import ProgressTracker, GenerationProgress, simple_progress_callback
from .cache import QuestionCache, save_intermediate, load_intermediate

__all__ = [
    # Version
    "__version__",
    # Config
    "Config",
    "DEFAULT_CONFIG",
    "QuestionStats",
    # Logger
    "setup_logging",
    "QuestionGeneratorError",
    "APIError",
    "ValidationError",
    "TemplateError",
    # Document
    "load_word_docs",
    "load_word_document",
    "semantic_chunk_text",
    # AI Client
    "APIClient",
    "call_ai_generate",
    "batch_generate_questions",
    "strip_markdown_fences",
    "generate_question_prompt",
    # Validator
    "QuestionValidator",
    "clean_questions",
    "check_option_balance",
    # Sampler
    "QuestionSampler",
    "sample_questions",
    "sample_by_source",
    # Exporter
    "export_to_excel",
    "map_question_to_template",
    # Progress
    "ProgressTracker",
    "GenerationProgress",
    "simple_progress_callback",
    # Cache
    "QuestionCache",
    "save_intermediate",
    "load_intermediate",
]