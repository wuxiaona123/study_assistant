"""聊资料接口：基于选中资料的问答、会话与消息管理。"""

from datetime import datetime

from flask import Blueprint, jsonify, request

from extensions import db
from llm import LLMError, answer_question
from models import ChatMessage, ChatSession

bp = Blueprint("chat", __name__, url_prefix="/api/chat")


def _error(message, code):
    return jsonify({"error": message}), code


@bp.post("")
def chat():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return _error("问题不能为空", 400)

    doc_ids = data.get("docIds") or []
    session = None
    if data.get("sessionId"):
        session = db.session.get(ChatSession, data["sessionId"])
        if session is None:
            return _error("会话不存在", 404)
    else:
        session = ChatSession(title=question[:20])
        db.session.add(session)
        db.session.flush()

    history = [
        {"role": msg.role, "content": msg.content}
        for msg in ChatMessage.query.filter_by(session_id=session.id).order_by(ChatMessage.id).all()
    ]

    db.session.add(ChatMessage(session_id=session.id, role="user", content=question))
    db.session.commit()

    try:
        answer, sources = answer_question(doc_ids, question, history)
    except LLMError as exc:
        return _error(str(exc), 502)

    db.session.add(
        ChatMessage(
            session_id=session.id, role="assistant", content=answer, sources=sources
        )
    )
    session.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"sessionId": session.id, "answer": answer, "sources": sources})


@bp.post("/sessions")
def create_session():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title") or "新对话").strip() or "新对话"
    session = ChatSession(title=title)
    db.session.add(session)
    db.session.commit()
    return jsonify(
        {
            "sessionId": session.id,
            "title": session.title,
            "createdAt": session.created_at.isoformat() if session.created_at else None,
        }
    )


@bp.get("/sessions")
def sessions():
    rows = ChatSession.query.order_by(ChatSession.updated_at.desc()).all()
    return jsonify(
        {
            "sessions": [
                {
                    "sessionId": row.id,
                    "title": row.title,
                    "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
                }
                for row in rows
            ]
        }
    )


@bp.get("/sessions/<int:session_id>/messages")
def messages(session_id):
    if db.session.get(ChatSession, session_id) is None:
        return _error("会话不存在", 404)
    rows = (
        ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.id).all()
    )
    return jsonify(
        {
            "messages": [
                {"role": row.role, "content": row.content, "sources": row.sources}
                for row in rows
            ]
        }
    )


@bp.delete("/sessions/<int:session_id>")
def delete_session(session_id):
    session = db.session.get(ChatSession, session_id)
    if session is None:
        return _error("会话不存在", 404)
    ChatMessage.query.filter_by(session_id=session_id).delete()
    db.session.delete(session)
    db.session.commit()
    return jsonify({"success": True})
