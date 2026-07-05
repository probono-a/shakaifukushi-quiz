from fastapi import APIRouter

from db import get_db

router = APIRouter(prefix="/api", tags=["stats"])

# 苦手問題の判定に使う最低解答回数
WEAK_MIN_ATTEMPTS = 3


@router.get("/stats")
def get_stats():
    """ダッシュボード用の集計データをまとめて返す"""
    with get_db() as conn:

        # --- 総正答率 ---
        overall = conn.execute(
            """SELECT COUNT(*) as total, SUM(is_correct) as correct,
                      ROUND(AVG(time_sec), 1) as avg_time_sec
               FROM history"""
        ).fetchone()

        # --- 科目別正答率（旧カリ名を新カリ名に統一）---
        subject_rows = conn.execute(
            """SELECT COALESCE(sm.subject_new, h.subject) AS subject,
                      COUNT(*) as total,
                      SUM(h.is_correct) as correct,
                      ROUND(AVG(h.time_sec), 1) as avg_time_sec
               FROM history h
               LEFT JOIN subject_mapping sm ON h.subject = sm.subject_old
               GROUP BY COALESCE(sm.subject_new, h.subject)
               ORDER BY subject"""
        ).fetchall()

        # --- 日次正答率（直近 30 日）---
        daily_rows = conn.execute(
            """SELECT DATE(answered_at) as date,
                      COUNT(*) as total,
                      SUM(is_correct) as correct
               FROM history
               WHERE answered_at >= DATE('now', '-30 days')
               GROUP BY DATE(answered_at)
               ORDER BY date"""
        ).fetchall()

        # --- 苦手問題 TOP 10 ---
        weak_rows = conn.execute(
            f"""SELECT h.question_id,
                       q.subject,
                       q.question_text,
                       q.edition,
                       COUNT(*) as total,
                       SUM(h.is_correct) as correct,
                       ROUND(SUM(h.is_correct) * 100.0 / COUNT(*), 1) as accuracy
                FROM history h
                JOIN questions q ON h.question_id = q.id
                GROUP BY h.question_id
                HAVING total >= {WEAK_MIN_ATTEMPTS} AND accuracy < 100
                ORDER BY accuracy ASC
                LIMIT 10"""
        ).fetchall()

        # --- 直近のセッション履歴（10 件）---
        session_rows = conn.execute(
            """SELECT s.id,
                      s.mode,
                      s.started_at,
                      s.ended_at,
                      s.config,
                      COUNT(h.id) as answered_count,
                      SUM(h.is_correct) as correct_count
               FROM sessions s
               LEFT JOIN history h ON s.id = h.session_id
               GROUP BY s.id
               ORDER BY s.started_at DESC
               LIMIT 10"""
        ).fetchall()

        # --- カリキュラム別正答率 ---
        curriculum_rows = conn.execute(
            """SELECT curriculum,
                      COUNT(*) as total,
                      SUM(is_correct) as correct
               FROM history
               WHERE curriculum IS NOT NULL
               GROUP BY curriculum"""
        ).fetchall()

    total_count = overall["total"] or 0
    correct_count = overall["correct"] or 0

    def accuracy(correct, total):
        return round(correct * 100 / total, 1) if total else 0

    return {
        "overall": {
            "total": total_count,
            "correct": correct_count,
            "accuracy": accuracy(correct_count, total_count),
            "avg_time_sec": overall["avg_time_sec"],
        },
        "by_subject": [
            {
                "subject": r["subject"],
                "total": r["total"],
                "correct": r["correct"],
                "accuracy": accuracy(r["correct"], r["total"]),
                "avg_time_sec": r["avg_time_sec"],
            }
            for r in subject_rows
        ],
        "daily_trend": [
            {
                "date": r["date"],
                "total": r["total"],
                "correct": r["correct"],
                "accuracy": accuracy(r["correct"], r["total"]),
            }
            for r in daily_rows
        ],
        "weak_questions": [
            {
                "question_id": r["question_id"],
                "subject": r["subject"],
                "edition": r["edition"],
                "question_text": (
                    r["question_text"][:80] + "…"
                    if r["question_text"] and len(r["question_text"]) > 80
                    else r["question_text"]
                ),
                "total": r["total"],
                "correct": r["correct"],
                "accuracy": r["accuracy"],
            }
            for r in weak_rows
        ],
        "recent_sessions": [
            {
                "id": r["id"],
                "mode": r["mode"],
                "started_at": r["started_at"],
                "ended_at": r["ended_at"],
                "answered_count": r["answered_count"] or 0,
                "correct_count": r["correct_count"] or 0,
                "accuracy": accuracy(r["correct_count"] or 0, r["answered_count"] or 0),
            }
            for r in session_rows
        ],
        "by_curriculum": [
            {
                "curriculum": r["curriculum"],
                "label": "新カリキュラム" if r["curriculum"] == "new" else "旧カリキュラム",
                "total": r["total"],
                "correct": r["correct"],
                "accuracy": accuracy(r["correct"], r["total"]),
            }
            for r in curriculum_rows
        ],
    }
