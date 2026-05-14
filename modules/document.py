"""Word document processor with semantic chunking."""
import re
from typing import List, Optional, Callable
from pathlib import Path

try:
    import docx
except ImportError:
    raise ImportError("python-docx is required. Install with: pip install python-docx")

from .logger import setup_logging, QuestionGeneratorError

logger = setup_logging()


def load_word_document(file_path: str) -> List[str]:
    """
    Load Word document and return paragraphs.
    
    Args:
        file_path: Path to .docx file
        
    Returns:
        List of non-empty paragraphs
    """
    try:
        doc = docx.Document(file_path)
        paragraphs = [
            p.text.strip() 
            for p in doc.paragraphs 
            if p.text.strip()
        ]
        logger.info(f"Loaded {len(paragraphs)} paragraphs from {file_path}")
        return paragraphs
    except Exception as e:
        logger.error(f"Failed to load document {file_path}: {e}")
        raise QuestionGeneratorError(f"Document loading failed: {e}")


def semantic_chunk_text(paragraphs: List[str], chunk_size: int = 800, 
                        overlap: int = 100, min_chunk_size: int = 200) -> List[str]:
    """
    Split paragraphs into semantic chunks with overlap.
    
    Args:
        paragraphs: List of text paragraphs
        chunk_size: Target size for each chunk
        overlap: Overlap between chunks in characters
        min_chunk_size: Minimum chunk size to keep
        
    Returns:
        List of text chunks
    """
    chunks = []
    current_chunk = []
    current_size = 0
    
    for para in paragraphs:
        para_size = len(para)
        
        if current_size + para_size <= chunk_size:
            current_chunk.append(para)
            current_size += para_size
        else:
            if current_chunk:
                chunk_text = "\n".join(current_chunk)
                chunks.append(chunk_text)
                
                if overlap > 0 and current_size > overlap:
                    overlap_text = chunk_text[-overlap:]
                    current_chunk = [overlap_text, para]
                    current_size = len(overlap_text) + para_size
                else:
                    current_chunk = [para]
                    current_size = para_size
            else:
                if para_size > chunk_size:
                    sub_chunks = split_long_paragraph(para, chunk_size)
                    chunks.extend(sub_chunks[:-1])
                    current_chunk = [sub_chunks[-1]]
                    current_size = len(sub_chunks[-1])
                else:
                    current_chunk = [para]
                    current_size = para_size
    
    if current_chunk:
        chunk_text = "\n".join(current_chunk)
        if len(chunk_text) >= min_chunk_size:
            chunks.append(chunk_text)
    
    logger.info(f"Created {len(chunks)} semantic chunks from {len(paragraphs)} paragraphs")
    return chunks


def split_long_paragraph(text: str, max_size: int) -> List[str]:
    """Split a long paragraph at sentence boundaries."""
    sentences = re.split(r'(?<=[。！？；\n])', text)
    chunks = []
    current = ""
    
    for sentence in sentences:
        if len(current) + len(sentence) <= max_size:
            current += sentence
        else:
            if current:
                chunks.append(current)
            current = sentence
    
    if current:
        chunks.append(current)
    
    return chunks if chunks else [text]


def load_word_docs(doc_paths: List[str], chunk_size: int = 800,
                   overlap: int = 100, min_chunk_size: int = 200,
                   progress_callback: Optional[Callable] = None) -> List[str]:
    """
    Load multiple Word documents and create semantic chunks.
    
    Args:
        doc_paths: List of paths to .docx files
        chunk_size: Target chunk size
        overlap: Overlap between chunks
        min_chunk_size: Minimum chunk size
        progress_callback: Optional callback for progress updates
        
    Returns:
        List of text chunks
    """
    all_chunks = []
    total_docs = len(doc_paths)
    
    for i, path in enumerate(doc_paths):
        try:
            paragraphs = load_word_document(path)
            chunks = semantic_chunk_text(paragraphs, chunk_size, overlap, min_chunk_size)
            
            for chunk in chunks:
                all_chunks.append(chunk)
            
            logger.info(f"Processed document {i+1}/{total_docs}: {path} -> {len(chunks)} chunks")
            
            if progress_callback:
                progress_callback(i + 1, total_docs, f"Loaded {Path(path).name}")
                
        except Exception as e:
            logger.error(f"Error processing {path}: {e}")
            continue
    
    logger.info(f"Total chunks created: {len(all_chunks)}")
    return all_chunks