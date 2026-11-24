"""数据库模型：严格按《功能需求文档》第 3 节的 9 张表设计。"""

from datetime import datetime

from extensions import db

# SQLite 下 BigInteger 主键不会自增，退化为 INTEGER；其他数据库仍为 BIGINT
PK = db.BigInteger().with_variant(db.Integer, "sqlite")


class Document(db.Model):
    """3.1 documents 文档表"""

    __tablename__ = "documents"

    id = db.Column(PK, primary_key=True, autoincrement=True)
    file_name = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(32), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False, default=0)
    storage_path = db.Column(db.String(512), nullable=False)
    parse_status = db.Column(db.String(16), nullable=False, default="parsing")
    fail_reason = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class DocumentChunk(db.Model):
    """3.2 document_chunks 文档切片表（本项目不做向量检索）"""

    __tablename__ = "document_chunks"

    id = db.Column(PK, primary_key=True, autoincrement=True)
    document_id = db.Column(
        db.BigInteger, db.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    section = db.Column(db.String(255), nullable=True)
    embedding_id = db.Column(db.String(64), nullable=True)  # 按文档保留字段，闲置不用


class KnowledgePoint(db.Model):
    """3.3 knowledge_points 知识点表"""

    __tablename__ = "knowledge_points"

    id = db.Column(PK, primary_key=True, autoincrement=True)
    document_id = db.Column(
        db.BigInteger, db.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    mastery = db.Column(db.Numeric(3, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class ChatSession(db.Model):
    """3.4 chat_sessions 会话表"""

    __tablename__ = "chat_sessions"

    id = db.Column(PK, primary_key=True, autoincrement=True)
    title = db.Column(db.String(255), nullable=False, default="新对话")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ChatMessage(db.Model):
    """3.5 chat_messages 消息表"""

    __tablename__ = "chat_messages"

    id = db.Column(PK, primary_key=True, autoincrement=True)
    session_id = db.Column(
        db.BigInteger, db.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role = db.Column(db.String(16), nullable=False)  # user / assistant
    content = db.Column(db.Text, nullable=False)
    sources = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Quiz(db.Model):
    """3.6 quizzes 测评表"""

    __tablename__ = "quizzes"

    id = db.Column(PK, primary_key=True, autoincrement=True)
    doc_ids = db.Column(db.JSON, nullable=False)
    score = db.Column(db.Numeric(5, 2), nullable=True)
    total = db.Column(db.Numeric(5, 2), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Question(db.Model):
    """3.7 questions 题目表"""

    __tablename__ = "questions"

    id = db.Column(PK, primary_key=True, autoincrement=True)
    quiz_id = db.Column(
        db.BigInteger, db.ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False
    )
    knowledge_point_id = db.Column(
        db.BigInteger, db.ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True
    )
    type = db.Column(db.String(16), nullable=False)  # choice / judge / short
    difficulty = db.Column(db.String(16), nullable=True)  # 简单 / 中等 / 较难
    question = db.Column(db.Text, nullable=False)
    options = db.Column(db.JSON, nullable=True)
    answer = db.Column(db.Text, nullable=True)
    key_points = db.Column(db.JSON, nullable=True)
    source = db.Column(db.String(512), nullable=True)
    score = db.Column(db.Numeric(3, 2), nullable=False, default=1)


class QuizAnswer(db.Model):
    """3.8 quiz_answers 作答表"""

    __tablename__ = "quiz_answers"

    id = db.Column(PK, primary_key=True, autoincrement=True)
    quiz_id = db.Column(
        db.BigInteger, db.ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False
    )
    question_id = db.Column(
        db.BigInteger, db.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    user_answer = db.Column(db.Text, nullable=True)
    correct = db.Column(db.Boolean, nullable=True)
    score = db.Column(db.Numeric(3, 2), nullable=False, default=0)
    feedback = db.Column(db.Text, nullable=True)


class WeeklyReport(db.Model):
    """3.9 weekly_reports 周报表"""

    __tablename__ = "weekly_reports"

    id = db.Column(PK, primary_key=True, autoincrement=True)
    week_start = db.Column(db.Date, nullable=False)
    week_end = db.Column(db.Date, nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
