#!/bin/bash
set -e

# ============================================================
# AI 智能体服务平台本地发布脚本
# ============================================================
# 用法: bash deploy.sh [job_ai|all]
#   job_ai - 只部署岗位 AI 插件
#   all    - 部署所有插件（默认）
# ============================================================

DEPLOY_TARGET="${1:-all}"
PROJECT_DIR="/opt/job-ai"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

echo "=== AI 智能体服务平台本地发布 ==="
echo "发布目标: $DEPLOY_TARGET"
echo "发布时间: $(date)"
echo ""

# 更新后端文件
echo "[1/2] 更新后端文件..."
cp backend/core/*.py "$BACKEND_DIR/core/"

if [ "$DEPLOY_TARGET" == "all" ] || [ "$DEPLOY_TARGET" == "job_ai" ]; then
    cp backend/plugins/job_ai.py "$BACKEND_DIR/plugins/"
fi

cp backend/app.py "$PROJECT_DIR/app.py"
echo "后端文件更新完成"

# 更新前端文件
echo "[2/2] 更新前端文件..."
cp frontend/index.html "$FRONTEND_DIR/"

if [ "$DEPLOY_TARGET" == "all" ] || [ "$DEPLOY_TARGET" == "job_ai" ]; then
    cp frontend/plugins/job_ai.html "$FRONTEND_DIR/plugins/"
fi

echo "前端文件更新完成"

# 重启服务
echo ""
echo "重启服务..."
bash "$PROJECT_DIR/start.sh"

sleep 3
if curl -s http://localhost:5000/ > /dev/null; then
    echo "✅ 服务验证通过！发布完成"
else
    echo "❌ 服务验证失败，请检查日志"
    echo "日志位置: $PROJECT_DIR/app.log"
fi

echo ""
echo "=== 本地发布完成 ==="
