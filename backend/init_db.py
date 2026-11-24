"""初始化数据库：按模型创建全部表（已存在的表不会被改动）。"""

import models  # noqa: F401  导入即把模型注册到 db.metadata
from app import create_app
from extensions import db

app = create_app()

with app.app_context():
    db.create_all()
    print("建表完成：" + ", ".join(sorted(db.metadata.tables.keys())))
