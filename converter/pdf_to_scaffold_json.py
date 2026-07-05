#!/usr/bin/env python3
"""
pdf_to_scaffold_json.py
問題 PDF (画像) + 正答 PDF → PNG レンダリング + 科目別スキャフォールド JSON

使い方:
  python converter/pdf_to_scaffold_json.py \
    --source-dir data/pdf/34th \
    --edition    34

  正答 PDF は --source-dir 内で "seitou" を含むファイルを自動検出します。
  問題 PDF はそれ以外の PDF をアルファベット順に連結してレンダリングします。
  --out / --png-dir を省略すると tmp/{edition}th / scratch/{edition}th が使われます。
"""

import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

try:
    import fitz
except ImportError:
    print("ERROR: PyMuPDF が必要です。  pip install pymupdf")
    sys.exit(1)

try:
    from converter.parse_answers_pdf import parse_answers_pdf
except ImportError:
    from parse_answers_pdf import parse_answers_pdf


# ── PDF 自動検出 ───────────────────────────────────────────────────────────────

def detect_pdfs(source_dir: str):
    """source_dir 内の PDF を正答 / 問題に分類して返す。"""
    pdfs = sorted(
        f for f in os.listdir(source_dir) if f.lower().endswith('.pdf')
    )
    answers_pdf = None
    question_pdfs = []
    for f in pdfs:
        if 'seitou' in f.lower() or 'answer' in f.lower():
            answers_pdf = os.path.join(source_dir, f)
        else:
            question_pdfs.append(os.path.join(source_dir, f))

    if answers_pdf is None:
        print('ERROR: 正答 PDF が見つかりません (ファイル名に "seitou" または "answer" が必要)。')
        print(f'       確認したディレクトリ: {source_dir}')
        print(f'       見つかった PDF: {pdfs}')
        sys.exit(1)
    if not question_pdfs:
        print('ERROR: 問題 PDF が見つかりません。')
        sys.exit(1)

    return question_pdfs, answers_pdf


# ── PDF レンダリング ────────────────────────────────────────────────────────────

def render_pages(pdf_paths: list, png_dir: str, scale: float = 2.0) -> list:
    """複数の PDF を連番で PNG 化する。"""
    os.makedirs(png_dir, exist_ok=True)
    mat = fitz.Matrix(scale, scale)
    paths = []
    page_num = 1
    for pdf_path in pdf_paths:
        doc = fitz.open(pdf_path)
        for page in doc:
            out = os.path.join(png_dir, f'p{page_num:02d}.png')
            page.get_pixmap(matrix=mat).save(out)
            paths.append(out)
            page_num += 1
        page_count = doc.page_count
        doc.close()
        print(f'  {os.path.basename(pdf_path)}: {page_count} ページ')
    print(f'  合計 {len(paths)} ページ → {png_dir}/')
    return paths


# ── スキャフォールド生成 ────────────────────────────────────────────────────────

def make_scaffold(subjects: list, answers: dict, edition: int) -> list:
    """正答情報だけでスキャフォールドを生成。テキストは TODO プレースホルダー。"""
    curriculum = 'new' if edition >= 37 else 'old'
    questions = []
    for subject, q_nums in subjects:
        for qn in q_nums:
            correct = answers.get(qn, [])
            questions.append({
                'id': f'{edition}_{qn}',
                'edition': edition,
                'curriculum': curriculum,
                'subject': subject,
                'question_number': qn,
                'question_type': '通常',
                'case_text': '',
                'question_text': 'TODO: 未入力',
                'is_multiple_answers': len(correct) > 1,
                'options': ['TODO: 未入力'] * 5,
                'correct_options': correct,
                'explanation': 'TODO: 解説未作成',
                'keywords': [],
                'reference_links': [],
                'image_paths': [],
                'is_reviewed': False,
            })
    return questions


# ── 出力 ───────────────────────────────────────────────────────────────────────

def write_subject_files(questions: list, subjects: list, out_dir: str) -> list:
    os.makedirs(out_dir, exist_ok=True)
    grouped = {}
    for q in questions:
        grouped.setdefault(q['subject'], []).append(q)

    written = []
    for idx, (subject, _) in enumerate(subjects, 1):
        group = grouped.get(subject)
        if not group:
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
    ap = argparse.ArgumentParser(
        description='問題 PDF (画像) + 正答 PDF → PNG + 科目別スキャフォールド JSON')
    ap.add_argument('--source-dir', required=True,
                    help='問題 PDF と正答 PDF が入ったディレクトリ')
    ap.add_argument('--edition', required=True, type=int, help='試験回次')
    ap.add_argument('--out',     help='JSON 出力ディレクトリ (デフォルト: tmp/{edition}th)')
    ap.add_argument('--png-dir', help='PNG 出力先 (デフォルト: scratch/{edition}th)')
    ap.add_argument('--scale',   type=float, default=2.0,
                    help='PNG 解像度倍率 (デフォルト: 2.0 = 144DPI / 節約時は 1.5 推奨)')
    args = ap.parse_args()

    out_dir = args.out     or f'tmp/{args.edition}th'
    png_dir = args.png_dir or f'scratch/{args.edition}th'

    print(f'[1/3] PDF 検出: {args.source_dir}/')
    question_pdfs, answers_pdf = detect_pdfs(args.source_dir)
    print(f'      問題 PDF: {[os.path.basename(p) for p in question_pdfs]}')
    print(f'      正答 PDF: {os.path.basename(answers_pdf)}')

    print(f'[2/3] 正答 PDF 解析: {answers_pdf}')
    subjects, answers = parse_answers_pdf(answers_pdf)
    print(f'      科目数: {len(subjects)}  問題数: {len(answers)}')

    print(f'[3/3] PDF レンダリング → {png_dir}/ (scale={args.scale})')
    render_pages(question_pdfs, png_dir, scale=args.scale)

    print(f'[4/4] スキャフォールド JSON 出力: {out_dir}/')
    questions = make_scaffold(subjects, answers, args.edition)
    written = write_subject_files(questions, subjects, out_dir)

    print(f'\n完了: {len(written)} ファイル → {out_dir}/')
    print()
    print('=' * 60)
    print('以下を Claude Code に貼り付けてください:')
    print('=' * 60)
    print(f"""\
`prompts/pdf_to_json.md` の指示に従い、以下のパスの PNG を視覚で読み取りながら、\
科目別スキャフォールド JSON に question_text・options・case_text・question_type・\
explanation・keywords をすべて追記してください。

  PNG ディレクトリ : {png_dir}/
  JSON ディレクトリ: {out_dir}/

対象ディレクトリが不明な場合は、処理を開始する前に確認してください。""")

if __name__ == '__main__':
    main()
