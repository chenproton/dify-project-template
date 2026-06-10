#!/bin/bash
set -e

# ============================================================
# AI 智能体服务平台部署脚本
# ============================================================
# 用法: bash deploy.sh [job_ai|all]
#   job_ai - 只部署岗位 AI 插件
#   all    - 部署所有插件（默认）
# ============================================================

DEPLOY_TARGET="${1:-all}"
REMOTE_HOST="111.170.170.202"
REMOTE_USER="root"
PROJECT_DIR="/opt/job-ai"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
DSL_DIR="$PROJECT_DIR/dsl"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$PROJECT_DIR/backups/$TIMESTAMP"

# Dify 配置
# 账号: chenproton@gmail.com
# 密码: jiuyueyun12724
DIFY_SERVER="http://127.0.0.1:8081"
DIFY_APP_ID="8b559157-8d40-43c3-869f-1df7ce7b2317"
DIFY_EMAIL="chenproton@gmail.com"
DIFY_PASSWORD="jiuyueyun12724"

echo "=== AI 智能体服务平台部署脚本 ==="
echo "部署目标: $DEPLOY_TARGET"
echo "部署时间: $(date)"
echo ""

# 1. 创建备份目录
echo "[1/5] 创建备份目录..."
mkdir -p "$BACKUP_DIR"

# 2. 备份现有文件
echo "[2/5] 备份现有文件..."
cp -r "$BACKEND_DIR" "$BACKUP_DIR/backend"
cp -r "$FRONTEND_DIR" "$BACKUP_DIR/frontend"
echo "备份完成: $BACKUP_DIR"

# 3. 更新后端文件
echo "[3/5] 更新后端文件..."

# 更新核心模块
cp backend/core/*.py "$BACKEND_DIR/core/"

# 更新插件
if [ "$DEPLOY_TARGET" == "all" ] || [ "$DEPLOY_TARGET" == "job_ai" ]; then
    cp backend/plugins/job_ai.py "$BACKEND_DIR/plugins/"
fi

# 更新主入口
cp backend/app.py "$BACKEND_DIR/../app.py"

echo "后端文件更新完成"

# 4. 更新前端文件
echo "[4/5] 更新前端文件..."
cp frontend/index.html "$FRONTEND_DIR/"

if [ "$DEPLOY_TARGET" == "all" ] || [ "$DEPLOY_TARGET" == "job_ai" ]; then
    cp frontend/plugins/job_ai.html "$FRONTEND_DIR/plugins/"
fi

echo "前端文件更新完成"

# 5. 更新 Dify DSL（可选）
echo "[5/5] 更新 Dify DSL..."
if command -v dify-workflow &> /dev/null; then
    cd "$DSL_DIR"
    
    # 推送 DSL
    dify-workflow remote push \
        --file 岗位AI辅助生成_v3.yml \
        --app-id "$DIFY_APP_ID" \
        --force
    
    # 发布
    TOKEN=$(cat ~/.dify-workflow/credentials.json | python3 -c "import sys,json;print(json.load(sys.stdin)['profiles']['default']['access_token'])")
    CSRF=$(cat ~/.dify-workflow/credentials.json | python3 -c "import sys,json;print(json.load(sys.stdin)['profiles']['default']['csrf_token'])")
    
    curl -s -X POST "http://127.0.0.1:8081/console/api/apps/$DIFY_APP_ID/workflows/publish" \
        -H "Authorization: Bearer $TOKEN" \
        -H "X-CSRF-Token: $CSRF" \
        -H "Content-Type: application/json" \
        -b "csrf_token=$CSRF" \
        -d "{\"marked_name\":\"v$(date +%Y%m%d)\",\"marked_comment\":\"自动部署\"}"
    
    echo "DSL 推送并发布完成"
else
    echo "警告: dify-workflow 未安装，跳过 DSL 推送"
fi

# 6. 重启服务
echo "[6/5] 重启后端服务..."
bash "$PROJECT_DIR/start.sh"

# 7. 验证部署
echo "[7/5] 验证部署..."
sleep 3
if curl -s http://localhost:5000/ > /dev/null; then
    echo "✅ 服务验证通过！部署完成"
else
    echo "❌ 服务验证失败，请检查日志"
    echo "日志位置: $PROJECT_DIR/app.log"
fi

echo ""
echo "=== 部署完成 ==="
echo "备份目录: $BACKUP_DIR"
echo ""
echo "新增智能体部署示例:"
echo "  1. cp backend/plugins/TEMPLATE.py backend/plugins/xxx_ai.py"
echo "  2. 修改 plugins/xxx_ai.py 中的配置"
echo "  3. cp frontend/plugins/TEMPLATE.html frontend/plugins/xxx_ai.html"
echo "  4. 在 frontend/index.html 添加入口卡片"
echo "  5. 在 backend/app.py 注册 Blueprint"
echo "  6. bash deploy.sh"
