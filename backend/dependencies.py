"""FastAPI 依赖注入 - 共享实例"""

from core.db_operations import DBOperations
from models.db_storage import DBStorage
from core.metadata_cache import MetadataCache

# 全局单例 —— 与 Tkinter 版本复用相同实例
db_ops = DBOperations()
db_storage = DBStorage()
cache = MetadataCache()


def get_db_ops() -> DBOperations:
    return db_ops


def get_db_storage() -> DBStorage:
    return db_storage


def get_cache() -> MetadataCache:
    return cache
