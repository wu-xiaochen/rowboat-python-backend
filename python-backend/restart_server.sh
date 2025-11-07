#!/bin/bash

echo "╔════════════════════════════════════════════════════════════╗"
echo "║                                                            ║"
echo "║           🔄 重启 Rowboat 后端服务器                      ║"
echo "║                                                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# 查找运行中的进程
PID=$(ps aux | grep "uvicorn.*main" | grep -v grep | awk '{print $2}')

if [ -z "$PID" ]; then
    echo "⚠️  未找到运行中的服务器"
else
    echo "🛑 停止运行中的服务器 (PID: $PID)..."
    kill $PID
    sleep 2
    
    # 确认进程已停止
    if ps -p $PID > /dev/null 2>&1; then
        echo "⚠️  进程仍在运行，强制终止..."
        kill -9 $PID
        sleep 1
    fi
    
    echo "✅ 服务器已停止"
fi

echo ""
echo "🚀 启动新服务器..."
echo ""

# 切换到脚本所在目录
cd "$(dirname "$0")"

# 激活虚拟环境
source venv/bin/activate

# 启动服务器
nohup python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &

NEW_PID=$!
echo "✅ 服务器已启动 (PID: $NEW_PID)"
echo ""

# 等待服务器启动
echo "⏳ 等待服务器初始化..."
sleep 3

# 检查服务器状态
if ps -p $NEW_PID > /dev/null 2>&1; then
    echo "✅ 服务器运行正常"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🌐 访问地址:"
    echo "  • API 文档: http://localhost:8000/docs"
    echo "  • Composio 状态: http://localhost:8000/api/tools/composio/status"
    echo "  • 日志文件: $(pwd)/server.log"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📝 查看日志: tail -f server.log"
    echo ""
else
    echo "❌ 服务器启动失败"
    echo "📋 检查日志: cat server.log"
    exit 1
fi

