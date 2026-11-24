"""做测评接口：AI 出题、提交阅卷、历史查询。"""

from flask import Blueprint, jsonify, request

from extensions import db
from llm import LLMError, generate_quiz_questions, grade_quiz
from models import KnowledgePoint, Question, Quiz, QuizAnswer

bp = Blueprint("quiz", __name__, url_prefix="/api/quiz")


def _error(message, code):
    return jsonify({"error": message}), code


def _allocate(data):
    """题型数量：优先用显式 count；否则按总数换算 1/2 选择 + 1/4 判断 + 余下简答。"""
    if all(key in data for key in ("choiceCount", "judgeCount", "shortCount")):
        return int(data["choiceCount"]), int(data["judgeCount"]), int(data["shortCount"])
    total = int(data.get("total") or 8)
    choice = round(total * 0.5)
    judge = round(total * 0.25)
    short = total - choice - judge
    return choice, judge, short


@bp.post("/generate")
def generate():
    data = request.get_json(silent=True) or {}
    doc_ids = data.get("docIds") or []
    choice_count, judge_count, short_count = _allocate(data)
    if choice_count + judge_count + short_count <= 0:
        return _error("题数必须大于 0", 400)

    try:
        questions = generate_quiz_questions(
            doc_ids, choice_count, judge_count, short_count
        )
    except LLMError as exc:
        return _error(str(exc), 502)
    if not questions:
        return _error("AI 未生成任何题目，请检查所选资料是否已解析完成", 502)

    quiz = Quiz(doc_ids=doc_ids, total=len(questions))
    db.session.add(quiz)
    db.session.flush()

    # 知识点按 (文档, 名称) 去重；多文档时题目归属取第一个选中文档，保证知识点有来源文档
    kp_doc_id = doc_ids[0] if doc_ids else None

    def resolve_kp(name):
        name = str(name or "").strip()
        if not name or kp_doc_id is None:
            return None
        kp = KnowledgePoint.query.filter_by(document_id=kp_doc_id, name=name).first()
        if kp is None:
            kp = KnowledgePoint(document_id=kp_doc_id, name=name, description=name)
            db.session.add(kp)
            db.session.flush()
        return kp.id

    for item in questions:
        qtype = item.get("type")
        if qtype not in ("choice", "judge", "short"):
            continue
        db.session.add(
            Question(
                quiz_id=quiz.id,
                knowledge_point_id=resolve_kp(item.get("knowledge_point")),
                type=qtype,
                difficulty=item.get("difficulty") or "中等",
                question=item.get("question", ""),
                options=item.get("options") if qtype == "choice" else None,
                answer=str(item.get("answer", "")) if item.get("answer") is not None else None,
                key_points=item.get("key_points") if qtype == "short" else None,
                source=item.get("source"),
                score=1,
            )
        )
    db.session.commit()

    # 生成阶段不返回答案
    saved = (
        Question.query.filter_by(quiz_id=quiz.id).order_by(Question.id).all()
    )
    return jsonify(
        {
            "quizId": quiz.id,
            "questions": [
                {
                    "questionId": row.id,
                    "type": row.type,
                    "difficulty": row.difficulty,
                    "question": row.question,
                    "options": row.options,
                }
                for row in saved
            ],
        }
    )


