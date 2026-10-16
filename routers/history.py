import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from db import get_db

router = APIRouter(prefix="/api", tags=["history"])


class HistoryCreate(BaseModel):
    session_id: str
    question_id: str
    is_correct: bool
    subject: str
    curriculum: str
    edition: int
    time_sec: float | None = None
    selected_options: list[int] | None = None  # 選んだ選択肢の番号。DB には小さい順に "1,3" の形で入れる


@router.post("/history", status_code=201)
def record_answer(body: HistoryCreate):
    """解答結果を history テーブルに記録する"""
    now = datetime.now(timezone.utc).isoformat()
    selected = (
        ",".join(str(n) for n in sorted(body.selected_options))
        if body.selected_options is not None else None
    )
    with get_db() as conn:
        conn.execute(
            """INSERT INTO history
               (session_id, question_id, answered_at, is_correct, subject, curriculum, edition, time_sec, selected_options)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                body.session_id,
                body.question_id,
                now,
                1 if body.is_correct else 0,
                body.subject,
                body.curriculum,
                body.edition,
                body.time_sec,
                selected,
            ),
        )
        conn.commit()
    return {"status": "ok", "answered_at": now}


@router.delete("/history")
def reset_history():
    """解答履歴を全件削除する"""
    with get_db() as conn:
        conn.execute("DELETE FROM history")
        conn.execute("DELETE FROM sessions")
        conn.commit()
    return {"status": "ok"}


@router.get("/history/export")
def export_history_csv():
    """解答履歴を CSV 形式でダウンロードする（Gemini などでの分析用）"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT question_id, subject, edition, curriculum, is_correct, answered_at, selected_options
               FROM history
               ORDER BY answered_at DESC"""
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["問題ID", "科目", "エディション（回）", "カリキュラム", "正誤", "解答日時", "選んだ選択肢"])
    for row in rows:
        writer.writerow([
            row["question_id"],
            row["subject"],
            row["edition"],
            row["curriculum"],
            "正解" if row["is_correct"] else "不正解",
            row["answered_at"],
            row["selected_options"] or "",
        ])

    output.seek(0)
    # utf-8-sig（BOM 付き）で出力すると Excel でも文字化けしない
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=study_history.csv"},
    )
