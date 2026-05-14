# AI 题库生成器

基于 AI 大模型，自动从 Word 文档生成考试题库。

## 功能特性

- 📄 支持 Word (.docx) 和文本 (.txt) 文档
- 🎯 支持单选、多选、判断、问答四种题型
- 🔧 支持多种 AI 模型（智谱、OpenAI、DeepSeek 等）
- 🔒 API Key 本地管理，安全可靠
- ⏸️ 支持暂停保存，随时中断继续
- 📊 实时进度显示
- 📥 Excel 格式导出，即拷即用

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

推荐使用智谱 AI（免费模型）：

- 注册：https://www.bigmodel.cn
- 获取 API Key：控制台 → API Keys → 创建密钥
- 免费模型：`glm-4-flash-250414`、`glm-4.7-flash`

### 3. 启动服务

```bash
cd question_generator
python app.py
```

浏览器打开：http://localhost:5000

### 4. 使用步骤

1. 填入 API Key，点击"测试连接"验证
2. 上传 Word 文档
3. 设置各题型数量
4. 点击"开始生成"
5. 可随时点击"暂停并保存"

## 支持的模型

| 模型 | 类型 | 说明 |
|------|------|------|
| GLM-4-Flash | 免费 | 128K上下文，推荐使用 |
| GLM-4.7-Flash | 免费 | 200K上下文，代码能力强 |
| GLM-Z1-Flash | 免费 | 推理专用 |
| GPT-4o-mini | 付费 | OpenAI 模型 |
| DeepSeek-V3 | 付费 | 国产高性能模型 |

## 命令行使用

```bash
# 基本用法
python main.py 文档.docx -o 输出.xlsx

# 指定模型和数量
python main.py 文档.docx --model glm-4-flash-250414 --single 100 --multi 50

# 查看帮助
python main.py --help
```

## 项目结构

```
question_generator/
├── app.py              # Web 服务入口
├── main.py             # 命令行入口
├── modules/            # 核心模块
│   ├── __init__.py
│   ├── config.py       # 配置管理
│   ├── logger.py       # 日志模块
│   ├── document.py     # 文档处理
│   ├── ai_client.py    # AI API 调用
│   ├── validator.py     # 数据验证
│   ├── sampler.py      # 题目抽样
│   ├── exporter.py     # Excel 导出
│   ├── progress.py     # 进度追踪
│   └── cache.py        # 缓存管理
├── templates/         # 前端模板
│   └── index.html     # Web 界面
├── tests/             # 单元测试
│   └── test_modules.py
└── docs/              # 文档
```

## 常见问题

### Q: 生成题目数量不对？
A: 检查设置的各类题型数量。题目会按类型分别抽取，总数可能略多或略少于设置值。

### Q: API 调用失败？
A: 检查 API Key 是否正确，余额是否充足。

### Q: 文档上传失败？
A: 确保文件格式为 .docx 或 .txt，大小不超过 50MB。

## 开发

```bash
# 运行测试
pytest tests/

# 语法检查
python -m py_compile modules/*.py
```

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交 Issue。