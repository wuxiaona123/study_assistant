#!/usr/bin/env bash
# ============================================================
# 后端启动脚本（macOS / Linux）
# 作用：创建虚拟环境 → 安装依赖 → 初始化数据库 → 启动 Flask 服务
# 路径全部基于脚本所在目录，无绝对路径，可整体移动项目后直接使用
# ============================================================
set -e

# 脚本所在目录（项目根目录）
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR/backend"

# 选择 Python 命令
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "[错误] 未找到 Python，请先安装 Python 3.9 及以上版本。"
  exit 1
fi

echo "[1/4] 准备虚拟环境..."
if [ ! -x ".venv/bin/python" ]; then
  echo "      正在创建虚拟环境 .venv ..."
  "$PY" -m venv .venv
fi

echo "[2/4] 激活虚拟环境..."
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[3/4] 安装 Python 依赖..."
python -m pip install -r requirements.txt

# 首次运行时建表（已存在则不动数据）
if [ ! -f "study_assistant.db" ]; then
  echo "      首次运行，正在初始化数据库..."
  python init_db.py
fi

echo "[4/4] 启动后端服务：http://127.0.0.1:5000"
echo "      按 Ctrl+C 停止服务。"
echo "------------------------------------------------------------"
exec python app.py
