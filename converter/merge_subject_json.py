#!/usr/bin/env python3
"""
merge_subject_json.py
科目別 JSON → 最終 JSON (問番号順ソート)

使い方:
  python converter/merge_subject_json.py \
    --dir tmp/37_am \
    --out data/json/37th/listen_ss_am_37.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')


def merge(dir_path: str, out_path: str):
    files = sorted(Path(dir_path).glob('*.json'))
    if not files:
        print(f'ERROR: {dir_path}/ に JSON ファイルが見つかりません')
        sys.exit(1)

    all_questions = []
    for fpath in files:
        with open(fpath, encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
            print(f'WARNING: {fpath.name} は list でないためスキップ')
            continue
        all_questions.extend(data)
        print(f'  {len(data):2d} 問 ← {fpath.name}')

    all_questions.sort(key=lambda q: q.get('question_number', 0))

    todo_q = [q['id'] for q in all_questions if 'TODO' in q.get('question_text', '')]
    todo_e = [q['id'] for q in all_questions if 'TODO' in q.get('explanation', '')]
    if todo_q:
        print(f'  WARNING: question_text に TODO が残っている問題: {todo_q}')
    if todo_e:
        print(f'  WARNING: explanation に TODO が残っている問題数: {len(todo_e)}')

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=2)

    print(f'\n完了: {len(all_questions)} 問 → {out_path}')


def main():
    ap = argparse.ArgumentParser(description='科目別 JSON → 最終 JSON')
    ap.add_argument('--dir', required=True, help='科目別 JSON が入ったディレクトリ')
    ap.add_argument('--out', required=True, help='出力先 JSON ファイルパス')
    args = ap.parse_args()
    merge(args.dir, args.out)

if __name__ == '__main__':
    main()
