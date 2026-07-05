import json
import random
from typing import List, Optional

from fastapi import APIRouter, Query, Body, HTTPException


from db import get_db

router = APIRouter(prefix="/api", tags=["questions"])


def _parse_question(row) -> dict:
    """DB の Row を JSON フィールドをデコードした dict に変換する"""
    q = dict(row)
    for field in ("options", "correct_options", "keywords", "reference_links", "image_paths"):
        raw = q.get(field) or "[]"
        q[field] = json.loads(raw)
    return q


@router.get("/editions")
def get_editions():
    """DB に登録されているエディション（回）の一覧を返す"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT edition FROM questions WHERE edition IS NOT NULL ORDER BY edition DESC"
        ).fetchall()
    return [r["edition"] for r in rows]


@router.get("/subjects")
def get_subjects():
    """DB に登録されている科目の一覧を返す（新カリ名に統一）"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT DISTINCT COALESCE(sm.subject_new, q.subject) AS subject
            FROM questions q
            LEFT JOIN subject_mapping sm ON q.subject = sm.subject_old
            ORDER BY subject
        """).fetchall()
    return [r["subject"] for r in rows]


@router.get("/subjects/old")
def get_old_subjects():
    """旧カリキュラムの生の科目名一覧を返す（editor.html の科目プルダウン用）"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT subject_old FROM subject_mapping ORDER BY subject_old"
        ).fetchall()
    return [r["subject_old"] for r in rows]


WEAK_MIN_ATTEMPTS = 3


@router.get("/questions")
def get_questions(
    mode: str = "subject",
    subjects: List[str] = Query(default=[]),
    ids: List[str] = Query(default=[]),
    edition: Optional[int] = None,
    count: Optional[int] = None,
    curriculum: Optional[str] = None,
    question_type: Optional[str] = None,
    multiple_only: bool = False,
):
    """
    セッションモードに応じた問題一覧を返す。

    mode:
        subject    … 指定した科目の問題
        wrong_only … 過去に 1 度でも不正解だった問題
        random     … 条件に合う問題をシャッフルして count 件
        edition    … 指定した回の全問
        weak       … 苦手問題（3 回以上解答・正答率 100% 未満）を正答率昇順
    ids:
        指定した ID の問題のみを返す（モード問わず優先）
    """
    with get_db() as conn:
        if ids:
            placeholders = ",".join("?" * len(ids))
            rows = conn.execute(
                f"""SELECT q.*,
                           COALESCE(
                               (SELECT subject_new FROM subject_mapping
                                WHERE subject_old = q.subject LIMIT 1),
                               q.subject
                           ) AS subject_display
                    FROM questions q
                    WHERE q.id IN ({placeholders})""",
                ids,
            ).fetchall()
            return [_parse_question(r) for r in rows]

        if mode == "weak":
            rows = conn.execute(
                f"""SELECT q.*,
                           COALESCE(
                               (SELECT subject_new FROM subject_mapping
                                WHERE subject_old = q.subject LIMIT 1),
                               q.subject
                           ) AS subject_display
                    FROM (
                        SELECT question_id
                        FROM history
                        GROUP BY question_id
                        HAVING COUNT(*) >= {WEAK_MIN_ATTEMPTS}
                           AND ROUND(SUM(is_correct) * 100.0 / COUNT(*), 1) < 100
                        ORDER BY ROUND(SUM(is_correct) * 100.0 / COUNT(*), 1) ASC
                    ) weak
                    JOIN questions q ON q.id = weak.question_id""",
            ).fetchall()
            return [_parse_question(r) for r in rows]

        if mode == "rare":
            conditions: List[str] = []
            params: List = []

            if subjects:
                expanded = list(subjects)
                for subj in subjects:
                    old_rows = conn.execute(
                        "SELECT subject_old FROM subject_mapping WHERE subject_new = ?",
                        (subj,),
                    ).fetchall()
                    expanded.extend(r["subject_old"] for r in old_rows)
                placeholders = ",".join("?" * len(expanded))
                conditions.append(f"q.subject IN ({placeholders})")
                params.extend(expanded)

            if curriculum:
                conditions.append("q.curriculum = ?")
                params.append(curriculum)

            if question_type:
                conditions.append("q.question_type = ?")
                params.append(question_type)

            if multiple_only:
                conditions.append("q.is_multiple = 1")

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            limit_clause = f"LIMIT {count}" if count else ""

            rows = conn.execute(
                f"""SELECT q.*,
                           COALESCE(
                               (SELECT subject_new FROM subject_mapping
                                WHERE subject_old = q.subject LIMIT 1),
                               q.subject
                           ) AS subject_display
                    FROM questions q
                    LEFT JOIN (
                        SELECT question_id, COUNT(*) AS cnt
                        FROM history
                        GROUP BY question_id
                    ) h ON q.id = h.question_id
                    {where}
                    ORDER BY COALESCE(h.cnt, 0) ASC, RANDOM()
                    {limit_clause}""",
                params,
            ).fetchall()
            return [_parse_question(r) for r in rows]

        if mode == "wrong_only":
            wrong_rows = conn.execute(
                "SELECT DISTINCT question_id FROM history WHERE is_correct = 0"
            ).fetchall()
            wrong_ids = [r["question_id"] for r in wrong_rows]
            if not wrong_ids:
                return []
            placeholders = ",".join("?" * len(wrong_ids))
            extra_conds: List[str] = []
            extra_params: List = []
            if question_type:
                extra_conds.append("q.question_type = ?")
                extra_params.append(question_type)
            if multiple_only:
                extra_conds.append("q.is_multiple = 1")
            extra_where = (" AND " + " AND ".join(extra_conds)) if extra_conds else ""
            rows = conn.execute(
                f"""SELECT q.*,
                           COALESCE(
                               (SELECT subject_new FROM subject_mapping
                                WHERE subject_old = q.subject LIMIT 1),
                               q.subject
                           ) AS subject_display
                    FROM questions q
                    WHERE q.id IN ({placeholders}){extra_where}""",
                wrong_ids + extra_params,
            ).fetchall()
        else:
            conditions: List[str] = []
            params: List = []

            if subjects:
                # 新カリ名で指定された科目を旧カリ名にも展開する
                expanded = list(subjects)
                for subj in subjects:
                    old_rows = conn.execute(
                        "SELECT subject_old FROM subject_mapping WHERE subject_new = ?",
                        (subj,),
                    ).fetchall()
                    expanded.extend(r["subject_old"] for r in old_rows)
                placeholders = ",".join("?" * len(expanded))
                conditions.append(f"subject IN ({placeholders})")
                params.extend(expanded)

            if edition is not None:
                conditions.append("edition = ?")
                params.append(edition)

            if curriculum:
                conditions.append("curriculum = ?")
                params.append(curriculum)

            if question_type:
                conditions.append("q.question_type = ?")
                params.append(question_type)

            if multiple_only:
                conditions.append("q.is_multiple = 1")

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            rows = conn.execute(
                f"""SELECT q.*,
                           COALESCE(
                               (SELECT subject_new FROM subject_mapping
                                WHERE subject_old = q.subject LIMIT 1),
                               q.subject
                           ) AS subject_display
                    FROM questions q
                    {where} ORDER BY q.edition, q.question_number""",
                params,
            ).fetchall()

    questions = [_parse_question(r) for r in rows]

    if mode == "random" and count:
        random.shuffle(questions)
        questions = questions[:count]

    return questions


