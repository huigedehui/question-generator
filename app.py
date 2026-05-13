"""Web server for AI Question Generator."""
import os
import json
import tempfile
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template, Response
from werkzeug.utils import secure_filename

from modules import (
    Config, load_word_docs, APIClient,
    QuestionValidator, clean_questions, sample_questions,
    export_to_excel, QuestionCache
)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

ALLOWED_EXTENSIONS = {'docx', 'txt'}

# Global state for controlling generation
generation_state = {
    'running': False,
    'stop_requested': False,
    'current_questions': [],
    'output_path': ''
}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def log_msg(msg):
    return f"data: {json.dumps({'type': 'log', 'message': msg})}\n\n"


def make_prompt(chunk):
    return f"""请基于以下知识内容生成考试题目。

题目类型包括: 单选、多选、判断、问答

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


@app.route('/api/stop', methods=['POST'])
def stop_generation():
    """Stop the current generation and save progress"""
    generation_state['stop_requested'] = True
    return jsonify({'success': True, 'message': '正在停止生成...'}), 200


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current generation status"""
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
        output_path = data.get('outputPath', generation_state['output_path'] or '生成试卷.xlsx')

        if generation_state['current_questions']:
            export_to_excel({'单选': generation_state['current_questions']}, '', output_path)
            return jsonify({'success': True, 'filePath': output_path, 'count': len(generation_state['current_questions'])})
        else:
            return jsonify({'success': False, 'error': '没有可保存的题目'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/generate', methods=['POST'])
def generate():
    # Reset state
    generation_state['running'] = True
    generation_state['stop_requested'] = False
    generation_state['current_questions'] = []

    # First, collect all form data BEFORE yielding anything
    api_key = request.form.get('apiKey', '')
    api_base = request.form.get('apiBase', 'https://open.bigmodel.cn/api/paas/v4')
    model = request.form.get('model', 'glm-4-flash-250414')

    if not api_key:
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
    generation_state['output_path'] = output_path
    category = request.form.get('category', '考试')
    difficulty = request.form.get('difficulty', '一般')
    max_retries = int(request.form.get('maxRetries', 3))

    # Check files
    files = request.files.getlist('documents')
    if not files or all(f.filename == '' for f in files):
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
        generation_state['running'] = False
        return Response(f"data: {json.dumps({'type': 'error', 'message': '没有有效的文档文件'})}\n\n",
                        mimetype='text/event-stream')

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
                generation_state['running'] = False
                return

            yield log_msg("开始生成题目...")

            for i, chunk in enumerate(chunks):
                # Check stop signal
                if generation_state['stop_requested']:
                    yield log_msg("用户已请求停止，正在保存当前进度...")
                    break

                yield log_msg(f"处理知识块 {i+1}/{len(chunks)}...")
                try:
                    resp = api_client.call(make_prompt(chunk))
                    if resp.success and resp.content:
                        qs = json.loads(resp.content)
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

            yield log_msg(f"共生成 {len(generation_state['current_questions'])} 道题目")

            # Check stop signal before validation
            if generation_state['stop_requested'] or not generation_state['current_questions']:
                if generation_state['current_questions']:
                    yield log_msg("保存已生成的题目...")
                generation_state['running'] = False
                result = {
                    'type': 'result',
                    'totalQuestions': len(generation_state['current_questions']),
                    'singleCount': len(generation_state['current_questions']),
                    'multiCount': 0,
                    'otherCount': 0,
                    'filePath': output_path,
                    'stopped': True
                }
                yield f"data: {json.dumps(result)}\n\n"
                return

            # Validate
            yield log_msg("验证和清洗数据...")
            validator = QuestionValidator(config)
            valid_questions, _ = validator.validate_batch(generation_state['current_questions'])
            cleaned = clean_questions(valid_questions, validator)
            yield log_msg(f"有效题目: {len(cleaned)} 道")

            # Sample
            yield log_msg("随机抽取题目...")
            final_questions = sample_questions(cleaned, sampling_config)

            # Export
            yield log_msg("导出到 Excel...")
            try:
                export_to_excel(final_questions, '', output_path, category=category, difficulty=difficulty)
                yield log_msg("导出完成!")
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'导出失败: {str(e)}'})}\n\n"

            result = {
                'type': 'result',
                'totalQuestions': sum(len(v) for v in final_questions.values()),
                'singleCount': len(final_questions.get('单选', [])),
                'multiCount': len(final_questions.get('多选', [])),
                'otherCount': len(final_questions.get('判断', [])) + len(final_questions.get('问答', [])),
                'filePath': output_path
            }
            yield f"data: {json.dumps(result)}\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            generation_state['running'] = False

    return Response(generate_response(), mimetype='text/event-stream')


@app.route('/api/download/<path:filename>')
def download(filename):
    import urllib.parse
    filepath = Path(urllib.parse.unquote(filename))
    # Try current directory first
    if not filepath.exists():
        filepath = Path.cwd() / filename
    if filepath.exists():
        return send_file(filepath, as_attachment=True)
    return jsonify({'error': f'File not found: {filename}'}), 404


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"启动 AI 题库生成器 Web 服务... (端口: {port})")
    app.run(debug=False, host='0.0.0.0', port=port)