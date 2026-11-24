"""传资料接口：上传后后台异步解析，列表/状态查询，删除时清理文件与记录。"""

import os
import uuid

from flask import Blueprint, current_app, jsonify, request

from document_processor import start_processing
from extensions import db
from models import Document, DocumentChunk

bp = Blueprint("documents", __name__, url_prefix="/api/documents")


def _ext_of(filename):
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _error(message, code):
    return jsonify({"error": message}), code


@bp.post("/upload")
def upload():
    file = request.files.get("file")
    if file is None or not file.filename:
        return _error("未选择文件", 400)

    ext = _ext_of(file.filename)
    if ext not in current_app.config["ALLOWED_EXTENSIONS"]:
        return _error("不支持的文件格式", 400)

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    storage_name = uuid.uuid4().hex + "." + ext
    storage_path = os.path.join(upload_dir, storage_name)
    file.save(storage_path)

    doc = Document(
        file_name=file.filename,
        file_type=ext,
        file_size=os.path.getsize(storage_path),
        storage_path=storage_path,
        parse_status="parsing",
    )
    db.session.add(doc)
    db.session.commit()

    # 后台慢慢跑，用户不用等
    start_processing(current_app._get_current_object(), doc.id, storage_path, ext)

    return jsonify(
        {
            "docId": doc.id,
            "fileName": doc.file_name,
            "parseStatus": doc.parse_status,
        }
    )


@bp.get("")
def list_documents():
    docs = Document.query.order_by(Document.created_at.desc()).all()
    return jsonify(
        {
            "documents": [
                {
                    "docId": doc.id,
                    "fileName": doc.file_name,
                    "fileType": doc.file_type,
                    "fileSize": doc.file_size,
                    "parseStatus": doc.parse_status,
                    "uploadTime": doc.created_at.isoformat() if doc.created_at else None,
                }
                for doc in docs
            ]
        }
    )


@bp.get("/<int:doc_id>")
def detail(doc_id):
    doc = db.session.get(Document, doc_id)
    if doc is None:
        return _error("文档不存在", 404)
    chunks = DocumentChunk.query.filter_by(document_id=doc_id).all()
    result = {
        "docId": doc.id,
        "fileName": doc.file_name,
        "fileType": doc.file_type,
        "fileSize": doc.file_size,
        "parseStatus": doc.parse_status,
        "uploadTime": doc.created_at.isoformat() if doc.created_at else None,
        "chunkCount": len(chunks),
        "sections": sorted({c.section for c in chunks if c.section}),
    }
    if doc.fail_reason:
        result["failReason"] = doc.fail_reason
    return jsonify(result)


@bp.get("/<int:doc_id>/status")
def status(doc_id):
    doc = db.session.get(Document, doc_id)
    if doc is None:
        return _error("文档不存在", 404)
    result = {"docId": doc.id, "parseStatus": doc.parse_status}
    if doc.fail_reason:
        result["failReason"] = doc.fail_reason
    return jsonify(result)


@bp.post("/<int:doc_id>/reparse")
def reparse(doc_id):
    doc = db.session.get(Document, doc_id)
    if doc is None:
        return _error("文档不存在", 404)
    if not os.path.exists(doc.storage_path):
        return _error("原文件已丢失，无法重新解析，请重新上传", 400)

    DocumentChunk.query.filter_by(document_id=doc_id).delete()
    doc.parse_status = "parsing"
    doc.fail_reason = None
    db.session.commit()
    start_processing(
        current_app._get_current_object(), doc.id, doc.storage_path, doc.file_type
    )
    return jsonify({"docId": doc.id, "parseStatus": doc.parse_status})


@bp.delete("/<int:doc_id>")
def delete(doc_id):
    doc = db.session.get(Document, doc_id)
    if doc is None:
        return _error("文档不存在", 404)

    storage_path = doc.storage_path
    DocumentChunk.query.filter_by(document_id=doc_id).delete()
    db.session.delete(doc)
    db.session.commit()
    if os.path.exists(storage_path):
        os.remove(storage_path)

    return jsonify({"success": True})