@bp.post("/<int:quiz_id>/submit")
def submit(quiz_id):
    quiz = db.session.get(Quiz, quiz_id)
    if quiz is None:
        return _error("测评不存在", 404)

    data = request.get_json(silent=True) or {}
    answers = data.get("answers") or []

    questions = (
        Question.query.filter_by(quiz_id=quiz_id).order_by(Question.id).all()
    )
    by_id = {row.id: row for row in questions}
    q_payload = [
        {
            "question_id": row.id,
            "type": row.type,
            "question": row.question,
            "answer": row.answer,
            "key_points": row.key_points,
        }
        for row in questions
    ]
    a_payload = [
        {
            "question_id": item.get("questionId"),
            "answer": item.get("answer"),
        }
        for item in answers
    ]

    try:
        graded = grade_quiz(q_payload, a_payload)
    except LLMError as exc:
        return _error(str(exc), 502)

    results = graded.get("results", [])
    graded_by_id = {}
    for item in results:
        try:
            graded_by_id[int(item.get("question_id"))] = item
        except (TypeError, ValueError):
            continue

    score = 0
    for item in answers:
        qid = item.get("questionId")
        row = by_id.get(qid)
        if row is None:
            continue
        judgement = graded_by_id.get(qid, {})
        try:
            point = float(judgement.get("score", 0))
        except (TypeError, ValueError):
            point = 0
        score += point
        correct = judgement.get("correct")
        db.session.add(
            QuizAnswer(
                quiz_id=quiz_id,
                question_id=qid,
                user_answer=str(item.get("answer", "")),
                correct=bool(correct) if isinstance(correct, bool) else None,
                score=point,
                feedback=judgement.get("feedback"),
            )
        )

    quiz.score = score
    db.session.commit()

    # 按知识点重算掌握度 = 该知识点所有已作答题目得分率的平均
    touched_kp_ids = {
        row.knowledge_point_id
        for qid, row in by_id.items()
        if row.knowledge_point_id is not None and qid in {i.get("questionId") for i in answers}
    }
    for kp_id in touched_kp_ids:
        kp_rows = Question.query.filter_by(knowledge_point_id=kp_id).all()
        kp_qids = {row.id for row in kp_rows}
        kp_answers = QuizAnswer.query.filter(QuizAnswer.question_id.in_(kp_qids)).all()
        if kp_answers:
            mastery = sum(float(a.score) for a in kp_answers) / len(kp_answers)
            kp = db.session.get(KnowledgePoint, kp_id)
            if kp:
                kp.mastery = round(mastery, 2)
    db.session.commit()

    return jsonify(
        {
            "score": score,
            "total": float(quiz.total),
            "results": results,
            "weakPoints": graded.get("weak_points", []),
        }
    )


@bp.get("/history")
def history():
    rows = Quiz.query.order_by(Quiz.created_at.desc()).all()
    return jsonify(
        {
            "quizzes": [
                {
                    "quizId": row.id,
                    "score": float(row.score) if row.score is not None else None,
                    "total": float(row.total),
                    "createdAt": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]
        }
    )


@bp.get("/<int:quiz_id>")
def get_quiz(quiz_id):
    quiz = db.session.get(Quiz, quiz_id)
    if quiz is None:
        return _error("测评不存在", 404)
    questions = Question.query.filter_by(quiz_id=quiz_id).order_by(Question.id).all()
    answers = QuizAnswer.query.filter_by(quiz_id=quiz_id).all()
    answer_by_qid = {row.question_id: row for row in answers}

    question_items = []
    for row in questions:
        item = {
            "questionId": row.id,
            "type": row.type,
            "difficulty": row.difficulty,
            "question": row.question,
            "options": row.options,
            "answer": row.answer,
            "keyPoints": row.key_points,
            "source": row.source,
        }
        ans = answer_by_qid.get(row.id)
        if ans is not None:
            item["userAnswer"] = ans.user_answer
            item["correct"] = ans.correct
            item["score"] = float(ans.score)
            item["feedback"] = ans.feedback
        question_items.append(item)

    return jsonify(
        {
            "quizId": quiz.id,
            "score": float(quiz.score) if quiz.score is not None else None,
            "total": float(quiz.total),
            "createdAt": quiz.created_at.isoformat() if quiz.created_at else None,
            "questions": question_items,
            "answers": [
                {
                    "questionId": row.question_id,
                    "userAnswer": row.user_answer,
                    "correct": row.correct,
                    "score": float(row.score),
                    "feedback": row.feedback,
                }
                for row in answers
            ],
        }
    )
