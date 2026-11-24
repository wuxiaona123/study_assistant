"""文档处理：提取文字 → 切片入库，放在后台线程执行，用户不用等。"""

import threading

from extensions import db
from models import Document, DocumentChunk

CHUNK_SIZE = 800  # 每个切片累积约 800 字符


def extract_text(path, ext):
    """返回 (text, error)；error 非空表示读取失败。"""
    try:
        if ext == "pdf":
            from pypdf import PdfReader

            reader = PdfReader(path)
            return "\n".join(page.extract_text() or "" for page in reader.pages), None

        if ext == "pptx":
            from pptx import Presentation

            prs = Presentation(path)
            parts = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if shape.has_text_frame and shape.text_frame.text.strip():
                        parts.append(shape.text_frame.text)
            return "\n".join(parts), None

        if ext == "docx":
            from docx import Document as DocxDocument

            doc = DocxDocument(path)
            parts = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    cells = [cell.text for cell in row.cells if cell.text.strip()]
                    if cells:
                        parts.append("\t".join(cells))
            return "\n".join(parts), None

        if ext in ("md", "markdown", "txt"):
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                return handle.read(), None

        if ext in ("doc", "ppt"):
            return "", "旧版二进制格式无法读取文字，请另存为 .docx / .pptx 后重新上传"

        return "", f"不支持的格式：{ext}"
    except Exception as exc:  # 解析库异常统一转成失败原因，写回数据库
        return "", f"提取文字失败：{str(exc)[:200]}"


def split_chunks(text):
    """按行累积切片，Markdown 的 # 标题记为 section。返回 [(section, content)]。"""
    parts = []
    buffer = []
    size = 0
    section = ""
    for line in (line.strip() for line in text.splitlines()):
        if not line:
            continue
        if line.startswith("#"):
            section = line.lstrip("#").strip()
        if buffer and size + len(line) > CHUNK_SIZE:
            parts.append((section or None, "\n".join(buffer)))
            buffer = []
            size = 0
        buffer.append(line)
        size += len(line)
    if buffer:
        parts.append((section or None, "\n".join(buffer)))
    # 无任何切片时也存一条空记录，保证"文字已入库"的状态一致
    return parts or [(None, "")]


def _process(app, doc_id, path, ext):
    with app.app_context():
        doc = db.session.get(Document, doc_id)
        if doc is None:
            return  # 处理期间被删除

        text, error = extract_text(path, ext)
        if error:
            doc.parse_status = "failed"
            doc.fail_reason = error
        else:
            for index, (section, content) in enumerate(split_chunks(text)):
                db.session.add(
                    DocumentChunk(
                        document_id=doc_id,
                        chunk_index=index,
                        content=content,
                        section=section,
                    )
                )
            doc.parse_status = "success"
            doc.fail_reason = None
        db.session.commit()


def start_processing(app, doc_id, path, ext):
    """启动后台线程处理；上传接口立即返回，不阻塞用户。"""
    thread = threading.Thread(
        target=_process, args=(app, doc_id, path, ext), daemon=True
    )
    thread.start()
