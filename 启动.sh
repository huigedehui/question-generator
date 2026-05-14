#!/bin/bash
# AI 题库生成器 启动脚本

echo "========================================"
echo "   AI Question Generator v1.0.0"
echo "========================================"
echo ""

# Check Python
if ! command -v python &> /dev/null; then
    echo "Error: Python not found. Please install Python 3.8+"
    exit 1
fi

# Install dependencies
echo "[1/3] Checking dependencies..."
pip install -r requirements.txt -q

# Start ngrok
echo "[2/3] Starting ngrok tunnel..."
ngrok/ngrok http 5000 --log=stdout > /dev/null 2>&1 &
NGROK_PID=$!

# Get public URL with retry
echo ""
echo "========================================"
echo "    ngrok connecting..."
for i in 1 2 3 4 5; do
    sleep 2
    PUBLIC_URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | python -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(d['tunnels'][0]['public_url'])
except: pass
" 2>/dev/null)
    if [ -n "$PUBLIC_URL" ]; then
        echo "    Public URL: $PUBLIC_URL"
        break
    fi
    echo "    Waiting for ngrok... ($i)"
done
if [ -z "$PUBLIC_URL" ]; then
    echo "    Public URL: (ngrok not ready, open http://localhost:5000 directly)"
fi
echo "========================================"
echo ""

# Start Flask
echo "[3/3] Starting Web server..."
python app.py

# Cleanup ngrok on exit
kill $NGROK_PID 2>/dev/null