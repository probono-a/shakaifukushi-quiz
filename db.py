import sqlite3
import os
from contextlib import contextmanager

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data", "quiz.db")

SUBJECT_MAPPINGS = [
    ("人体の構造と機能及び疾病", "医学概論", 1),
    ("心理学理論と心理的支援", "心理学と心理的支援", 1),
    ("社会理論と社会システム", "社会学と社会システム", 1),
    ("現代社会と福祉", "社会福祉の原理と政策", 1),
    ("地域福祉の理論と方法", "地域福祉と包括的支援体制", 1),
    ("福祉行財政と福祉計画", "地域福祉と包括的支援体制", 1),
    ("相談援助の基盤と専門職", "ソーシャルワークの基盤と専門職", 1),
    ("相談援助の理論と方法", "ソーシャルワークの理論と方法", 1),
    ("社会調査の基礎", "社会福祉調査の基礎", 1),
    ("高齢者に対する支援と介護保険制度", "高齢者福祉", 2),
    ("障害者に対する支援と障害者自立支援制度", "障害者福祉", 2),
    ("児童や家庭に対する支援と児童・家庭福祉制度", "児童・家庭福祉", 2),
    ("低所得者に対する支援と生活保護制度", "貧困に対する支援", 2),
    ("保健医療サービス", "保健医療と福祉", 2),
    ("権利擁護と成年後見制度", "権利擁護を支える法制度", 2),
    ("更生保護制度", "刑事司法と福祉", 2),
]


def get_db_path() -> str:
    """使う DB の絶対パスを返す。環境変数 QUIZ_DB_PATH があればそれを使う。

    環境変数を読むのはここだけ。呼ばれるたびに読むので、あとから変えても効く。
    相対パスは、実行したフォルダではなくプロジェクトのルートを基準にする。
    """
    path = os.environ.get("QUIZ_DB_PATH", "")
    if not path:
        return DEFAULT_DB_PATH
    if not os.path.isabs(path):
        path = os.path.join(PROJECT_ROOT, path)
    return os.path.normpath(path)


@contextmanager
def get_db():
    """SQLite 接続をコンテキストマネージャーとして提供する"""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row  # カラム名でアクセスできるようにする
    try:
        yield conn
    finally:
        conn.close()


def init_db(conn: sqlite3.Connection) -> None:
    """必要なテーブルが揃っていることを保証する (テーブル作成・移行・初期データ)。

    最後に自分で commit してから戻る。
    """
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
        curriculum       TEXT,
        is_reviewed      INTEGER NOT NULL DEFAULT 0,
        needs_check      INTEGER NOT NULL DEFAULT 0,
        check_note       TEXT
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

    # 既存 DB への後方互換マイグレーション: カラムが存在しない場合のみ追加
    existing = {r[1] for r in cursor.execute("PRAGMA table_info(history)")}
    if "session_id" not in existing:
        cursor.execute("ALTER TABLE history ADD COLUMN session_id TEXT")
    if "edition" not in existing:
        cursor.execute("ALTER TABLE history ADD COLUMN edition INTEGER")
    if "time_sec" not in existing:
        cursor.execute("ALTER TABLE history ADD COLUMN time_sec REAL")

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
        cursor.executemany(
            "INSERT INTO subject_mapping (subject_old, subject_new, subject_group) VALUES (?, ?, ?)",
            SUBJECT_MAPPINGS,
        )

    conn.commit()

    _migrate_questions_is_reviewed(conn)
    _migrate_questions_needs_check(conn)


def _migrate_questions_is_reviewed(conn: sqlite3.Connection) -> None:
    """questions に is_reviewed 列がなければ足し、既存の問題をすべて確認済み (1) にする。

    これまで DB に入っていた問題は、すべて人が確認したうえで入れたもの。
    列の追加と UPDATE は 1 つのトランザクションで行う。分けると、UPDATE の前に落ちたとき
    列だけが残り、次の起動では「列がある」と判断されて UPDATE が二度と走らない。
    """
    columns = {r[1] for r in conn.execute("PRAGMA table_info(questions)")}
    if "is_reviewed" in columns:
        return
    # Python の sqlite3 は DDL を自動では BEGIN で囲まないので、明示する
    conn.execute("BEGIN")
    try:
        conn.execute("ALTER TABLE questions ADD COLUMN is_reviewed INTEGER NOT NULL DEFAULT 0")
        conn.execute("UPDATE questions SET is_reviewed = 1")
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def _migrate_questions_needs_check(conn: sqlite3.Connection) -> None:
    """questions に要確認の印 (needs_check) と理由 (check_note) の列がなければ足す。

    既存の問題は印なし・理由なしでよいので、値は書き換えない。
    ALTER はその場で確定するので、列ごとに確かめれば、途中で落ちても次の起動で残りが足される。
    """
    columns = {r[1] for r in conn.execute("PRAGMA table_info(questions)")}
    if "needs_check" not in columns:
        conn.execute("ALTER TABLE questions ADD COLUMN needs_check INTEGER NOT NULL DEFAULT 0")
    if "check_note" not in columns:
        conn.execute("ALTER TABLE questions ADD COLUMN check_note TEXT")
    conn.commit()


def open_initialized_db() -> sqlite3.Connection:
    """DB の親フォルダを作り、接続して init_db() を呼んで返す。"""
    path = get_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print(f"DB: {path}")
    conn = sqlite3.connect(path)
    init_db(conn)
    return conn
