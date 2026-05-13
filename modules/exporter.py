"""Excel exporter with template mapping."""
from typing import List, Dict, Optional
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    raise ImportError("pandas is required. Install with: pip install pandas")

try:
    import openpyxl
except ImportError:
    raise ImportError("openpyxl is required. Install with: pip install openpyxl")

from .logger import setup_logging, TemplateError

logger = setup_logging()


TYPE_MAPPING = {
    "单选": "单选题",
    "多选": "多选题",
    "判断": "判断题",
    "问答": "问答题",
    "填空": "填空题"
}

CATEGORY_MAPPING = {
    "考试": "考试",
    "练习": "练习",
    "考试和练习": "考试和练习"
}

DIFFICULTY_MAPPING = {
    "容易": "容易",
    "较易": "较易", 
    "一般": "一般",
    "较难": "较难",
    "非常难": "非常难"
}


def map_question_to_template(question: Dict, template_columns: List[str]) -> Dict:
    """
    Map question dictionary to template columns.
    
    Args:
        question: Question dictionary
        template_columns: List of template column names
        
    Returns:
        Row dictionary matching template
    """
    row = {}
    options = question.get("options", [])
    
    for col in template_columns:
        if col == "题型" or col == "试题类型":
            row[col] = TYPE_MAPPING.get(question.get("type", ""), question.get("type", ""))
        elif col == "题干" or col == "题目内容":
            row[col] = question.get("content", "")
        elif col.startswith("选项") and len(col) <= 3:
            idx = ord(col[-1]) - ord("A")
            if idx < len(options):
                row[col] = options[idx]
            else:
                row[col] = ""
        elif col == "正确答案" or col == "答案":
            row[col] = question.get("answer", "")
        elif col == "解析" or col == "题目解析":
            analysis = question.get("analysis", "")
            row[col] = analysis[:160] if analysis else ""
        elif col == "试题分类":
            row[col] = question.get("category", "考试")
        elif col == "难易度" or col == "难度":
            row[col] = question.get("difficulty", "一般")
        elif col == "试题分数" or col == "分数":
            row[col] = question.get("score", 1)
        elif col == "题目出处" or col == "出处":
            row[col] = question.get("source", "")
        elif col == "知识点":
            row[col] = question.get("knowledge_point", "")
        elif col == "选项数目":
            choice_type = question.get("type", "")
            if choice_type in {"单选", "多选", "判断"}:
                row[col] = len([o for o in options if o])
            else:
                row[col] = ""
        else:
            row[col] = question.get(col, "")
    
    return row


def export_to_excel(questions: Dict[str, List[Dict]], 
                   template_path: str,
                   output_path: str,
                   category: str = "考试",
                   difficulty: str = "一般") -> bool:
    """
    Export questions to Excel template.
    
    Args:
        questions: Dict of {type: [questions]}
        template_path: Path to template Excel file
        output_path: Output Excel file path
        
    Returns:
        True if successful
    """
    try:
        if template_path and Path(template_path).exists():
            df_template = pd.read_excel(template_path)
            template_columns = list(df_template.columns)
        else:
            template_columns = [
                "序号", "试题类型", "题干", "选项A", "选项B", "选项C", "选项D",
                "正确答案", "解析", "试题分类", "难易度", "试题分数",
                "题目出处", "知识点", "选项数目"
            ]
            if template_path:
                logger.warning(f"Template not found, using default columns")
        
        all_rows = []
        seq_num = 1
        
        for q_type, qs in questions.items():
            for q in qs:
                q["category"] = q.get("category", category)
                q["difficulty"] = q.get("difficulty", difficulty)
                
                row = map_question_to_template(q, template_columns)
                
                if "序号" in template_columns:
                    row["序号"] = seq_num
                    seq_num += 1
                
                all_rows.append(row)
        
        df = pd.DataFrame(all_rows)
        
        for col in template_columns:
            if col not in df.columns:
                df[col] = ""
        
        df = df[template_columns]
        
        df.to_excel(output_path, index=False, engine='openpyxl')
        logger.info(f"Exported {len(df)} questions to {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise TemplateError(f"Export to Excel failed: {e}")


def export_single_type(questions: List[Dict],
                       output_path: str,
                       question_type: str = "单选") -> bool:
    """
    Export a single type of questions to Excel.
    
    Args:
        questions: List of questions
        output_path: Output file path
        question_type: Type of questions
        
    Returns:
        True if successful
    """
    return export_to_excel({question_type: questions}, "", output_path)


def append_to_excel(questions: List[Dict],
                   existing_path: str,
                   sheet_name: str = "Sheet1") -> bool:
    """
    Append questions to existing Excel file.
    
    Args:
        questions: List of questions
        existing_path: Path to existing Excel file
        sheet_name: Sheet name to append to
        
    Returns:
        True if successful
    """
    try:
        df_existing = pd.read_excel(existing_path, sheet_name=sheet_name)
        template_columns = list(df_existing.columns)
        
        new_rows = []
        start_seq = int(df_existing.iloc[-1]["序号"]) + 1 if "序号" in df_existing.columns and len(df_existing) > 0 else 1
        
        for i, q in enumerate(questions):
            row = map_question_to_template(q, template_columns)
            if "序号" in template_columns:
                row["序号"] = start_seq + i
            new_rows.append(row)
        
        df_new = pd.DataFrame(new_rows)
        for col in template_columns:
            if col not in df_new.columns:
                df_new[col] = ""
        df_new = df_new[template_columns]
        
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        df_combined.to_excel(existing_path, index=False, engine='openpyxl')
        
        logger.info(f"Appended {len(questions)} questions to {existing_path}")
        return True
        
    except Exception as e:
        logger.error(f"Append failed: {e}")
        return False