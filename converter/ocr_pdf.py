#!/usr/bin/env python3
"""
ocr_pdf.py
問題 PDF (スキャン画像) を tools/ndlocr-lite で OCR し、PDF と同じディレクトリに
テキストファイル ({PDF名}.ocr.txt) を出力する。

事前準備 (初回のみ):
  cd tools/ndlocr-lite
  python -m venv .venv
  .venv/Scripts/python.exe -m pip install -r requirements.txt

使い方:
  # 特定のディレクトリ内の PDF をすべて処理
  .venv\\Scripts\\python.exe converter/ocr_pdf.py --source-dir data/pdf/34th

  # 特定の PDF 一つだけ処理
  .venv\\Scripts\\python.exe converter/ocr_pdf.py --pdf data/pdf/34th/34th_specialized.pdf

  # data/pdf/ 以下の全 PDF を対象
  .venv\\Scripts\\python.exe converter/ocr_pdf.py --all

出力形式:
  - 問題 PDF (スキャン画像): {PDF名}.ocr.txt を作成する。ページ区切りは
    "=== p001 ===" のようなマーカーで示す。OCR の精度は完全ではない。
    事実精査の裏取り用途では、OCR結果が「らしい」箇所を見つけた後、
    必要に応じて該当ページを PyMuPDF で画像化し目視で最終確認すること。
  - 正答 PDF (ファイル名に "answer" または "seitou" を含むもの): 既にテキスト層を
    持っており OCR は不要などころか、表レイアウトが画像化・OCR で崩れてかえって
    読みにくくなる (実際に確認済み)。そのため `parse_answers_pdf.py` で直接テキスト
    抽出し、{PDF名}.md に科目ごとの正答一覧を Markdown 表として出力する (OCR は行わない)。
  いずれも既に出力ファイルが存在する PDF はデフォルトでスキップする (--force で再実行)。
"""

import argparse
import glob
import os
import subprocess
import sys
import tempfile

try:
    import fitz
except ImportError:
    print("ERROR: PyMuPDF が必要です。  pip install pymupdf")
    sys.exit(1)

try:
    from converter.parse_answers_pdf import parse_answers_pdf
except ImportError:
    from parse_answers_pdf import parse_answers_pdf

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NDLOCR_DIR = os.path.join(REPO_ROOT, "tools", "ndlocr-lite")
NDLOCR_PY = os.path.join(NDLOCR_DIR, ".venv", "Scripts", "python.exe")
NDLOCR_SRC = os.path.join(NDLOCR_DIR, "src")


def is_answer_pdf(path: str) -> bool:
    name = os.path.basename(path).lower()
    return "answer" in name or "seitou" in name


def render_pdf_to_pngs(pdf_path: str, out_dir: str, dpi: int = 150) -> list:
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    paths = []
    for i, page in enumerate(doc, 1):
        out = os.path.join(out_dir, f"p{i:03d}.png")
        page.get_pixmap(dpi=dpi).save(out)
        paths.append(out)
    doc.close()
    return paths


def run_ocr(png_dir: str, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    subprocess.run(
        [NDLOCR_PY, "ocr.py", "--sourcedir", png_dir, "--output", out_dir, "--json-only"],
        cwd=NDLOCR_SRC,
        check=True,
        stdout=subprocess.DEVNULL,
    )


def combine_txt(png_paths: list, ocr_out_dir: str, dest_txt: str) -> None:
    import json as jsonlib

    with open(dest_txt, "w", encoding="utf-8") as out:
        for p in png_paths:
            stem = os.path.splitext(os.path.basename(p))[0]
            out.write(f"\n=== {stem} ===\n")
            json_path = os.path.join(ocr_out_dir, stem + ".json")
            if os.path.exists(json_path):
                with open(json_path, encoding="utf-8") as f:
                    data = jsonlib.load(f)
                for block in data.get("contents", []):
                    for line in block:
                        out.write(line.get("text", "") + "\n")


def write_answer_markdown(pdf_path: str, dest_md: str) -> int:
    subjects, answers = parse_answers_pdf(pdf_path)
    with open(dest_md, "w", encoding="utf-8") as f:
        f.write(f"# {os.path.basename(pdf_path)} 正答一覧\n\n")
        for name, q_nums in subjects:
            f.write(f"## {name}\n\n")
            f.write("| 問題番号 | 正答 |\n|---|---|\n")
            for qn in q_nums:
                choices = answers.get(qn, [])
                f.write(f"| {qn} | {','.join(str(c) for c in choices)} |\n")
            f.write("\n")
    return len(answers)


def process_answer_pdf(pdf_path: str, force: bool) -> None:
    dest_md = os.path.splitext(pdf_path)[0] + ".md"
    if os.path.exists(dest_md) and not force:
        print(f"  skip (既存): {dest_md}")
        return
    print(f"[正答抽出] {pdf_path}")
    n = write_answer_markdown(pdf_path, dest_md)
    print(f"  -> {dest_md} ({n} 問)")


def process_question_pdf(pdf_path: str, force: bool, dpi: int) -> None:
    dest_txt = os.path.splitext(pdf_path)[0] + ".ocr.txt"
    if os.path.exists(dest_txt) and not force:
        print(f"  skip (既存): {dest_txt}")
        return
    print(f"[OCR] {pdf_path}")
    with tempfile.TemporaryDirectory() as tmp:
        png_dir = os.path.join(tmp, "png")
        ocr_dir = os.path.join(tmp, "ocr")
        png_paths = render_pdf_to_pngs(pdf_path, png_dir, dpi=dpi)
        run_ocr(png_dir, ocr_dir)
        combine_txt(png_paths, ocr_dir, dest_txt)
    print(f"  -> {dest_txt} ({len(png_paths)} ページ)")


def process_pdf(pdf_path: str, force: bool, dpi: int) -> None:
    if is_answer_pdf(pdf_path):
        process_answer_pdf(pdf_path, force=force)
    else:
        process_question_pdf(pdf_path, force=force, dpi=dpi)


def main():
    ap = argparse.ArgumentParser(description="PDF (スキャン画像) を ndlocr-lite で OCR してテキスト化する")
    ap.add_argument("--source-dir", help="対象ディレクトリ (直下の *.pdf を処理)")
    ap.add_argument("--pdf", help="対象 PDF ファイルを一つだけ処理")
    ap.add_argument("--all", action="store_true", help="data/pdf/ 以下の全 PDF を対象 (問題PDFはOCR、正答PDFはMarkdown抽出)")
    ap.add_argument("--force", action="store_true", help="既存の .ocr.txt があっても再実行する")
    ap.add_argument("--dpi", type=int, default=150, help="PNG レンダリング解像度 (デフォルト 150)")
    args = ap.parse_args()

    if not os.path.exists(NDLOCR_PY):
        print(f"ERROR: {NDLOCR_PY} が見つかりません。")
        print("       tools/ndlocr-lite で venv 作成・依存インストールを行ってください:")
        print("       cd tools/ndlocr-lite && python -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements.txt")
        sys.exit(1)

    if args.pdf:
        targets = [args.pdf]
    elif args.source_dir:
        targets = sorted(glob.glob(os.path.join(args.source_dir, "*.pdf")))
    elif args.all:
        targets = sorted(glob.glob(os.path.join(REPO_ROOT, "data", "pdf", "*", "*.pdf")))
    else:
        print("ERROR: --pdf, --source-dir, --all のいずれかを指定してください。")
        sys.exit(1)

    print(f"対象: {len(targets)} 件")
    for t in targets:
        process_pdf(t, force=args.force, dpi=args.dpi)
    print("完了。")


if __name__ == "__main__":
    main()
