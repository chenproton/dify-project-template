# ============================================================
# 方法A 工具安装：dify-workflow CLI（dify-ai-workflow-tools）
# ============================================================
# 从 GitHub 拉取源码并安装到 tools/venv，提供：
#   tools/venv/bin/dify-workflow  —— 校验/布局/导出/remote push/pull
#   tools/venv/bin/python        —— 运行 scripts/generate_dsl_cli.py
# 用法: bash tools/install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOLS_DIR="$(dirname "$SCRIPT_DIR")/tools"
VENV_DIR="$TOOLS_DIR/venv"
SRC_DIR="$TOOLS_DIR/dify-workflow-cli"

echo "=== 安装 dify-workflow CLI (方法A) ==="

# 1. 下载源码（优先 codeload tarball，失败则 git clone）
if [ ! -d "$SRC_DIR" ]; then
  echo "[1/3] 下载 dify-workflow-cli 源码..."
  mkdir -p "$TOOLS_DIR"
  TARBALL="$TOOLS_DIR/dify-workflow-cli.tar.gz"
  curl -sL --retry 3 -o "$TARBALL" \
    https://codeload.github.com/Akabane71/dify-workflow-cli/tar.gz/refs/heads/main
  tar xzf "$TARBALL" -C "$TOOLS_DIR"
  mv "$TOOLS_DIR/dify-workflow-cli-main" "$SRC_DIR"
  rm -f "$TARBALL"
else
  echo "[1/3] 源码已存在: $SRC_DIR（如需更新请删除后重跑）"
fi

# 2. 创建 venv 并安装
echo "[2/3] 创建 Python venv..."
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install -q --upgrade pip
echo "[3/3] 安装 dify-workflow-cli..."
"$VENV_DIR/bin/pip" install -q -e "$SRC_DIR"

"$VENV_DIR/bin/dify-workflow" --version
echo "✅ 安装完成，可用命令:"
echo "  $VENV_DIR/bin/dify-workflow validate --strict <dsl.yml>"
echo "  $VENV_DIR/bin/dify-workflow remote push --file <dsl.yml> --app-id <id> --force"
