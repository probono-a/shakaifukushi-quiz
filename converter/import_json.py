import json
import shutil
import os
import glob
import sys

# プロジェクトルートを基準にパスを解決 (実行場所に依存しない)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from db import open_initialized_db  # noqa: E402

JSON_DIR = os.path.join(PROJECT_ROOT, "data", "json", "checked")
IMPORTED_DIR = os.path.join(PROJECT_ROOT, "data", "json", "imported_to_db")

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
    moved_files = []
    pending_files = []

    for file_path in json_files:
        print(f"Processing: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON {file_path}: {e}")
                continue

        # ファイルハンドルを閉じた後に処理する (Windows では開いたままだとリネーム/移動できない)
        file_skipped = 0

        for item in data:
            # 人間による確認が完了しているものだけを対象とする
            if not item.get("is_reviewed", False):
                total_skipped += 1
                file_skipped += 1
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

        # ファイル内の全レコードがインポート済み (未レビュー混在なし) の場合のみ移動対象にする
        if file_skipped == 0:
            os.makedirs(IMPORTED_DIR, exist_ok=True)
            dest_path = os.path.join(IMPORTED_DIR, os.path.basename(file_path))
            shutil.move(file_path, dest_path)
            moved_files.append(os.path.basename(file_path))
        else:
            pending_files.append(os.path.basename(file_path))

    conn.commit()
    print(f"\nImport Summary:")
    print(f"- Total imported: {total_imported}")
    print(f"- Total skipped (not reviewed): {total_skipped}")
    print(f"- Files moved to imported_to_db/: {len(moved_files)}")
    for name in moved_files:
        print(f"    {name}")
    if pending_files:
        print(f"- Files kept in checked/ (contain unreviewed records): {len(pending_files)}")
        for name in pending_files:
            print(f"    {name}")

if __name__ == "__main__":
    connection = open_initialized_db()
    try:
        import_json_files(connection)
    finally:
        connection.close()
