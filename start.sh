#!/bin/bash
# AI 智能体服务平台启动脚本
# 用法: bash start.sh

cd "$(dirname "$0")"
source venv/bin/activate

# 停止旧进程
pkill -f "gunicorn.*app:app" 2>/dev/null
sleep 1

# 启动服务
# 生产环境建议用 supervisor/systemd 管理
nohup gunicorn -w 1 -b 0.0.0.0:5000 --timeout 300 app:app >> app.log 2>&1 &

echo "服务已启动，监听端口 5000"
echo "日志: $(pwd)/app.log"
