"""AI API client with retry logic and rate limiting handling."""
import json
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
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
    
    def _make_session(self):
        """Create a fresh requests session."""
        import requests
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        })
        return session
    
    def _make_payload(self, prompt: str, system_prompt: Optional[str] = None) -> dict:
        payload = {
            "model": self.config.model,
            "messages": [],
            "temperature": 0.7,
            "max_tokens": 4000
        }
        if system_prompt:
            payload["messages"].append({"role": "system", "content": system_prompt})
        payload["messages"].append({"role": "user", "content": prompt})
        return payload
    
    def _do_request(self, payload: dict) -> AIResponse:
        """Execute a single request with fresh session."""
        session = self._make_session()
        try:
            response = session.post(
                f"{self.config.api_base}/chat/completions",
                json=payload,
                timeout=(10, self.config.timeout)
            )
        finally:
            session.close()
        
        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            logger.debug(f"API call successful, tokens used: {usage.get('total_tokens', 0)}")
            return AIResponse(success=True, content=content, usage=usage)
        
        elif response.status_code == 429:
            return AIResponse(success=False, error="rate_limited")
        
        elif response.status_code == 400:
            logger.error(f"Bad request: {response.text}")
            return AIResponse(success=False, error=f"Bad request: {response.text}")
        
        else:
            logger.error(f"API error {response.status_code}: {response.text}")
            return AIResponse(success=False, error=f"API error: {response.status_code}")
    
    def call(self, prompt: str, system_prompt: Optional[str] = None) -> AIResponse:
        """
        Call AI API with retry logic and hard timeout.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            
        Returns:
            AIResponse object
        """
        payload = self._make_payload(prompt, system_prompt)
        
        for attempt in range(self.config.max_retries):
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self._do_request, payload)
                    try:
                        result = future.result(timeout=120)
                    except TimeoutError:
                        logger.error(f"Request timed out after 120s (attempt {attempt+1})")
                        if attempt < self.config.max_retries - 1:
                            time.sleep(self.config.backoff_factor ** attempt)
                        continue
                
                if result.success:
                    return result
                
                if result.error == "rate_limited":
                    wait_time = self.config.backoff_factor ** attempt * 2
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                
                if attempt == self.config.max_retries - 1:
                    return result
                time.sleep(self.config.backoff_factor ** attempt)
                    
            except Exception as e:
                logger.error(f"API call failed: {e}")
                if attempt == self.config.max_retries - 1:
                    return AIResponse(success=False, error=str(e))
                time.sleep(self.config.backoff_factor ** attempt)
        
        return AIResponse(success=False, error="Max retries exceeded")


PROMPT_TEMPLATE = """请基于以下知识内容生成高质量的考试题目。

{type_hint}

质量要求（必须遵守）：
1. **混淆性**：单选题的4个选项中，错误选项必须与正确答案高度相似——长度相近、措辞相近、内容相关，不能一眼看出是错的。错误选项要基于文档中的真实信息编造，不能随意编造无关内容。
2. **多选题**有2-4个选项，答案用逗号分隔，如 "A,B"，错误选项同样要有迷惑性。
3. **判断题**答案为 "正确" 或 "错误"，题干要针对容易混淆的知识点设计。
4. **问答题**答案不超过30个字，答案要精确、唯一。
5. **题干**必须完整、独立成句，不能出现"以下哪个"、"下列说法正确的是"等模糊指代。
6. 每道题都要有**解析**，解析要说明为什么正确/错误。
7. 禁止出现"以上都对"、"以上都错"、"以上都不是"、"全部都对"、"全部错误"等选项。
8. 单选题确保答案唯一，不能有多选争议。
9. **选项长度均衡**：四个选项的长度应相近，最大长度不超过平均长度的1.8倍，最短不小于平均长度的30%。
10. **错误选项**必须与正确答案在语法结构上一致（同为名词短语、完整句子等），不能随便写几个字充数。
11. **错误选项**必须基于文档中的真实信息改编，使其看起来似是而非，不能凭空捏造与文档无关的内容。
12. 避免在选项中使用"总是"、"从不"、"所有"、"绝对"等绝对化词汇。

输出格式：JSON数组
[
  {{
    "type": "单选/多选/判断/问答",
    "content": "题干内容",
    "options": ["A选项", "B选项", "C选项", "D选项"],
    "answer": "正确答案",
    "analysis": "题目解析（说明为什么不选其他选项）"
  }}
]

知识内容：
{chunk}

请严格按照以上要求生成题目："""


def strip_markdown_fences(text: str) -> str:
    """Strip markdown code fences from AI response."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end_idx = len(lines) - 1 if lines[-1].startswith("```") else len(lines)
        text = "\n".join(lines[1:end_idx])
    return text


def generate_question_prompt(chunk: str, question_type: Optional[str] = None) -> str:
    """Generate prompt for question generation."""
    type_hint = f"题目类型为 {question_type}" if question_type else "题目类型包括: 单选、多选、判断、问答"
    return PROMPT_TEMPLATE.format(type_hint=type_hint, chunk=chunk)


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
        content = strip_markdown_fences(response.content)
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