"""Web server for AI Question Generator."""
import os
import json
import tempfile
import threading
import shutil
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template, Response
from werkzeug.utils import secure_filename

from modules import (
    Config, load_word_docs, APIClient,
    QuestionValidator, clean_questions, sample_questions,
    export_to_excel, QuestionCache, generate_question_prompt,
    strip_markdown_fences
)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

ALLOWED_EXTENSIONS = {'docx', 'txt'}
CONFIG_FILE = Path('.api_config.json')

# Global state for controlling generation
generation_state = {
    'running': False,
    'stop_requested': False,
    'current_questions': [],
    'output_path': ''
}
state_lock = threading.Lock()


def add_timestamp(filename: str) -> str:
    """Insert timestamp before extension: 生成试卷.xlsx → 生成试卷_20260514_112233.xlsx"""
    p = Path(filename)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(p.parent / f"{p.stem}_{ts}{p.suffix}")


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def log_msg(msg):
    return f"data: {json.dumps({'type': 'log', 'message': msg})}\n\n"


def make_prompt(chunk):
    return generate_question_prompt(chunk)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/test', methods=['POST'])
def test_api():
    try:
        data = request.get_json()
        api_key = data.get('apiKey', '')
        api_base = data.get('apiBase', 'https://open.bigmodel.cn/api/paas/v4')
        model = data.get('model', 'glm-4-flash-250414')

        if not api_key:
            return jsonify({'success': False, 'error': 'API Key is required'}), 400

        config = Config(api_key=api_key, api_base=api_base, model=model)
        api_client = APIClient(config)

        import time
        start_time = time.time()
        response = api_client.call("请回复 OK", "你是一个简单的测试助手，只回复 OK。")
        latency = int((time.time() - start_time) * 1000)

        if response.success:
            return jsonify({'success': True, 'model': model, 'latency': latency})
        else:
            return jsonify({'success': False, 'error': response.error or 'Unknown error'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    if request.method == 'GET':
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
            return jsonify({'success': True, 'config': data})
        return jsonify({'success': True, 'config': {}})

    data = request.get_json()
    CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return jsonify({'success': True})


@app.route('/api/stop', methods=['POST'])
def stop_generation():
    """Stop the current generation and save progress"""
    with state_lock:
        generation_state['stop_requested'] = True
    return jsonify({'success': True, 'message': '正在停止生成...'}), 200


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current generation status"""
    with state_lock:
        return jsonify({
            'running': generation_state['running'],
            'stop_requested': generation_state['stop_requested'],
            'question_count': len(generation_state['current_questions'])
        }), 200


@app.route('/api/save', methods=['POST'])
def save_current():
    """Save current questions to file"""
    try:
        data = request.get_json()
        with state_lock:
            output_path = data.get('outputPath', generation_state['output_path'] or '生成试卷.xlsx')
            questions = generation_state['current_questions'][:]

        if questions:
            output_path = add_timestamp(output_path)
            resolved = str(Path(output_path).resolve())
            with state_lock:
                generation_state['output_path'] = resolved
            export_to_excel({'单选': questions}, '', resolved)
            return jsonify({'success': True, 'filePath': resolved, 'count': len(questions)})
        else:
            return jsonify({'success': False, 'error': '没有可保存的题目'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/generate', methods=['POST'])
def generate():
    # Reset state
    with state_lock:
        generation_state['running'] = True
        generation_state['stop_requested'] = False
        generation_state['current_questions'] = []

    # First, collect all form data BEFORE yielding anything
    api_key = request.form.get('apiKey', '')
    api_base = request.form.get('apiBase', 'https://open.bigmodel.cn/api/paas/v4')
    model = request.form.get('model', 'glm-4-flash-250414')

    if not api_key:
        with state_lock:
            generation_state['running'] = False
        return Response(f"data: {json.dumps({'type': 'error', 'message': 'API Key 不能为空'})}\n\n",
                        mimetype='text/event-stream')

    sampling_config = {
        "单选": int(request.form.get('singleCount', 150)),
        "多选": int(request.form.get('multiCount', 90)),
        "判断": int(request.form.get('tfCount', 90)),
        "问答": int(request.form.get('essayCount', 20))
    }

    chunk_size = int(request.form.get('chunkSize', 800))
    output_path = request.form.get('outputPath', '生成试卷.xlsx')
    output_path = add_timestamp(output_path)
    with state_lock:
        generation_state['output_path'] = output_path
    category = request.form.get('category', '考试')
    difficulty = request.form.get('difficulty', '一般')
    max_retries = int(request.form.get('maxRetries', 3))

    # Check files
    files = request.files.getlist('documents')
    if not files or all(f.filename == '' for f in files):
        with state_lock:
            generation_state['running'] = False
        return Response(f"data: {json.dumps({'type': 'error', 'message': '请上传至少一个文档'})}\n\n",
                        mimetype='text/event-stream')

    # Save files
    doc_paths = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            doc_paths.append(filepath)

    if not doc_paths:
        with state_lock:
            generation_state['running'] = False
        return Response(f"data: {json.dumps({'type': 'error', 'message': '没有有效的文档文件'})}\n\n",
                        mimetype='text/event-stream')

    def timeout_wrapper(generator, timeout_seconds):
        """Wrap generator with timeout check."""
        import time
        start_time = time.time()
        try:
            for chunk in generator:
                elapsed = time.time() - start_time
                if elapsed > timeout_seconds:
                    yield f"data: {json.dumps({'type': 'error', 'message': f'生成超时 ({timeout_seconds}秒)'})}\n\n"
                    break
                yield chunk
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    def generate_response():
        try:
            config = Config(api_key=api_key, api_base=api_base, model=model, max_retries=max_retries)
            api_client = APIClient(config)

            # Load documents
            yield log_msg("正在加载文档...")
            try:
                chunks = load_word_docs(doc_paths, chunk_size)
                yield log_msg(f"文档已切片，共 {len(chunks)} 个知识块")
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'加载文档失败: {str(e)}'})}\n\n"
                with state_lock:
                    generation_state['running'] = False
                return

            yield log_msg("开始生成题目...")

            for i, chunk in enumerate(chunks):
                # Check stop signal
                with state_lock:
                    stop_requested = generation_state['stop_requested']
                if stop_requested:
                    yield log_msg("用户已请求停止，正在保存当前进度...")
                    break

                yield log_msg(f"处理知识块 {i+1}/{len(chunks)}...")
                try:
                    resp = api_client.call(make_prompt(chunk))
                    if resp.success and resp.content:
                        content = strip_markdown_fences(resp.content)
                        qs = json.loads(content)
                        with state_lock:
                            if isinstance(qs, list):
                                generation_state['current_questions'].extend(qs)
                            elif isinstance(qs, dict):
                                generation_state['current_questions'].append(qs)
                            yield log_msg(f"已生成 {len(generation_state['current_questions'])} 道题目")
                    elif resp.error:
                        yield log_msg(f"API 错误: {resp.error}")
                except Exception as e:
                    yield log_msg(f"处理失败: {str(e)}")
                    continue

            with state_lock:
                yield log_msg(f"共生成 {len(generation_state['current_questions'])} 道题目")

            # Check stop signal before validation
            with state_lock:
                should_stop = generation_state['stop_requested'] or not generation_state['current_questions']
                current_questions = generation_state['current_questions'][:]
            if should_stop:
                if current_questions:
                    yield log_msg("保存已生成的题目...")
                with state_lock:
                    generation_state['running'] = False
                with state_lock:
                    stored_path = generation_state.get('output_path', output_path)
                result = {
                    'type': 'result',
                    'totalQuestions': len(current_questions),
                    'singleCount': len(current_questions),
                    'multiCount': 0,
                    'otherCount': 0,
                    'filePath': stored_path if stored_path else output_path,
                    'stopped': True
                }
                yield f"data: {json.dumps(result)}\n\n"
                return

            # Validate
            yield log_msg("验证和清洗数据...")
            validator = QuestionValidator(config)
            valid_questions, _ = validator.validate_batch(current_questions)

            yield log_msg("正在进行质量评分...")
            for q in valid_questions:
                q["_quality"] = validator.quality_score(q)
            before = len(valid_questions)
            valid_questions = [q for q in valid_questions if q["_quality"] >= 6]
            filtered = before - len(valid_questions)
            if filtered:
                yield log_msg(f"质量过滤: 移除 {filtered} 道低分题目")

            cleaned = clean_questions(valid_questions, validator)
            yield log_msg(f"有效题目: {len(cleaned)} 道")

            # Sample
            yield log_msg("随机抽取题目...")
            final_questions = sample_questions(cleaned, sampling_config)

            # Clean up internal _quality field before export
            for qs in final_questions.values():
                for q in qs:
                    q.pop("_quality", None)

            # Export
            yield log_msg("导出到 Excel...")
            try:
                resolved_output = str(Path(output_path).resolve())
                with state_lock:
                    generation_state['output_path'] = resolved_output
                export_to_excel(final_questions, '', resolved_output, category=category, difficulty=difficulty)
                yield log_msg("导出完成!")
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'导出失败: {str(e)}'})}\n\n"

            with state_lock:
                stored_path = generation_state.get('output_path', output_path)
            result = {
                'type': 'result',
                'totalQuestions': sum(len(v) for v in final_questions.values()),
                'singleCount': len(final_questions.get('单选', [])),
                'multiCount': len(final_questions.get('多选', [])),
                'otherCount': len(final_questions.get('判断', [])) + len(final_questions.get('问答', [])),
                'filePath': stored_path
            }
            yield f"data: {json.dumps(result)}\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            with state_lock:
                generation_state['running'] = False

    # Wrap with 10-minute timeout
    timeout_seconds = 600
    return Response(timeout_wrapper(generate_response(), timeout_seconds), mimetype='text/event-stream')


def cleanup_temp_files():
    """Clean up temporary upload files."""
    upload_folder = Path(app.config['UPLOAD_FOLDER'])
    if upload_folder.exists() and upload_folder.is_dir():
        try:
            shutil.rmtree(upload_folder)
            app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
        except Exception as e:
            logger = setup_logging()
            logger.warning(f"Failed to cleanup temp files: {e}")


# Register cleanup on shutdown
import atexit
atexit.register(cleanup_temp_files)


@app.route('/api/download/<path:filename>')
def download(filename):
    import urllib.parse
    filename = urllib.parse.unquote(filename)

    # Priority 1: check generation_state for absolute output path
    with state_lock:
        saved_path = generation_state.get('output_path', '')
    if saved_path and Path(saved_path).exists() and Path(saved_path).is_file():
        return send_file(Path(saved_path).resolve(), as_attachment=True)

    # Priority 2: resolve relative to CWD
    allowed_dirs = [Path.cwd().resolve(), Path(app.config['UPLOAD_FOLDER']).resolve()]
    filepath = (Path.cwd() / filename).resolve()
    if filepath.exists() and filepath.is_file():
        if any(str(filepath).startswith(str(d)) for d in allowed_dirs):
            return send_file(filepath, as_attachment=True)

    # Priority 3: search CWD by basename (handles path prefix differences)
    from glob import glob as glob_search
    matches = glob_search(str(Path.cwd() / filename), recursive=False)
    if matches:
        fp = Path(matches[0]).resolve()
        if any(str(fp).startswith(str(d)) for d in allowed_dirs):
            return send_file(fp, as_attachment=True)

    return jsonify({'error': f'File not found: {filename}'}), 404


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"启动 AI 题库生成器 Web 服务... (端口: {port})")
    app.run(debug=False, host='0.0.0.0', port=port)