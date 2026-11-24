"""配置：优先读环境变量，其次读 backend/.env，最后用默认值。"""

import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    """应用配置。LLM 地址与密钥单独配置，不写死在代码里。"""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

    # 数据库：默认 SQLite（单机单用户），可用 DATABASE_URI 覆盖
    DATABASE_URI = (
        os.environ.get("DATABASE_URI")
        or "sqlite:///" + os.path.join(BASE_DIR, "study_assistant.db")
    )
    SQLALCHEMY_DATABASE_URI = DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 上传
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER") or os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 50 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {"pdf", "ppt", "pptx", "doc", "docx", "md", "markdown", "txt"}

    # 大模型：OpenAI 兼容 /chat/completions，地址与密钥单独配置
    LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "").rstrip("/")
    LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
    LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", 60))
