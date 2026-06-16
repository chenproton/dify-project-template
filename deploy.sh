#!/bin/bash
set -euo pipefail

# ============================================================
# AI 智能体服务平台本地发布脚本（成熟版）
# ============================================================
# 用法: bash deploy.sh [job_ai|all]
#   job_ai - 只部署岗位 AI 插件
#   all    - 部署所有插件（默认）
# ============================================================

DEPLOY_TARGET="${1:-all}"
PROJECT_DIR="${PROJECT_DIR:-/opt/job-ai}"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$PROJECT_DIR/venv"

echo "=== AI 智能体服务平台本地发布 ==="
echo "发布目标: $DEPLOY_TARGET"
echo "项目目录: $PROJECT_DIR"
echo "发布时间: $(date)"
echo ""

# 检查项目目录
if [ ! -d "$PROJECT_DIR" ]; then
  echo "❌ 项目目录不存在: $PROJECT_DIR"
  echo "   请先在本地初始化部署环境，或设置 PROJECT_DIR 环境变量"
  exit 1
fi

# 初始化 Python 虚拟环境
if [ ! -d "$VENV_DIR" ]; then
  echo "[0/3] 初始化 Python 虚拟环境..."
  if ! command -v python3 &>/dev/null; then
    echo "❌ 未安装 python3"
    exit 1
  fi
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install -q -r backend/requirements.txt

echo ""
echo "[1/3] 更新后端文件..."
mkdir -p "$BACKEND_DIR/core" "$BACKEND_DIR/plugins"
cp backend/core/*.py "$BACKEND_DIR/core/"

if [ "$DEPLOY_TARGET" == "all" ] || [ "$DEPLOY_TARGET" == "job_ai" ]; then
  cp backend/plugins/job_ai.py "$BACKEND_DIR/plugins/"
fi

cp backend/app.py "$PROJECT_DIR/app.py"
echo "后端文件更新完成"

echo ""
echo "[2/3] 更新前端文件..."
mkdir -p "$FRONTEND_DIR/plugins"
cp frontend/index.html "$FRONTEND_DIR/"

if [ "$DEPLOY_TARGET" == "all" ] || [ "$DEPLOY_TARGET" == "job_ai" ]; then
  cp frontend/plugins/job_ai.html "$FRONTEND_DIR/plugins/"
fi

echo "前端文件更新完成"

# 重启服务
echo ""
echo "[3/3] 重启服务..."
pkill -f "gunicorn.*app:app" &>/dev/null || true
sleep 1

cd "$PROJECT_DIR"
nohup gunicorn -w 1 -b 0.0.0.0:5000 --timeout 300 app:app >> app.log 2>&1 &
echo "服务已启动，监听端口 5000"

sleep 3
if curl -s http://localhost:5000/health > /dev/null; then
  echo "✅ 服务验证通过！发布完成"
else
  echo "❌ 服务验证失败，请检查日志"
  echo "日志位置: $PROJECT_DIR/app.log"
  exit 1
fi

echo ""
echo "=== 本地发布完成 ==="
