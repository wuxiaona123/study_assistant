#!/usr/bin/env bash
# ============================================================
# 前端启动脚本（macOS / Linux）
# 作用：在 frontend 目录启动静态文件服务（端口 8765）
# 路径全部基于脚本所在目录，无绝对路径，可整体移动项目后直接使用
# 说明：文件名按需求指定为 start_fronted.sh
# ============================================================
set -e

# 脚本所在目录（项目根目录）
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR/frontend"

# 选择 Python 命令（前端仅用标准库 http.server，无需虚拟环境）
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "[错误] 未找到 Python，请先安装 Python 3.9 及以上版本。"
  exit 1
fi

echo "前端服务启动：http://127.0.0.1:8765"
echo "按 Ctrl+C 停止服务。"
echo "------------------------------------------------------------"
exec "$PY" -m http.server 8765
