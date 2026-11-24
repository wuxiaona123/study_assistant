@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
REM ============================================================
REM 前端启动脚本（Windows）
REM 作用：在 frontend 目录启动静态文件服务（端口 8765）
REM 路径全部基于脚本所在目录，无绝对路径，可整体移动项目后直接使用
REM ============================================================

REM 切换到脚本所在目录（项目根目录）
cd /d "%~dp0"
cd frontend

REM 选择 Python 命令：优先 python，其次 py 启动器（前端仅用标准库，无需虚拟环境）
set "PY="
where python >nul 2>nul
if not errorlevel 1 set "PY=python"
if "!PY!"=="" (
  where py >nul 2>nul
  if not errorlevel 1 set "PY=py"
)
if "!PY!"=="" (
  echo [错误] 未找到 Python，请先安装 Python 3.9 及以上版本，并加入 PATH。
  pause
  exit /b 1
)

echo 前端服务启动：http://127.0.0.1:8765
echo 关闭窗口或按 Ctrl+C 停止服务。
echo ------------------------------------------------------------
"!PY!" -m http.server 8765
pause
