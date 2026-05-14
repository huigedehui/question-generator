# AI 题库生成器 — AGENTS.md

## Entrypoints

- **Web (Flask/SSE)**: `python app.py` → http://localhost:5000, binds `0.0.0.0:5000`
- **CLI**: `python main.py 文档.docx -o 输出.xlsx` (see `--help` for all options)

## Testing

```powershell
pytest tests/
```
Uses `unittest` framework, no test runner config. Single test file: `tests/test_modules.py`.

## Key architecture

- **Data flow**: Upload docs → `load_word_docs()` → `semantic_chunk_text()` (overlapping chunks split at Chinese punctuation) → `APIClient.call()` per chunk → parse JSON → `QuestionValidator.validate_batch()` → `clean_questions()` (dedup + normalize answers) → `sample_questions()` (per-type with configurable strategy) → `export_to_excel()` (template-mapped columns) → .xlsx
- **Global mutable state**: `generation_state` dict + `state_lock` in `app.py` coordinates SSE generator with `/api/stop` and `/api/status`. Single-user — not safe for concurrent requests.
- **Web uses SSE** (`text/event-stream`) with a 10-minute timeout wrapper, not WebSocket.
- **Config layers**: env vars (`OPENAI_API_KEY`, `API_BASE`, `PORT`) → `Config` dataclass defaults → `.api_config.json` (persisted from web UI, **contains secrets — in `.gitignore`**) → per-request form/arg overrides.
- **Import pattern**: `from modules import Config, APIClient, ...` — all re-exported via `modules/__init__.py`.
- **Question types (Chinese)**: 单选, 多选, 判断, 问答. Answer normalization: truthy → "正确", falsy → "错误", multi-choice sorted alphabetically.
- **Quality threshold**: Questions with `_quality < 6` are filtered after validation (`app.py:279`). The `_quality` field is stripped before Excel export.

## Production Deployment (PythonAnywhere)

- **URL**: https://gcbz123.pythonanywhere.com
- **Source dir**: `/home/gcbz123/question-generator`
- **Virtualenv**: `/home/gcbz123/question-generator/venv`
- **WSGI file**: `/var/www/gcbz123_pythonanywhere_com_wsgi.py`
- **Start command**: `gunicorn app:app`
- **After code change**: user must run `git pull` in PythonAnywhere Bash console, then click **Reload** on Web tab
- **GitHub**: https://github.com/huigedehui/question-generator

## Dev notes

- Python 3.12+ (CPython 3.14 local, 3.12 on PythonAnywhere)
- No formatter/linter config in repo — do not add without asking
- UI is Chinese, AI prompts are Chinese
- Startup scripts (`启动.bat`, `启动.sh`) optionally bundle ngrok tunnel; ngrok binary in `ngrok/`
- Config reads `OPENAI_API_KEY` and `API_BASE` env vars (see `modules/config.py`)
- CLI default model: `gpt-4o-mini`; web UI default: `glm-4-flash-250414` (Zhipu free tier)
- Temp deploy scripts (`deploy_*.py`, `debug_*.py`) can be cleaned up
