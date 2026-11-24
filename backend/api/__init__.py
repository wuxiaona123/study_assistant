"""按 5 个功能注册蓝图。接口业务逻辑在后续阶段实现。"""

from . import chat, documents, progress, quiz, reports

BLUEPRINTS = (documents.bp, chat.bp, quiz.bp, progress.bp, reports.bp)


def register_blueprints(app):
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)
