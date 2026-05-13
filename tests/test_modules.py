"""Unit tests for question generator modules."""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules import (
    Config,
    QuestionValidator,
    clean_questions,
    sample_questions,
    semantic_chunk_text,
    check_option_balance
)


class TestConfig(unittest.TestCase):
    """Tests for Config class."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = Config()
        self.assertEqual(config.chunk_size, 800)
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.max_answer_length, 30)
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = Config(
            chunk_size=1000,
            max_retries=5,
            model="gpt-4"
        )
        self.assertEqual(config.chunk_size, 1000)
        self.assertEqual(config.max_retries, 5)
        self.assertEqual(config.model, "gpt-4")
    
    def test_sampling_config(self):
        """Test sampling configuration."""
        config = Config()
        self.assertIn("单选", config.sampling_config)
        self.assertEqual(config.sampling_config["单选"], 150)


class TestSemanticChunkText(unittest.TestCase):
    """Tests for semantic chunking."""
    
    def test_empty_input(self):
        """Test empty input."""
        result = semantic_chunk_text([], chunk_size=800)
        self.assertEqual(result, [])
    
    def test_single_paragraph(self):
        """Test single paragraph."""
        paragraphs = ["这是一个测试段落。"]
        result = semantic_chunk_text(paragraphs, chunk_size=100, min_chunk_size=50)
        self.assertGreaterEqual(len(result), 0)
    
    def test_multiple_paragraphs(self):
        """Test multiple paragraphs."""
        paragraphs = [
            "第一段内容。" * 20,
            "第二段内容。" * 20
        ]
        result = semantic_chunk_text(paragraphs, chunk_size=200)
        self.assertGreater(len(result), 0)


class TestQuestionValidator(unittest.TestCase):
    """Tests for QuestionValidator."""
    
    def setUp(self):
        """Set up test validator."""
        self.validator = QuestionValidator()
    
    def test_valid_single_choice(self):
        """Test valid single choice question."""
        question = {
            "type": "单选",
            "content": "这是什么？",
            "options": ["A选项", "B选项", "C选项", "D选项"],
            "answer": "A",
            "analysis": "答案是A"
        }
        errors = self.validator.validate_question(question)
        self.assertEqual(len(errors), 0)
    
    def test_valid_multi_choice(self):
        """Test valid multi choice question."""
        question = {
            "type": "多选",
            "content": "哪些是正确的？",
            "options": ["选项A", "选项B", "选项C", "选项D"],
            "answer": "A,B",
            "analysis": "A和B正确"
        }
        errors = self.validator.validate_question(question)
        self.assertEqual(len(errors), 0)
    
    def test_valid_true_false(self):
        """Test valid true/false question."""
        question = {
            "type": "判断",
            "content": "这是正确的吗？",
            "options": ["正确", "错误"],
            "answer": "正确",
            "analysis": "这是对的"
        }
        errors = self.validator.validate_question(question)
        self.assertEqual(len(errors), 0)
    
    def test_missing_type(self):
        """Test missing question type."""
        question = {
            "content": "内容",
            "answer": "A"
        }
        errors = self.validator.validate_question(question)
        self.assertIn("Missing question type", errors)
    
    def test_invalid_type(self):
        """Test invalid question type."""
        question = {
            "type": "无效类型",
            "content": "内容",
            "answer": "A"
        }
        errors = self.validator.validate_question(question)
        self.assertTrue(any("Invalid type" in e for e in errors))
    
    def test_missing_content(self):
        """Test missing content."""
        question = {
            "type": "单选",
            "answer": "A"
        }
        errors = self.validator.validate_question(question)
        self.assertIn("Missing question content", errors)
    
    def test_insufficient_options(self):
        """Test insufficient options for choice question."""
        question = {
            "type": "单选",
            "content": "内容",
            "options": ["A"],
            "answer": "A"
        }
        errors = self.validator.validate_question(question)
        self.assertTrue(any("Insufficient options" in e for e in errors))


class TestCleanQuestions(unittest.TestCase):
    """Tests for clean_questions function."""
    
    def test_empty_list(self):
        """Test empty question list."""
        result = clean_questions([])
        self.assertEqual(result, [])
    
    def test_remove_duplicates(self):
        """Test duplicate removal."""
        questions = [
            {"type": "单选", "content": "问题1", "answer": "A"},
            {"type": "单选", "content": "问题1", "answer": "A"},
            {"type": "单选", "content": "问题2", "answer": "B"}
        ]
        result = clean_questions(questions)
        self.assertEqual(len(result), 2)
    
    def test_normalize_multi_choice_answer(self):
        """Test multi-choice answer normalization."""
        questions = [
            {"type": "多选", "content": "问题", "answer": "B,A"}
        ]
        result = clean_questions(questions)
        self.assertEqual(result[0]["answer"], "A,B")
    
    def test_normalize_true_false_answer(self):
        """Test true/false answer normalization."""
        questions = [
            {"type": "判断", "content": "问题", "answer": "true"}
        ]
        result = clean_questions(questions)
        self.assertEqual(result[0]["answer"], "正确")


class TestSampleQuestions(unittest.TestCase):
    """Tests for sample_questions function."""
    
    def test_sample_single_type(self):
        """Test sampling single type."""
        questions = [
            {"type": "单选", "content": f"问题{i}", "answer": "A"}
            for i in range(10)
        ]
        result = sample_questions(questions, {"单选": 5})
        self.assertEqual(len(result["单选"]), 5)
    
    def test_sample_multiple_types(self):
        """Test sampling multiple types."""
        questions = [
            {"type": "单选", "content": f"单选{i}", "answer": "A"}
            for i in range(10)
        ] + [
            {"type": "多选", "content": f"多选{i}", "answer": "A,B"}
            for i in range(10)
        ]
        result = sample_questions(questions, {"单选": 5, "多选": 3})
        self.assertEqual(len(result["单选"]), 5)
        self.assertEqual(len(result["多选"]), 3)
    
    def test_insufficient_questions(self):
        """Test when not enough questions available."""
        questions = [
            {"type": "单选", "content": f"问题{i}", "answer": "A"}
            for i in range(3)
        ]
        result = sample_questions(questions, {"单选": 5})
        self.assertEqual(len(result["单选"]), 3)


class TestCheckOptionBalance(unittest.TestCase):
    """Tests for check_option_balance function."""
    
    def test_balanced_options(self):
        """Test balanced options."""
        options = ["选项A", "选项B", "选项C", "选项D"]
        result = check_option_balance(options)
        self.assertTrue(result)
    
    def test_unbalanced_options(self):
        """Test unbalanced options."""
        options = ["A", "B" * 500]
        result = check_option_balance(options)
        self.assertFalse(result)
    
    def test_single_option(self):
        """Test single option."""
        result = check_option_balance(["A"])
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()