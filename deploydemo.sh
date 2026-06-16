#!/bin/bash
set -euo pipefail

# ============================================================
# AI 智能体服务平台演示环境发布脚本（成熟版）
# ============================================================
# 用法: bash deploydemo.sh [job_ai|all]
#   job_ai - 只部署岗位 AI 插件
#   all    - 部署所有插件（默认）
#
# 说明：
# - 演示环境不部署 Dify 服务，复用当前环境的 Dify 接口
# - 前端 API 指向演示服务器 demo2.zhiyu.com.cn:5000
# - 后端 Dify API 指向当前环境 111.170.170.202:8081
# ============================================================

DEPLOY_TARGET="${1:-all}"
DEMO_HOST="${DEMO_HOST:-demo2.zhiyu.com.cn}"
DEMO_USER="${DEMO_USER:-root}"
DEMO_PASS="${DEMO_PASS:-lEL9cHcBQMjCEqp6}"
OLD_API_IP="${OLD_API_IP:-111.170.170.202}"
OLD_DIFY_HOST="${OLD_DIFY_HOST:-127.0.0.1}"
DIFY_HOST="${DIFY_HOST:-111.170.170.202}"
DIFY_PORT="${DIFY_PORT:-8081}"
REMOTE_BASE="${REMOTE_BASE:-/opt/job-ai-demo}"
SSH_PORT="${SSH_PORT:-22}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 安全提示
if [ -z "${DEMO_PASS:-}" ]; then
  echo "❌ 错误：未设置 DEMO_PASS 环境变量且脚本默认密码为空"
  exit 1
fi

# 检查 sshpass
if ! command -v sshpass &>/dev/null; then
  echo "❌ 未检测到 sshpass，请先安装："
  echo "   Debian/Ubuntu: sudo apt-get install -y sshpass"
  exit 1
fi

export SSHPASS="$DEMO_PASS"
SSH_CMD="sshpass -e ssh"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=15 -o ServerAliveInterval=60 -o ServerAliveCountMax=3 -p $SSH_PORT"

echo "=== AI 智能体服务平台演示环境发布 ==="
echo "发布目标: $DEPLOY_TARGET"
echo "演示服务器: $DEMO_HOST"
echo "Dify 接口: http://$DIFY_HOST:$DIFY_PORT"
echo "发布时间: $(date)"
echo ""

# 临时替换前端 API 地址（指向演示服务器）
replace_frontend_ip() {
  find "$SCRIPT_DIR/frontend" -type f \( -name '*.html' -o -name '*.js' \) -print0 | while IFS= read -r -d '' f; do
    if grep -qF "$OLD_API_IP" "$f"; then
      sed -i "s/$OLD_API_IP/$DEMO_HOST/g" "$f"
      echo "  前端已替换: $f"
    fi
  done
}

# 临时替换后端 Dify 地址（指向当前环境的 Dify）
replace_dify_host() {
  find "$SCRIPT_DIR/backend" -type f -name '*.py' -print0 | while IFS= read -r -d '' f; do
    if grep -qF "http://$OLD_DIFY_HOST:$DIFY_PORT" "$f"; then
      sed -i "s#http://$OLD_DIFY_HOST:$DIFY_PORT#http://$DIFY_HOST:$DIFY_PORT#g" "$f"
      echo "  后端已替换: $f"
    fi
  done
}

restore_frontend_ip() {
  find "$SCRIPT_DIR/frontend" -type f \( -name '*.html' -o -name '*.js' \) -print0 | while IFS= read -r -d '' f; do
    if grep -qF "$DEMO_HOST" "$f"; then
      sed -i "s/$DEMO_HOST/$OLD_API_IP/g" "$f"
      echo "  前端已还原: $f"
    fi
  done
}

restore_dify_host() {
  find "$SCRIPT_DIR/backend" -type f -name '*.py' -print0 | while IFS= read -r -d '' f; do
    if grep -qF "http://$DIFY_HOST:$DIFY_PORT" "$f"; then
      sed -i "s#http://$DIFY_HOST:$DIFY_PORT#http://$OLD_DIFY_HOST:$DIFY_PORT#g" "$f"
      echo "  后端已还原: $f"
    fi
  done
}

restore_all() {
  echo ""
  echo ">>> 还原源码配置..."
  restore_frontend_ip
  restore_dify_host
}

trap 'restore_all' EXIT

echo "[0/3] 临时替换源码配置..."
replace_frontend_ip
replace_dify_host

echo ""
echo "[1/3] 创建远程部署目录..."
$SSH_CMD $SSH_OPTS "$DEMO_USER@$DEMO_HOST" \
  "rm -rf $REMOTE_BASE && mkdir -p $REMOTE_BASE/backend/core $REMOTE_BASE/backend/plugins $REMOTE_BASE/frontend/plugins"

echo ""
echo "[2/3] 上传项目文件..."
rsync -az --delete \
  -e "$SSH_CMD $SSH_OPTS" \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='venv' \
  --exclude='*.log' \
  "$SCRIPT_DIR/backend/" "$DEMO_USER@$DEMO_HOST:$REMOTE_BASE/backend/"
rsync -az --delete \
  -e "$SSH_CMD $SSH_OPTS" \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='venv' \
  --exclude='*.log' \
  "$SCRIPT_DIR/frontend/" "$DEMO_USER@$DEMO_HOST:$REMOTE_BASE/frontend/"

echo ""
echo "[3/3] 远程安装依赖并启动服务..."
$SSH_CMD $SSH_OPTS "$DEMO_USER@$DEMO_HOST" \
  "export REMOTE_BASE='$REMOTE_BASE'; export PYPI_MIRROR='${PYPI_MIRROR:-https://pypi.tuna.tsinghua.edu.cn/simple}'; bash -s" << 'REMOTE_EOF'
  set -e

  cd "$REMOTE_BASE"

  if ! command -v python3 &>/dev/null; then
    echo "❌ 远程服务器未安装 python3"
    exit 1
  fi

  # 初始化虚拟环境
  if [ ! -d "venv" ]; then
    python3 -m venv venv
  fi
  source venv/bin/activate

  # 配置 pip 镜像（避免超时）
  mkdir -p "$HOME/.config/pip"
  cat > "$HOME/.config/pip/pip.conf" << EOF
[global]
index-url = $PYPI_MIRROR
timeout = 120
retries = 5
EOF

  pip install -q --upgrade pip
  pip install -q -r backend/requirements.txt

  # 停止旧进程（限定路径，避免误杀）
  pkill -f "gunicorn.*$REMOTE_BASE.*app:app" &>/dev/null || true
  sleep 1

  # 使用 setsid 启动，确保脚本退出后服务继续运行
  setsid gunicorn -w 1 -b 0.0.0.0:5000 --timeout 300 --chdir backend app:app >> app.log 2>&1 < /dev/null &

  echo "服务已启动，监听端口 5000"
  echo "日志: $REMOTE_BASE/app.log"
REMOTE_EOF

sleep 3
if $SSH_CMD $SSH_OPTS "$DEMO_USER@$DEMO_HOST" "curl -s http://localhost:5000/health > /dev/null"; then
  echo "✅ 服务验证通过！"
else
  echo "❌ 服务验证失败，请检查日志"
  echo "日志位置: $REMOTE_BASE/app.log"
  exit 1
fi

echo ""
echo "=== 演示环境发布完成 ==="
echo "   访问地址: http://$DEMO_HOST:5000"
echo "   Dify 接口: http://$DIFY_HOST:$DIFY_PORT"
echo ""
