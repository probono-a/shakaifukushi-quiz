from fastapi import APIRouter

from db import get_db

router = APIRouter(prefix="/api", tags=["recommend"])

# おすすめを出すのに必要な最低解答数
RECOMMEND_MIN_ANSWERS = 10
# おすすめセッションの問題数
RECOMMEND_COUNT = 20


@router.get("/recommend")
def get_recommendation():
    """
    解答履歴をもとにルールベースで「今日のおすすめセッション」を返す。

    ロジック:
        1. 科目別正答率が低い順に並べる
        2. 同率の場合は最後に学習した日が古い科目を優先する
        3. 上位 3 科目を対象にした「ランダム N 問」セッション設定を返す
    """
    with get_db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM history"
        ).fetchone()["cnt"]

        if total < RECOMMEND_MIN_ANSWERS:
            return {
                "available": False,
                "reason": f"おすすめを生成するには {RECOMMEND_MIN_ANSWERS} 問以上の解答履歴が必要です（現在 {total} 問）",
            }

        rows = conn.execute(
            """SELECT COALESCE(sm.subject_new, h.subject) AS subject,
                      COUNT(*) as total,
                      SUM(is_correct) as correct,
                      ROUND(SUM(is_correct) * 100.0 / COUNT(*), 1) as accuracy,
                      MAX(answered_at) as last_studied
               FROM history h
               LEFT JOIN subject_mapping sm ON h.subject = sm.subject_old
               GROUP BY COALESCE(sm.subject_new, h.subject)
               ORDER BY accuracy ASC, last_studied ASC
               LIMIT 3"""
        ).fetchall()

    subjects = [r["subject"] for r in rows]
    subject_stats = [
        {
            "subject": r["subject"],
            "accuracy": r["accuracy"],
            "last_studied": r["last_studied"],
        }
        for r in rows
    ]

    return {
        "available": True,
        "subjects": subjects,
        "subject_stats": subject_stats,
        "suggested_session": {
            "mode": "random",
            "config": {
                "subjects": subjects,
                "count": RECOMMEND_COUNT,
            },
        },
    }
