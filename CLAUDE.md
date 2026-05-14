# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered Chinese exam question generator. Uploads Word/text documents, uses OpenAI-compatible LLM APIs to generate questions, validates/cleans/samples them, and exports formatted Excel files. All UI text, AI prompts, and output are in Chinese. Two entry points: Flask web app (primary) and CLI.

## Commands

```powershell
# Install dependencies
pip install -r requirements.txt

# Run web app (http://localhost:5000)
python app.py

# Run CLI
python main.py 文档.docx -o 输出.xlsx --api-key KEY --model glm-4-flash-250414

# Run all tests
pytest tests/

# Package
python setup.py sdist
```

## Architecture

```
Entry Points          modules/ (shared business logic)
─────────────         ─────────────────────────────────
app.py (Flask/SSE) →  config → document → ai_client → validator → sampler → exporter
main.py (CLI)     →  (same pipeline, orchestrated differently)
                      progress (CLI only) | cache (CLI only) | logger (cross-cutting)
```

**Data flow:** Upload docs → `load_word_docs()` → `semantic_chunk_text()` (overlapping chunks split at Chinese punctuation) → `APIClient.call()` per chunk → parse JSON → `QuestionValidator.validate_batch()` → `clean_questions()` (dedup + normalize answers) → `sample_questions()` (per-type with configurable strategy) → `export_to_excel()` (template-mapped columns) → .xlsx download

## Key Design Details

- **Dual prompts:** Web path defines `make_prompt()` inline in `app.py`; CLI path uses `generate_question_prompt()` from `modules/ai_client.py`. These are similar but maintained separately.
- **Global mutable state:** `generation_state` dict in `app.py` coordinates SSE generator with `/api/stop` and `/api/status` endpoints. Single-user design — not safe for concurrent requests.
- **OpenAI-compatible API:** `APIClient` calls `{api_base}/chat/completions`, works with any OpenAI-format provider (Zhipu, DeepSeek, OpenAI). Default web model: `glm-4-flash-250414`.
- **Config layers:** Env vars (`OPENAI_API_KEY`, `API_BASE`, `PORT`) → `Config` dataclass defaults → `.api_config.json` (persisted from web UI) → per-request form/arg overrides.
- **Import pattern:** `from modules import Config, APIClient, ...` — all re-exported via `modules/__init__.py`.
- **Question types (Chinese):** 单选, 多选, 判断, 问答, 填空. Answer normalization: truthy → "正确", falsy → "错误", multi-choice sorted alphabetically.
- **Excel export:** Reads column names from an existing template file if provided, otherwise uses a default 15-column Chinese schema. Allows matching any LMS format.

## Dev Notes

- Python 3.12+ required
- No formatter/linter config — do not add without asking
- Frontend is a single-page app in `templates/index.html` (vanilla HTML/CSS/JS, no framework)
- Deploy scripts (`deploy_*.py`, `debug_*.py`) are temporary automation for PythonAnywhere deployment
- Production: PythonAnywhere with gunicorn, see `render.yaml` for Render config
