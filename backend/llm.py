"""LLM 客户端。

按用户要求：不使用向量模型、不做 RAG。
聊天用关键词从选中资料中筛出相关段落；出题/周报用选中资料全文。
三套系统提示词来自《功能需求文档》第 4 节；周报提示词为本次能力补充（文档未提供）。
地址与密钥从配置读取；调用失败自动重试最多 3 次；自动去除 AI 回复外的 ```json``` 包裹。
"""

import json
import re
import time
import urllib.error
import urllib.request

from flask import current_app

# ---------- 4.1 日常聊天 —— 学习导师（文档原文） ----------
TUTOR_PROMPT = """# Role
你是「学习助手」的 AI 学习导师，专门辅导用户学习大模型（LLM）相关课程。

# Context
你会收到用户的问题，以及从用户上传资料（PDF / PPT / Markdown）中检索出的相关片段，
片段放在 <参考资料> 标签内。

# Task
依据参考资料回答用户问题；资料不足以回答时如实说明，不得编造。

# 风格要求
- 有洞察：点明"为什么"，帮用户建立理解，而非机械复述原文。
- 不啰嗦：先给结论再给依据，能三句话讲清就不用五句。
- 使用中文，术语准确。

# 回答规则
1. 优先基于参考资料作答，关键结论后标注来源（资料名 / 章节）。
2. 资料未覆盖时可补充自身知识，但必须明确标注"以下为补充，非来自资料"。
3. 不确定的内容直说不确定，不臆测。
4. 与学习无关的问题不予展开，礼貌拉回主题。

# 输入
<参考资料>
{{retrieved_context}}
</参考资料>
<用户问题>
{{question}}
</用户问题>
"""

# ---------- 4.2 出题 —— 出题官（文档原文） ----------
QUIZ_PROMPT = """# Role
你是「学习助手」的出题官，负责依据用户上传的资料生成测评题。

# Task
严格依据 <参考资料> 生成三类题目：单选题、判断题、简答题。

# 硬性规则
1. 只能基于参考资料出题，不得引入资料之外的知识点，不得凭常识编造。
2. 每道题都必须能在资料中找到明确依据，并标注出处（资料名 / 章节）。
3. 覆盖资料关键知识点，避免重复。
4. 题量按参数指定：{{choice_count}} 道单选、{{judge_count}} 道判断、{{short_count}} 道简答。
5. 题干清晰无歧义；单选题 4 个选项且唯一正确答案；判断题答案仅"正确"或"错误"；简答题须给出评分要点 key_points。

# 输出格式
仅输出 JSON，不得输出任何解释文字：
{
  "questions": [
    {
      "type": "choice",
      "question": "题干",
      "options": ["A...", "B...", "C...", "D..."],
      "answer": "A",
      "source": "资料名/章节",
      "knowledge_point": "知识点名称"
    },
    {
      "type": "judge",
      "question": "题干",
      "answer": "正确",
      "source": "资料名/章节",
      "knowledge_point": "知识点名称"
    },
    {
      "type": "short",
      "question": "题干",
      "answer": "参考答案",
      "key_points": ["要点1", "要点2"],
      "source": "资料名/章节",
      "knowledge_point": "知识点名称"
    }
  ]
}

# 输入
<参考资料>
{{retrieved_context}}
</参考资料>
"""

# ---------- 4.3 改卷 —— 阅卷官（文档原文） ----------
GRADER_PROMPT = """# Role
你是「学习助手」的阅卷官，负责对照标准答案为用户评分。

# Task
根据用户作答与标准答案逐题判定，给出得分与简要反馈，并指出薄弱知识点。

# 评分规则
1. 单选题、判断题为客观题，二值评分：答对得满分，答错得 0 分，不存在部分分。
2. 简答题采用 0 / 0.5 / 1 三档：
   - 1 分：覆盖全部关键要点，表述准确；
   - 0.5 分：覆盖部分关键要点，或基本正确但有遗漏 / 偏差；
   - 0 分：答非所问、要点基本错误，或未作答。
3. 严格以标准答案 / key_points 为准；同义表述视为正确，不因措辞不同而误判。
4. 不额外加分，不凭主观印象给分。

# 输出格式
仅输出 JSON，不得输出任何解释文字：
{
  "results": [
    { "question_id": "...", "type": "choice", "correct": true, "score": 1, "feedback": "..." },
    { "question_id": "...", "type": "short", "score": 0.5, "feedback": "命中要点1，缺少要点2" }
  ],
  "total_score": 3.5,
  "weak_points": ["未掌握的知识点1", "未掌握的知识点2"]
}

# 输入
<题目与标准答案>
{{questions}}
</题目与标准答案>
<用户作答>
{{answers}}
</用户作答>
"""

