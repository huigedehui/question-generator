#!/bin/bash
# AI 题库生成器 启动脚本

echo "========================================"
echo "   AI 题库生成器 v1.0.0"
echo "========================================"
echo ""

# 检查 Python
if ! command -v python &> /dev/null; then
    echo "错误: 未找到 Python，请先安装 Python 3.8+"
    exit 1
fi

# 安装依赖
echo "正在检查依赖..."
pip install -r requirements.txt -q

# 启动服务
echo "启动服务..."
python app.py