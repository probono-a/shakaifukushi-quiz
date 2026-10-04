import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from db import open_initialized_db
from routers import history, link_preview, questions, recommend, sessions, stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    open_initialized_db().close()
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
