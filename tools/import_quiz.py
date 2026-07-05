import sqlite3
import json
import argparse
import os
from pathlib import Path

import sys

# Reconfigure stdout for Windows console
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def import_quiz(json_path, db_path):
    if not os.path.exists(json_path):
        print(f"Error: JSON file not found at {json_path}")
        return
    
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # We'll use 'INSERT OR REPLACE' to allow updates
    query = """
    INSERT OR REPLACE INTO questions (
        id, edition, subject, question_number, question_type, 
        case_text, question_text, is_multiple, options, 
        correct_options, explanation, keywords, reference_links, 
        image_paths, curriculum
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    count = 0
    for q in data:
        # Map JSON keys to DB columns
        # Note: list/dict fields must be stringified
        params = (
            q["id"],
            q["edition"],
            q["subject"],
            q["question_number"],
            q["question_type"],
            q["case_text"],
            q["question_text"],
            1 if q.get("is_multiple_answers", False) else 0,
            json.dumps(q["options"], ensure_ascii=False),
            json.dumps(q["correct_options"], ensure_ascii=False),
            q.get("explanation", ""),
            json.dumps(q.get("keywords", []), ensure_ascii=False),
            json.dumps(q.get("reference_links", []), ensure_ascii=False),
            json.dumps(q.get("image_paths", []), ensure_ascii=False),
            "new" if q["edition"] >= 37 else "old" # Curriculum heuristic
        )
        cursor.execute(query, params)
        count += 1
    
    conn.commit()
    conn.close()
    print(f"Successfully imported {count} questions into {db_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("json_path", type=str, help="Path to the validated quiz JSON")
    parser.add_argument("--db", type=str, default="data/quiz.db", help="Path to the SQLite database")
    args = parser.parse_args()
    
    import_quiz(args.json_path, args.db)
