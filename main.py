import os
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from db import DB_PATH
from routers import history, link_preview, questions, recommend, sessions, stats


def _init_db() -> None:
    """起動時に必要なテーブルが揃っていることを保証する"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id               TEXT PRIMARY KEY,
        edition          INTEGER,
        subject          TEXT,
        question_number  INTEGER,
        question_type    TEXT,
        case_text        TEXT,
        question_text    TEXT,
        is_multiple      INTEGER,
        options          TEXT,
        correct_options  TEXT,
        explanation      TEXT,
        keywords         TEXT,
        reference_links  TEXT,
        image_paths      TEXT,
        curriculum       TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id          TEXT PRIMARY KEY,
        started_at  DATETIME,
        ended_at    DATETIME,
        mode        TEXT,
        config      TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id   TEXT,
        question_id  TEXT,
        answered_at  DATETIME,
        is_correct   INTEGER,
        subject      TEXT,
        curriculum   TEXT,
        edition      INTEGER
    )
    """)

    # 既存 DB への後方互換マイグレーション
    existing = {r[1] for r in cursor.execute("PRAGMA table_info(history)")}
    if "session_id" not in existing:
        cursor.execute("ALTER TABLE history ADD COLUMN session_id TEXT")
    if "edition" not in existing:
        cursor.execute("ALTER TABLE history ADD COLUMN edition INTEGER")
    if "time_sec" not in existing:
        cursor.execute("ALTER TABLE history ADD COLUMN time_sec REAL")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subject_mapping (
        subject_old   TEXT,
        subject_new   TEXT,
        subject_group INTEGER
    )
    """)

    conn.commit()
    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_db()
    yield


app = FastAPI(
    title="社会福祉士過去問アプリ",
    description="社会福祉士国家試験の過去問学習アプリ API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    response: Response = await call_next(request)
    if request.url.path.endswith((".js", ".css", ".html")):
        response.headers["Cache-Control"] = "no-store"
    return response

# API ルーターの登録（静的ファイルより先に登録することで優先される）
app.include_router(questions.router)
app.include_router(sessions.router)
app.include_router(history.router)
app.include_router(stats.router)
app.include_router(recommend.router)
app.include_router(link_preview.router)

# 静的ファイルの配信（フロントエンド）
# フェーズ 4 で本格的な HTML/CSS/JS を配置する
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
