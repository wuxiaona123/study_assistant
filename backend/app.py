"""Flask 应用工厂。"""

from flask import Flask, jsonify

from api import register_blueprints
from config import Config
from extensions import db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    register_blueprints(app)

    @app.get("/api/health")
    def health():
        # 前端 api.js 用这个接口判断右上角状态点是否亮绿
        return jsonify({"status": "ok"})

    @app.after_request
    def add_cors_headers(response):
        # 前端静态服务与后端端口不同，允许跨域联调
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
        return response

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
