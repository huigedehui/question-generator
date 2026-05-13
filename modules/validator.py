"""Question validator for data quality assurance."""
from typing import List, Dict, Optional, Tuple
from .config import Config
from .logger import setup_logging, ValidationError

logger = setup_logging()

VALID_TYPES = {"单选", "多选", "判断", "问答", "填空"}


class QuestionValidator:
    """Validator for question data quality."""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.validation_errors = []
    
    def validate_question(self, question: Dict) -> List[str]:
        """
        Validate a single question.
        
        Args:
            question: Question dictionary
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        q_type = question.get("type", "")
        content = question.get("content", "").strip()
        answer = question.get("answer", "")
        options = question.get("options", [])
        analysis = question.get("analysis", "")
        
        if not q_type:
            errors.append("Missing question type")
        elif q_type not in VALID_TYPES:
            errors.append(f"Invalid type: {q_type}")
        
        if not content:
            errors.append("Missing question content")
        elif len(content) > 500:
            errors.append(f"Question content too long: {len(content)} chars")
        
        if q_type in {"单选", "多选"}:
            if not options or len(options) < 2:
                errors.append("Insufficient options for choice question")
            
            valid_options = set(f"选项{i}" for i in range(1, len(options) + 1))
            answer_clean = answer.strip()
            
            if q_type == "单选" and answer_clean not in ["A", "B", "C", "D"]:
                if not any(opt in answer_clean for opt in valid_options):
                    errors.append(f"Invalid answer for single choice: {answer}")
            
            if q_type == "多选":
                if len(answer) > 30:
                    errors.append("Answer exceeds 30 characters")
        
        if q_type == "判断":
            if answer not in ["正确", "错误", "A", "B"]:
                errors.append(f"Invalid answer for true/false: {answer}")
        
        if q_type == "问答":
            if len(answer) > self.config.max_answer_length:
                errors.append(f"Answer exceeds {self.config.max_answer_length} characters")
        
        if analysis and len(analysis) > self.config.max_analysis_length:
            errors.append(f"Analysis exceeds {self.config.max_analysis_length} characters")
        
        return errors
    
    def validate_batch(self, questions: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Validate a batch of questions.
        
        Returns:
            Tuple of (valid_questions, invalid_questions)
        """
        valid = []
        invalid = []
        
        for q in questions:
            errors = self.validate_question(q)
            if errors:
                invalid.append({"question": q, "errors": errors})
                logger.warning(f"Invalid question: {errors}")
            else:
                valid.append(q)
        
        logger.info(f"Validation: {len(valid)} valid, {len(invalid)} invalid")
        return valid, invalid
    
    def normalize_answer(self, question: Dict) -> Dict:
        """Normalize answer format for a question."""
        q_type = question.get("type", "")
        answer = question.get("answer", "").strip()
        
        if q_type == "多选":
            parts = [a.strip() for a in answer.split(",")]
            sorted_parts = sorted(parts)
            question["answer"] = ",".join(sorted_parts)
        
        elif q_type == "判断":
            if answer in ["true", "True", "T"]:
                question["answer"] = "正确"
            elif answer in ["false", "False", "F"]:
                question["answer"] = "错误"
            elif answer == "A":
                question["answer"] = "正确"
            elif answer == "B":
                question["answer"] = "错误"
        
        return question


def clean_questions(questions: List[Dict], 
                    validator: Optional[QuestionValidator] = None) -> List[Dict]:
    """
    Clean and deduplicate questions.
    
    Args:
        questions: Raw question list
        validator: Optional validator instance
        
    Returns:
        Cleaned and deduplicated questions
    """
    if validator is None:
        validator = QuestionValidator()
    
    seen = set()
    cleaned = []
    duplicates = 0
    
    for q in questions:
        qid = q.get("content", "").strip()
        
        if qid in seen:
            duplicates += 1
            continue
        
        seen.add(qid)
        q = validator.normalize_answer(q)
        cleaned.append(q)
    
    logger.info(f"Cleaned questions: {len(cleaned)} kept, {duplicates} duplicates removed")
    return cleaned


def check_option_balance(options: List[str]) -> bool:
    """Check if options have reasonable balance (not too similar or too different)."""
    if len(options) < 2:
        return False
    
    lengths = [len(opt) for opt in options]
    avg_length = sum(lengths) / len(lengths)
    
    if max(lengths) > avg_length * 1.5:
        return False
    
    return True