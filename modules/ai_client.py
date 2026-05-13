"""AI API client with retry logic and rate limiting handling."""
import json
import time
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from .config import Config
from .logger import setup_logging, APIError

logger = setup_logging()


@dataclass
class AIResponse:
    """Structured AI response."""
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    usage: Optional[Dict] = None


class APIClient:
    """API client with exponential backoff retry."""
    
    def __init__(self, config: Config):
        self.config = config
        self.session = None
    
    def _create_session(self):
        """Create HTTP session for API calls."""
        try:
            import requests
            self.session = requests.Session()
            self.session.headers.update({
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            })
        except ImportError:
            raise ImportError("requests library is required. Install with: pip install requests")
    
    def call(self, prompt: str, system_prompt: Optional[str] = None) -> AIResponse:
        """
        Call AI API with retry logic.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            
        Returns:
            AIResponse object
        """
        if not self.session:
            self._create_session()
        
        payload = {
            "model": self.config.model,
            "messages": [],
            "temperature": 0.7,
            "max_tokens": 4000
        }
        
        if system_prompt:
            payload["messages"].append({"role": "system", "content": system_prompt})
        payload["messages"].append({"role": "user", "content": prompt})
        
        for attempt in range(self.config.max_retries):
            try:
                response = self.session.post(
                    f"{self.config.api_base}/chat/completions",
                    json=payload,
                    timeout=self.config.timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})
                    logger.debug(f"API call successful, tokens used: {usage.get('total_tokens', 0)}")
                    return AIResponse(success=True, content=content, usage=usage)
                
                elif response.status_code == 429:
                    wait_time = self.config.backoff_factor ** attempt * 2
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                
                elif response.status_code == 400:
                    logger.error(f"Bad request: {response.text}")
                    return AIResponse(success=False, error=f"Bad request: {response.text}")
                
                else:
                    logger.error(f"API error {response.status_code}: {response.text}")
                    if attempt == self.config.max_retries - 1:
                        return AIResponse(success=False, error=f"API error: {response.status_code}")
                    time.sleep(self.config.backoff_factor ** attempt)
                    
            except Exception as e:
                logger.error(f"API call failed: {e}")
                if attempt == self.config.max_retries - 1:
                    return AIResponse(success=False, error=str(e))
                time.sleep(self.config.backoff_factor ** attempt)
        
        return AIResponse(success=False, error="Max retries exceeded")


def generate_question_prompt(chunk: str, question_type: Optional[str] = None) -> str:
    """Generate prompt for question generation."""
    type_hint = f"题目类型为 {question_type}" if question_type else "题目类型包括: 单选、多选、判断、问答"
    
    return f"""请基于以下知识内容生成考试题目。

{type_hint}

要求：
1. 单选题有4个选项，选项必须具有迷惑性
2. 多选题有2-4个选项，答案用逗号分隔，如 "A,B"
3. 判断题答案为 "正确" 或 "错误"
4. 问答题答案不超过30个字
5. 每道题都要有解析

输出格式：JSON数组
[
  {{
    "type": "单选/多选/判断/问答",
    "content": "题干内容",
    "options": ["A选项", "B选项", "C选项", "D选项"],
    "answer": "正确答案",
    "analysis": "题目解析"
  }}
]

知识内容：
{chunk}

请生成题目："""


def call_ai_generate(chunk: str, api_client: APIClient, 
                     question_type: Optional[str] = None) -> List[Dict]:
    """
    Call AI to generate questions from a text chunk.
    
    Args:
        chunk: Text chunk to generate questions from
        api_client: APIClient instance
        question_type: Optional specific question type
        
    Returns:
        List of question dictionaries
    """
    prompt = generate_question_prompt(chunk, question_type)
    response = api_client.call(prompt)
    
    if not response.success:
        logger.error(f"AI generation failed: {response.error}")
        return []
    
    try:
        content = response.content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        
        questions = json.loads(content)
        
        if isinstance(questions, dict):
            questions = [questions]
        
        valid_questions = []
        for q in questions:
            if isinstance(q, dict) and "type" in q and "content" in q:
                valid_questions.append(q)
        
        logger.info(f"Generated {len(valid_questions)} questions from chunk")
        return valid_questions
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.debug(f"Raw response: {response.content[:500]}")
        return []


def batch_generate_questions(chunks: List[str], api_client: APIClient,
                            questions_per_batch: int = 5,
                            progress_callback: Optional[callable] = None) -> List[Dict]:
    """
    Generate questions from multiple chunks in batch.
    
    Args:
        chunks: List of text chunks
        api_client: APIClient instance
        questions_per_batch: Questions to generate per batch
        progress_callback: Optional progress callback
        
    Returns:
        List of all generated questions
    """
    all_questions = []
    total = len(chunks)
    
    for i, chunk in enumerate(chunks):
        questions = call_ai_generate(chunk, api_client)
        all_questions.extend(questions)
        
        if progress_callback and (i + 1) % 10 == 0:
            progress_callback(i + 1, total, f"Processed {i + 1}/{total} chunks")
    
    logger.info(f"Batch generation complete: {len(all_questions)} total questions")
    return all_questions