# ---------- 周报撰写人（本次补充：文档第 4 节只有三套提示词，无周报提示词） ----------
REPORT_PROMPT = """# Role
你是「学习助手」的周报撰写人，负责根据用户本周的学习数据写一份中文学习周报。

# Task
依据 <本周数据> 写一份周报，必须包含三部分：本周学了什么、哪里薄弱、下周建议。

# 要求
- 使用 Markdown，含标题与列表；结论在前，不啰嗦。
- 只依据给出的数据陈述，不编造未提供的信息。
- 薄弱点要结合具体知识点；下周建议要针对薄弱点，具体可执行。

# 输入
<本周数据>
{{summary}}
</本周数据>
"""

MAX_RETRIES = 3  # 调用失败最多重试 3 次


class LLMError(Exception):
    """LLM 未配置、调用失败或返回无法解析。"""


def call_llm(prompt):
    """调用 OpenAI 兼容的 /chat/completions；网络错误/5xx 自动重试最多 3 次。"""
    cfg = current_app.config
    if not cfg["LLM_BASE_URL"] or not cfg["LLM_API_KEY"]:
        raise LLMError("未配置 LLM_BASE_URL 或 LLM_API_KEY，请在 backend/.env 中填写")

    payload = {
        "model": cfg["LLM_MODEL"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    url = cfg["LLM_BASE_URL"] + "/chat/completions"

    last_error = None
    for attempt in range(MAX_RETRIES):
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + cfg["LLM_API_KEY"],
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=cfg["LLM_TIMEOUT"]) as response:
                data = json.loads(response.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "ignore")[:200]
            if exc.code < 500:  # 4xx 是请求/密钥问题，重试无用
                raise LLMError(f"LLM HTTP {exc.code}: {body}") from exc
            last_error = f"LLM HTTP {exc.code}: {body}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = f"LLM 连接失败: {exc}"

        if attempt < MAX_RETRIES - 1:
            time.sleep(1 * (attempt + 1))  # 1s、2s 递增退避

    raise LLMError(f"LLM 调用失败（已重试 {MAX_RETRIES} 次）: {last_error}")


def parse_json_response(text):
    """剥掉 AI 常加的 ```json``` 包裹，解析成 dict；失败抛 LLMError。"""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        cleaned = cleaned[start : end + 1]

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMError(f"AI 返回的 JSON 无法解析: {cleaned[:200]}") from exc


def _chunks_to_context(chunks):
    """把切片列表拼成带来源标注的参考资料。"""
    from models import Document

    if not chunks:
        return ""
    ids = {chunk.document_id for chunk in chunks}
    names = {
        doc.id: doc.file_name
        for doc in Document.query.filter(Document.id.in_(ids)).all()
    }
    parts = []
    for chunk in chunks:
        name = names.get(chunk.document_id, f"文档{chunk.document_id}")
        section = f" / {chunk.section}" if chunk.section else ""
        parts.append(f"【{name}{section}】\n{chunk.content}")
    return "\n\n".join(parts)


def _chunks_to_sources(chunks):
    """把切片列表转成来源标注数组。"""
    from models import Document

    if not chunks:
        return []
    ids = {chunk.document_id for chunk in chunks}
    names = {
        doc.id: doc.file_name
        for doc in Document.query.filter(Document.id.in_(ids)).all()
    }
    result = []
    seen = set()
    for chunk in chunks:
        key = (chunk.document_id, chunk.section or "")
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "docId": chunk.document_id,
                "fileName": names.get(chunk.document_id, f"文档{chunk.document_id}"),
                "section": chunk.section or "",
            }
        )
    return result


