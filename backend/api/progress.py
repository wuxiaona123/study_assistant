"""看进度接口：总览统计、知识点掌握度、薄弱点。

掌握度来自题库作答（提交阅卷时写入 knowledge_points.mastery）；
未作过任何题的知识点 mastery=0，状态为 unlearned。
"""

from flask import Blueprint, jsonify

from extensions import db
from models import Document, KnowledgePoint, Question, Quiz, QuizAnswer

bp = Blueprint("progress", __name__, url_prefix="/api/progress")

MASTERED_THRESHOLD = 0.8  # 掌握度 ≥ 0.8 记为已掌握


def _status(mastery, answered):
    if not answered:
        return "unlearned"
    if float(mastery or 0) >= MASTERED_THRESHOLD:
        return "mastered"
    return "weak"


def _point_items():
    rows = KnowledgePoint.query.order_by(KnowledgePoint.id).all()
    # 有作答记录才算「学过」；答错得分 0 也应判 weak，而非 unlearned
    answered_ids = {
        row[0]
        for row in db.session.query(Question.knowledge_point_id)
        .join(QuizAnswer, QuizAnswer.question_id == Question.id)
        .filter(Question.knowledge_point_id.isnot(None))
        .distinct()
        .all()
    }
    return [
        {
            "knowledgePointId": row.id,
            "name": row.name,
            "mastery": round(float(row.mastery or 0), 2),
            "status": _status(row.mastery, row.id in answered_ids),
            "docId": row.document_id,
        }
        for row in rows
    ]


@bp.get("/overview")
def overview():
    document_count = Document.query.count()
    quizzes = Quiz.query.all()
    quiz_count = len(quizzes)
    scored = [row for row in quizzes if row.score is not None and float(row.total) > 0]
    avg_accuracy = (
        round(sum(float(q.score) / float(q.total) for q in scored) / len(scored), 2)
        if scored
        else 0
    )
    return jsonify(
        {
            "documentCount": document_count,
            "quizCount": quiz_count,
            "avgAccuracy": avg_accuracy,
        }
    )


@bp.get("/knowledge-points")
def knowledge_points():
    return jsonify({"points": _point_items()})


@bp.get("/weak-points")
def weak_points():
    weak = [item for item in _point_items() if item["status"] == "weak"]
    return jsonify({"weakPoints": weak, "count": len(weak)})
