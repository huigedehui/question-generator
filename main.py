"""Main entry point for exam question generator."""
import os
import sys
import argparse
from pathlib import Path
from typing import Optional

from modules import (
    Config,
    setup_logging,
    load_word_docs,
    APIClient,
    batch_generate_questions,
    QuestionValidator,
    clean_questions,
    sample_questions,
    export_to_excel,
    ProgressTracker,
    QuestionCache,
    QuestionGeneratorError
)

logger = setup_logging()


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="AI-powered exam question generator"
    )
    parser.add_argument(
        "documents", 
        nargs="+", 
        help="Word documents to process (.docx files)"
    )
    parser.add_argument(
        "-o", "--output",
        default="生成试卷.xlsx",
        help="Output Excel file path"
    )
    parser.add_argument(
        "-t", "--template",
        default="题库模板.xlsx",
        help="Template Excel file path"
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key (or set OPENAI_API_KEY env variable)"
    )
    parser.add_argument(
        "--api-base",
        default=None,
        help="API base URL"
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="AI model to use"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=800,
        help="Chunk size for text splitting"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip loading from cache"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint if available"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    return parser.parse_args()


def main():
    """Main execution function."""
    args = parse_args()
    
    if args.verbose:
        import logging
        setup_logging(level=logging.DEBUG)
    
    logger.info("Starting question generator")
    
    config = Config(
        api_key=args.api_key or os.getenv("OPENAI_API_KEY", ""),
        api_base=args.api_base or os.getenv("API_BASE", "https://api.openai.com/v1"),
        model=args.model,
        chunk_size=args.chunk_size,
        template_path=args.template
    )
    
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    doc_paths = [Path(p) for p in args.documents]
    for p in doc_paths:
        if not p.exists():
            logger.error(f"Document not found: {p}")
            sys.exit(1)
    
    cache = QuestionCache()
    
    chunks = None
    if args.resume and not args.no_cache:
        chunks = cache.load_chunks()
        if chunks:
            logger.info(f"Resumed with {len(chunks)} cached chunks")
    
    if chunks is None:
        logger.info(f"Loading documents: {[str(p) for p in doc_paths]}")
        chunks = load_word_docs([str(p) for p in doc_paths], config.chunk_size)
        cache.save_chunks(chunks)
    
    progress = ProgressTracker(len(chunks), update_interval=5)
    
    api_client = APIClient(config)
    
    logger.info("Generating questions from chunks...")
    all_questions = []
    
    for i, chunk in enumerate(chunks):
        questions = call_ai_generate(chunk, api_client)
        all_questions.extend(questions)
        
        if (i + 1) % 10 == 0:
            progress.update(
                processed=i + 1,
                questions_generated=len(all_questions)
            )
    
    progress.update(
        processed=len(chunks),
        questions_generated=len(all_questions)
    )
    
    cache.save_questions(all_questions, "raw_questions.json")
    
    validator = QuestionValidator(config)
    valid_questions, invalid_questions = validator.validate_batch(all_questions)
    
    if invalid_questions:
        logger.warning(f"Found {len(invalid_questions)} invalid questions")
        cache.save_questions(invalid_questions, "invalid_questions.json")
    
    logger.info(f"Valid questions: {len(valid_questions)}")
    
    cleaned = clean_questions(valid_questions, validator)
    
    final_questions = sample_questions(cleaned, config.sampling_config)
    
    export_to_excel(
        final_questions,
        args.template,
        args.output,
        category="考试",
        difficulty="一般"
    )
    
    progress.complete()
    
    stats = progress.get_stats()
    logger.info(
        f"Completed! Generated {stats.valid_questions} valid questions "
        f"in {stats.processed_chunks} chunks"
    )
    
    print(f"\nOutput saved to: {args.output}")


if __name__ == "__main__":
    main()