def build_context(doc_ids):
    """选中文档的全部切片（供出题 / 周报用）。"""
    from models import DocumentChunk

    if not doc_ids:
        return ""
    chunks = (
        DocumentChunk.query.filter(DocumentChunk.document_id.in_(doc_ids))
        .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        .all()
    )
    return _chunks_to_context(chunks)


def sources_of(doc_ids):
    """选中文档的全部切片来源。"""
    from models import DocumentChunk

    if not doc_ids:
        return []
    chunks = (
        DocumentChunk.query.filter(DocumentChunk.document_id.in_(doc_ids))
        .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        .all()
    )
    return _chunks_to_sources(chunks)


def retrieve_relevant_chunks(doc_ids, question, top_n=6):
    """关键词匹配：从选中文档的切片中筛出与问题最相关的前 top_n 条（不用向量）。"""
    from models import DocumentChunk

    if not doc_ids:
        return []
    chunks = (
        DocumentChunk.query.filter(DocumentChunk.document_id.in_(doc_ids))
        .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        .all()
    )
    if not chunks:
        return []

    keywords = set(re.findall(r"[a-zA-Z0-9]{2,}", question.lower()))
    for seg in re.findall(r"[\u4e00-\u9fff]+", question):
        if len(seg) == 1:
            keywords.add(seg)
        else:
            keywords.update(seg[i : i + 2] for i in range(len(seg) - 1))

    if not keywords:
        return chunks[:top_n]

    scored = []
    for chunk in chunks:
        text = chunk.content.lower()
        hits = sum(1 for word in keywords if word in text)
        scored.append((hits, chunk))
    scored.sort(key=lambda item: (-item[0], item[1].document_id, item[1].chunk_index))

    selected = [chunk for hits, chunk in scored[:top_n] if hits > 0]
    return selected or chunks[:top_n]  # 一个都没命中时退回前几条，保证有上下文


def answer_question(doc_ids, question, history=None):
    """能力一：聊天。返回 (answer, sources)。"""
    chunks = retrieve_relevant_chunks(doc_ids, question)
    prompt = (
        TUTOR_PROMPT.replace("{{retrieved_context}}", _chunks_to_context(chunks))
        .replace("{{question}}", question)
    )
    if history:
        lines = [
            f"{'用户' if msg['role'] == 'user' else 'AI'}: {msg['content']}"
            for msg in history[-6:]
        ]
        prompt += "\n\n# 对话历史（供理解上下文，回答仍以参考资料为准）\n" + "\n".join(lines)

    return call_llm(prompt), _chunks_to_sources(chunks)


def generate_quiz_questions(doc_ids, choice_count, judge_count, short_count):
    """能力二：出题。返回 AI 生成的题目列表（含 answer/key_points，由接口层决定不外泄）。"""
    prompt = (
        QUIZ_PROMPT.replace("{{retrieved_context}}", build_context(doc_ids))
        .replace("{{choice_count}}", str(choice_count))
        .replace("{{judge_count}}", str(judge_count))
        .replace("{{short_count}}", str(short_count))
    )
    prompt += (
        "\n\n# 难度要求\n"
        "请在每道题的 JSON 中增加 difficulty 字段，取值为「简单」「中等」「较难」之一，"
        "三种难度需合理搭配。"
    )
    data = parse_json_response(call_llm(prompt))
    return data.get("questions", [])


def grade_quiz(questions, answers):
    """能力三：改卷。questions/answers 为已序列化的列表，返回评分 dict。"""
    prompt = (
        GRADER_PROMPT.replace(
            "{{questions}}", json.dumps(questions, ensure_ascii=False)
        )
        .replace("{{answers}}", json.dumps(answers, ensure_ascii=False))
    )
    return parse_json_response(call_llm(prompt))


def generate_weekly_report(summary):
    """能力四：周报。summary 为本周学习数据 dict，返回 Markdown 文本。"""
    prompt = REPORT_PROMPT.replace(
        "{{summary}}", json.dumps(summary, ensure_ascii=False)
    )
    return call_llm(prompt)
