"""出周报接口：汇总本周数据，交给 AI 撰写周报，并保存历史。"""

from datetime import date, datetime

from flask import Blueprint, jsonify, request, send_file
from io import BytesIO

from extensions import db
from llm import LLMError, generate_weekly_report
from models import Document, Quiz, QuizAnswer, Question, WeeklyReport

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


def _error(message, code):
    return jsonify({"error": message}), code


def _parse_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


@bp.post("/weekly")
def create_weekly():
    data = request.get_json(silent=True) or {}
    week_start = _parse_date(data.get("weekStart"))
    week_end = _parse_date(data.get("weekEnd"))
    if week_start is None or week_end is None:
        return _error("weekStart / weekEnd 需为 YYYY-MM-DD 格式", 400)

    start_dt = datetime.combine(week_start, datetime.min.time())
    end_dt = datetime.combine(week_end, datetime.max.time())

    docs = (
        Document.query.filter(Document.created_at >= start_dt, Document.created_at <= end_dt)
        .order_by(Document.created_at)
        .all()
    )
    quizzes = (
        Quiz.query.filter(Quiz.created_at >= start_dt, Quiz.created_at <= end_dt)
        .order_by(Quiz.created_at)
        .all()
    )
    quiz_ids = [row.id for row in quizzes]
    answers = (
        QuizAnswer.query.filter(QuizAnswer.quiz_id.in_(quiz_ids)).all()
        if quiz_ids
        else []
    )
    questions = {
        row.id: row
        for row in Question.query.filter(
            Question.id.in_([ans.question_id for ans in answers])
        ).all()
    }

    total_score = sum(float(row.score) for row in quizzes if row.score is not None)
    total_full = sum(float(row.total) for row in quizzes)
    avg_accuracy = round(total_score / total_full, 2) if total_full else 0

    weak = []
    for ans in answers:
        if float(ans.score) < 1:
            question = questions.get(ans.question_id)
            title = question.question[:60] if question else f"题目{ans.question_id}"
            if title not in weak:
                weak.append(title)

    summary = {
        "weekStart": week_start.isoformat(),
        "weekEnd": week_end.isoformat(),
        "documentCount": len(docs),
        "documents": [doc.file_name for doc in docs],
        "quizCount": len(quizzes),
        "avgAccuracy": avg_accuracy,
        "answeredCount": len(answers),
        "weakPoints": weak[:10],
    }

    try:
        content = generate_weekly_report(summary)
    except LLMError as exc:
        return _error(str(exc), 502)

    report = WeeklyReport(
        week_start=week_start, week_end=week_end, content=content
    )
    db.session.add(report)
    db.session.commit()

    return jsonify(
        {
            "reportId": report.id,
            "weekStart": week_start.isoformat(),
            "weekEnd": week_end.isoformat(),
            "content": content,
            "createdAt": report.created_at.isoformat() if report.created_at else None,
        }
    )


@bp.get("/weekly")
def list_weekly():
    rows = WeeklyReport.query.order_by(WeeklyReport.created_at.desc()).all()
    return jsonify(
        {
            "reports": [
                {
                    "reportId": row.id,
                    "weekStart": row.week_start.isoformat(),
                    "weekEnd": row.week_end.isoformat(),
                    "createdAt": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]
        }
    )


@bp.get("/weekly/<int:report_id>/download")
def download_weekly(report_id):
    report = db.session.get(WeeklyReport, report_id)
    if report is None:
        return _error("周报不存在", 404)
    header = (
        f"# 学习周报（{report.week_start.isoformat()} ~ {report.week_end.isoformat()}）\n\n"
    )
    content = (header + report.content).encode("utf-8")
    filename = f"周报_{report.week_start.isoformat()}_{report.week_end.isoformat()}.md"
    return send_file(
        BytesIO(content),
        mimetype="text/markdown; charset=utf-8",
        as_attachment=True,
        download_name=filename,
    )


@bp.get("/weekly/<int:report_id>")
def get_weekly(report_id):
    report = db.session.get(WeeklyReport, report_id)
    if report is None:
        return _error("周报不存在", 404)
    return jsonify(
        {
            "reportId": report.id,
            "weekStart": report.week_start.isoformat(),
            "weekEnd": report.week_end.isoformat(),
            "content": report.content,
            "createdAt": report.created_at.isoformat() if report.created_at else None,
        }
    )
