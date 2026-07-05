import json
import sqlite3
import os
import glob

# プロジェクトルートを基準にパスを解決 (実行場所に依存しない)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "quiz.db")
JSON_DIR = os.path.join(PROJECT_ROOT, "data", "json", "checked")

def init_db():
    """データベースとテーブルの初期化"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 問題テーブル
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

    # セッションテーブル (1 回の学習セッションを管理)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id          TEXT PRIMARY KEY,
        started_at  DATETIME,
        ended_at    DATETIME,
        mode        TEXT,
        config      TEXT
    )
    """)

    # 学習履歴テーブル
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

    # 既存 DB への後方互換対応: カラムが存在しない場合のみ追加
    existing_columns = {row[1] for row in cursor.execute("PRAGMA table_info(history)")}
    if "session_id" not in existing_columns:
        cursor.execute("ALTER TABLE history ADD COLUMN session_id TEXT")
    if "edition" not in existing_columns:
        cursor.execute("ALTER TABLE history ADD COLUMN edition INTEGER")

    # 科目マッピングテーブル
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subject_mapping (
        subject_old   TEXT,
        subject_new   TEXT,
        subject_group INTEGER
    )
    """)

    # マッピングデータが空の場合のみ初期データを投入
    count = cursor.execute("SELECT COUNT(*) FROM subject_mapping").fetchone()[0]
    if count == 0:
        mappings = [
            ("人体の構造と機能及び疾病", "医学概論", 1),
            ("心理学理論と心理的支援", "心理学と心理的支援", 1),
            ("社会理論と社会システム", "社会学と社会システム", 1),
            ("現代社会と福祉", "社会福祉の原理と政策", 1),
            ("地域福祉の理論と方法", "地域福祉と包括的支援体制", 1),
            ("相談援助の基盤と専門職", "ソーシャルワークの基盤と専門職", 1),
            ("相談援助の理論と方法", "ソーシャルワークの理論と方法", 1),
            ("社会調査の基礎", "社会福祉調査の基礎", 1),
            ("高齢者に対する支援と介護保険制度", "高齢者福祉", 2),
            ("児童や家庭に対する支援と児童・家庭福祉制度", "児童・家庭福祉", 2),
            ("低所得者に対する支援と生活保護制度", "貧困に対する支援", 2),
            ("保健医療サービス", "保健医療と福祉", 2),
            ("権利擁護と成年後見制度", "権利擁護を支える法制度", 2)
        ]
        cursor.executemany(
            "INSERT INTO subject_mapping (subject_old, subject_new, subject_group) VALUES (?, ?, ?)",
            mappings
        )
        print("Initialized subject_mapping table with master data.")

    conn.commit()
    return conn

def get_curriculum(edition):
    """回数からカリキュラム区分を判定"""
    # 第 37 回（2025 年 2 月）から新カリキュラム
    if edition >= 37:
        return "new"
    else:
        return "old"

def import_json_files(conn):
    """JSON ファイルを走査して DB にインポート"""
    cursor = conn.cursor()

    # 全ての JSON ファイルを取得 (サブディレクトリ含む)
    json_files = glob.glob(os.path.join(JSON_DIR, "**/*.json"), recursive=True)
    
    total_imported = 0
    total_skipped = 0

    for file_path in json_files:
        print(f"Processing: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON {file_path}: {e}")
                continue

            for item in data:
                # 人間による確認が完了しているものだけを対象とする
                if not item.get("is_reviewed", False):
                    total_skipped += 1
                    continue

                # カリキュラム判定
                curriculum = get_curriculum(item.get("edition"))

                # SQLite に挿入するための値の準備 (リストやフラグの変換)
                cursor.execute("""
                INSERT OR REPLACE INTO questions (
                    id, edition, subject, question_number, question_type,
                    case_text, question_text, is_multiple, options,
                    correct_options, explanation, keywords, reference_links,
                    image_paths, curriculum
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.get("id"),
                    item.get("edition"),
                    item.get("subject"),
                    item.get("question_number"),
                    item.get("question_type"),
                    item.get("case_text"),
                    item.get("question_text"),
                    1 if item.get("is_multiple_answers") else 0,
                    json.dumps(item.get("options", []), ensure_ascii=False),
                    json.dumps(item.get("correct_options", []), ensure_ascii=False),
                    item.get("explanation"),
                    json.dumps(item.get("keywords", []), ensure_ascii=False),
                    json.dumps(item.get("reference_links", []), ensure_ascii=False),
                    json.dumps(item.get("image_paths", []), ensure_ascii=False),
                    curriculum
                ))
                total_imported += 1

    conn.commit()
    print(f"\nImport Summary:")
    print(f"- Total imported: {total_imported}")
    print(f"- Total skipped (not reviewed): {total_skipped}")

if __name__ == "__main__":
    connection = init_db()
    try:
        import_json_files(connection)
    finally:
        connection.close()
