import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db import get_db

router = APIRouter(prefix="/api", tags=["sessions"])


class SessionCreate(BaseModel):
    mode: str  # "subject" / "wrong_only" / "random" / "edition"
    config: dict = {}


@router.post("/sessions", status_code=201)
def create_session(body: SessionCreate):
    """新しい学習セッションを開始する"""
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO sessions (id, started_at, mode, config) VALUES (?, ?, ?, ?)",
            (session_id, now, body.mode, json.dumps(body.config, ensure_ascii=False)),
        )
        conn.commit()
    return {"id": session_id, "started_at": now}


@router.patch("/sessions/{session_id}")
def end_session(session_id: str):
    """学習セッションを終了する"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found")
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ?",
            (now, session_id),
        )
        conn.commit()
    return {"id": session_id, "ended_at": now}
