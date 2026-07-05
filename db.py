import sqlite3
import os
from contextlib import contextmanager

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "quiz.db")


@contextmanager
def get_db():
    """SQLite 接続をコンテキストマネージャーとして提供する"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # カラム名でアクセスできるようにする
    try:
        yield conn
    finally:
        conn.close()
