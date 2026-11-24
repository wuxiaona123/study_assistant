@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
REM ============================================================
REM 后端启动脚本（Windows）
REM 作用：创建虚拟环境 → 安装依赖 → 初始化数据库 → 启动 Flask 服务
REM 路径全部基于脚本所在目录，无绝对路径，可整体移动项目后直接使用
REM ============================================================

REM 切换到脚本所在目录（项目根目录）
cd /d "%~dp0"
cd backend

REM 选择 Python 命令：优先 python，其次 py 启动器
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

echo [1/4] 准备虚拟环境...
if not exist ".venv\Scripts\python.exe" (
  echo       正在创建虚拟环境 .venv ...
  "!PY!" -m venv .venv
)

echo [2/4] 激活虚拟环境...
call .venv\Scripts\activate.bat

echo [3/4] 安装 Python 依赖...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo [错误] 依赖安装失败，请检查网络或 requirements.txt。
  pause
  exit /b 1
)

REM 首次运行时建表（已存在则不动数据）
if not exist "study_assistant.db" (
  echo       首次运行，正在初始化数据库...
  python init_db.py
)

echo [4/4] 启动后端服务：http://127.0.0.1:5000
echo       关闭窗口或按 Ctrl+C 停止服务。
echo ------------------------------------------------------------
python app.py
pause
