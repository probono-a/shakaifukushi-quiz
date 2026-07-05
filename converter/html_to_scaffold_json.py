#!/usr/bin/env python3
"""
html_to_scaffold_json.py
HTML + 正答PDF → 科目別スキャフォールド JSON

使い方:
  python converter/html_to_scaffold_json.py \
    --html    data/pdf/37th/listen_ss_am_37.html \
    --answers data/pdf/37th/s_kijun_seitou_37.pdf \
    --edition 37 \
    --out     tmp/37_am
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: beautifulsoup4 が必要です。  pip install beautifulsoup4")
    sys.exit(1)

try:
    from converter.parse_answers_pdf import parse_answers_pdf
    from converter.normalize_text import normalize_text, normalize_question_stem, normalize_option
except ImportError:
    from parse_answers_pdf import parse_answers_pdf
    from normalize_text import normalize_text, normalize_question_stem, normalize_option

def normalize_note_ul(ul_tag) -> str:
    items = []
    for i, li in enumerate(ul_tag.find_all('li')):
        t = li.get_text(' ', strip=True).replace('\xa0', ' ')
        t = t.replace('（注）', '(注)')
        t = re.sub(r'[ \t]+', ' ', t)
        if i > 0 and not t.startswith('(注)'):
            t = '(注) ' + t
        items.append(t.strip())
    return '\n'.join(items)


# ── HTML 解析 ──────────────────────────────────────────────────────────────────

def _dt_to_text(dt_tag) -> str:
    """<dt> の HTML を文字列化し <br> を改行に変換してテキスト取得"""
    html = str(dt_tag)
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    text = BeautifulSoup(html, 'html.parser').get_text(separator='')
    return re.sub(r'\n{2,}', '\n', text).strip()

def _attach_note(ul_tag, pending_q, questions):
    target = pending_q if pending_q else (questions[-1] if questions else None)
    if not target:
        return
    note = normalize_note_ul(ul_tag)
    if note:
        target['question_text'] += f'\n\n{note}'

def _make_question(dt_tag, subject, answers, edition, curriculum, questions, pending_q):
    """直前の問題を確定して新しい問題エントリを返す"""
    if pending_q is not None:
        questions.append(pending_q)

    raw = _dt_to_text(dt_tag)
    m = re.match(r'問題(\d+)', raw.replace('\xa0', ' '))
    qnum = int(m.group(1)) if m else 0

    if '〔事' in raw:
        question_type = '事例'
        parts = re.split(r'〔事[　\s]*例〕', raw)
        q_stem = normalize_question_stem(parts[0])
        case_text = normalize_text(parts[1].strip()) if len(parts) > 1 else ''
    else:
        question_type = '通常'
        q_stem = normalize_question_stem(raw)
        case_text = ''

    correct = answers.get(qnum, [])
    return {
        'id': f'{edition}_{qnum}',
        'edition': edition,
        'curriculum': curriculum,
        'subject': subject,
        'question_number': qnum,
        'question_type': question_type,
        'case_text': case_text,
        'question_text': q_stem,
        'is_multiple_answers': len(correct) > 1,
        'options': [],
        'correct_options': correct,
        'explanation': 'TODO: 解説未作成',
        'keywords': [],
        'reference_links': [],
        'image_paths': [],
        'is_reviewed': False,
    }

def _iter_tags(parent):
    for c in parent.children:
        if hasattr(c, 'name') and c.name:
            yield c


def _walk(parent, state: dict) -> None:
    """html.parser が任意の深さで吸収した <h2>/<dl>/<dt>/<dd>/<ul> を再帰的に処理する。"""
    for tag in _iter_tags(parent):
        if tag.name == 'h2':
            state['subject'] = tag.get_text(strip=True)
        elif tag.name == 'ul':
            _attach_note(tag, state['pending_q'], state['questions'])
        elif tag.name == 'dt':
            state['pending_q'] = _make_question(
                tag, state['subject'], state['answers'],
                state['edition'], state['curriculum'],
                state['questions'], state['pending_q'])
        elif tag.name == 'dd' and state['pending_q'] is not None:
            state['pending_q']['options'].append(
                normalize_option(tag.get_text(' ', strip=True)))
        elif tag.name == 'dl':
            _walk(tag, state)


def parse_html(html_path: str, answers: dict, edition: int) -> list:
    curriculum = 'new' if edition >= 37 else 'old'
    with open(html_path, encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    listen_div = soup.find('div', class_='listen_exam')
    if not listen_div:
        raise ValueError('div.listen_exam が見つかりません')

    state = {
        'questions': [],
        'pending_q': None,
        'subject': None,
        'answers': answers,
        'edition': edition,
        'curriculum': curriculum,
    }
    _walk(listen_div, state)

    if state['pending_q']:
        state['questions'].append(state['pending_q'])
    return state['questions']


# ── 出力 ───────────────────────────────────────────────────────────────────────

def write_subject_files(questions: list, subjects_order: list, out_dir: str) -> list:
    os.makedirs(out_dir, exist_ok=True)
    grouped = {}
    for q in questions:
        grouped.setdefault(q['subject'], []).append(q)

    written = []
    for idx, (subject, _) in enumerate(subjects_order, 1):
        group = grouped.get(subject)
        if not group:
            print(f'  WARNING: "{subject}" の問題が HTML に見つかりません')
            continue
        fname = f'{idx:02d}_{subject}.json'
        fpath = os.path.join(out_dir, fname)
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(group, f, ensure_ascii=False, indent=2)
        written.append(fpath)
        print(f'  {len(group):2d} 問 → {fpath}')
    return written


# ── エントリポイント ────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description='HTML + 正答PDF → 科目別スキャフォールド JSON')
    ap.add_argument('--html',    required=True)
    ap.add_argument('--answers', required=True)
    ap.add_argument('--edition', required=True, type=int)
    ap.add_argument('--out',     required=True)
    args = ap.parse_args()

    print(f'[1/3] 正答 PDF 解析: {args.answers}')
    subjects, answers = parse_answers_pdf(args.answers)
    print(f'      科目数: {len(subjects)}  問題数: {len(answers)}')

    print(f'[2/3] HTML 解析: {args.html}')
    questions = parse_html(args.html, answers, args.edition)
    print(f'      抽出問題数: {len(questions)}')

    html_qnums = {q['question_number'] for q in questions}
    missing = html_qnums - set(answers)
    if missing:
        print(f'  WARNING: 正答にない問番号: {sorted(missing)}')

    print(f'[3/3] 科目別 JSON 出力: {args.out}/')
    written = write_subject_files(questions, subjects, args.out)
    print(f'\n完了: {len(written)} ファイル → {args.out}/')
    print()
    print('=' * 60)
    print('以下を Claude Code に貼り付けてください:')
    print('=' * 60)
    print(f"""\
`prompts/pdf_to_json.md` の指示に従い、{args.out}/ 配下の科目別スキャフォールド JSON に explanation と keywords を追記してください。対象ディレクトリが不明な場合は、処理を開始する前に確認してください。""")

if __name__ == '__main__':
    main()