@router.get("/questions/{question_id}")
def get_question(question_id: str):
    with get_db() as conn:
        row = conn.execute(
            """SELECT q.*,
                      COALESCE(
                          (SELECT subject_new FROM subject_mapping
                           WHERE subject_old = q.subject LIMIT 1),
                          q.subject
                      ) AS subject_display
               FROM questions q WHERE q.id = ?""",
            (question_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return _parse_question(row)


@router.post("/questions")
def create_question(body: dict = Body(...)):
    edition = body.get("edition")
    question_number = body.get("question_number")
    if not edition or not question_number:
        raise HTTPException(status_code=422, detail="edition と question_number は必須です")

    question_id = f"{edition}_{question_number}"
    correct_options = body.get("correct_options", [])

    with get_db() as conn:
        exists = conn.execute("SELECT id FROM questions WHERE id = ?", (question_id,)).fetchone()
        if exists:
            raise HTTPException(status_code=422, detail=f"ID '{question_id}' は既に登録されています")

        conn.execute("""
            INSERT INTO questions (
                id, edition, subject, question_number, question_type, case_text, question_text,
                is_multiple, options, correct_options, explanation, keywords, reference_links, curriculum
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            question_id,
            edition,
            body.get("subject"),
            question_number,
            body.get("question_type"),
            body.get("case_text"),
            body.get("question_text"),
            1 if len(correct_options) > 1 else 0,
            json.dumps(body.get("options", []), ensure_ascii=False),
            json.dumps(correct_options, ensure_ascii=False),
            body.get("explanation"),
            json.dumps(body.get("keywords", []), ensure_ascii=False),
            json.dumps(body.get("reference_links", []), ensure_ascii=False),
            body.get("curriculum"),
        ))
        conn.commit()
    return {"ok": True, "id": question_id}


@router.put("/questions/{question_id}")
def update_question(question_id: str, body: dict = Body(...)):
    with get_db() as conn:
        row = conn.execute("SELECT id FROM questions WHERE id = ?", (question_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Question not found")
        correct_options = body.get("correct_options", [])
        conn.execute("""
            UPDATE questions SET
                subject = ?, question_type = ?, case_text = ?, question_text = ?,
                is_multiple = ?, options = ?, correct_options = ?,
                explanation = ?, keywords = ?, reference_links = ?, curriculum = ?
            WHERE id = ?
        """, (
            body.get("subject"),
            body.get("question_type"),
            body.get("case_text"),
            body.get("question_text"),
            1 if len(correct_options) > 1 else 0,
            json.dumps(body.get("options", []), ensure_ascii=False),
            json.dumps(correct_options, ensure_ascii=False),
            body.get("explanation"),
            json.dumps(body.get("keywords", []), ensure_ascii=False),
            json.dumps(body.get("reference_links", []), ensure_ascii=False),
            body.get("curriculum"),
            question_id,
        ))
        conn.commit()
    return {"ok": True}
