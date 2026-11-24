"""全局扩展实例，单独成文件以避免循环导入。"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
