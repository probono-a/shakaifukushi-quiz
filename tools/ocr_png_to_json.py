#!/usr/bin/env python3
"""
ocr_png_to_json.py

PNG ページを OCR してスキャフォールド JSON の
  question_text / options / case_text / question_type
を埋める。explanation / keywords は Claude が別途担当する。

使い方:
    # ndlocr-lite (推奨): 事前に ndlocr-lite で JSON を生成しておく
    python tools/ocr_png_to_json.py \\
        --png_dir scratch/34th \\
        --json_dir tmp/34th \\
        --engine ndlocr \\
        [--dump scratch/34th/ocr_raw.txt] \\
        [--dry_run]

    # Tesseract / EasyOCR: PNG から直接 OCR
    python tools/ocr_png_to_json.py \\
        --png_dir scratch/34th \\
        --json_dir tmp/34th \\
        --engine tesseract|easyocr

ndlocr-lite の事前実行:
    python tools/ndlocr-lite/src/ocr.py \\
        --sourcedir scratch/34th --output scratch/34th --json-only

事前インストール (tesseract/easyocr 使用時のみ):
    【Tesseract】
        1. https://github.com/UB-Mannheim/tesseract/wiki から Windows installer を入手
        2. インストール時に「Japanese」言語パックを選択
        3. pip install pytesseract pillow
    【EasyOCR】
        pip install easyocr
"""

import json
import re
import sys
import argparse
from pathlib import Path
from typing import Optional

# ── OCR バックエンド ──────────────────────────────────────────────────────────

def load_engine(name: str):
    if name == "ndlocr":
        return None  # JSON ファイルを直接読むのでランタイム不要
    elif name == "tesseract":
        try:
            import pytesseract  # noqa: F401
            from PIL import Image  # noqa: F401
        except ImportError:
            sys.exit("pytesseract / pillow が見つかりません。pip install pytesseract pillow を実行してください。")
        return None
    elif name == "easyocr":
        try:
            import easyocr
        except ImportError:
            sys.exit("easyocr が見つかりません。pip install easyocr を実行してください。")
        print("EasyOCR モデルをロード中...")
        return easyocr.Reader(["ja"], gpu=False)
    else:
        sys.exit(f"不明なエンジン: {name}")


def ocr_page_ndlocr(img_path: Path) -> str:
    """ndlocr-lite が出力した同名 JSON から本文テキストを抽出する"""
    json_path = img_path.with_suffix(".json")
    if not json_path.exists():
        raise FileNotFoundError(f"ndlocr JSON が見つかりません: {json_path}")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    lines = []
    for block in data.get("contents", []):
        # Y 座標（boundingBox[0][1]）でソートして読み順を確保
        sorted_block = sorted(block, key=lambda x: x["boundingBox"][0][1])
        for item in sorted_block:
            lines.append(item["text"])
    return "\n".join(lines)


def ocr_page(img_path: Path, engine_name: str, reader) -> str:
    if engine_name == "ndlocr":
        return ocr_page_ndlocr(img_path)
    elif engine_name == "tesseract":
        import pytesseract
        from PIL import Image
        img = Image.open(img_path)
        return pytesseract.image_to_string(img, lang="jpn", config="--psm 6 --oem 1")
    else:
        result = reader.readtext(str(img_path), detail=0, paragraph=True)
        return "\n".join(result)


# ── テキスト正規化 ────────────────────────────────────────────────────────────

# ふりがな除去: 漢字の直後の括弧内ひらがな（例: 誤嚥｛えん｝）
_FURIGANA_RE = re.compile(r"[｛〔（(][ぁ-ん]{1,6}[｝〕）)]")
# ページ番号行（－ N－ or ─ N ─）
_PAGENUM_RE = re.compile(r"\n[ \t]*[－―─-]+[ \t]*\d+[ \t]*[－―─-]+[ \t]*\n")
# 連続改行
_MULTI_NL_RE = re.compile(r"\n{3,}")


def normalize(text: str) -> str:
    text = _FURIGANA_RE.sub("", text)
    text = _PAGENUM_RE.sub("\n", text)
    text = re.sub(r"[ \t　]+", " ", text)  # 連続スペース（全角含む）を整理
    text = _MULTI_NL_RE.sub("\n\n", text)
    # OCR 折り返し改行を除去（\n\n は段落区切りとして保持）
    text = text.replace('\n\n', '\x00')
    text = text.replace('\n', '')
    text = text.replace('\x00', '\n\n')
    return text.strip()


def zen2int(c: str) -> int:
    """全角数字 or 半角数字 → int"""
    zenkaku = "０１２３４５６７８９"
    if c in zenkaku:
        return zenkaku.index(c)
    return int(c)


# ── パース ────────────────────────────────────────────────────────────────────

# 問題番号検出: "問題1加齢..." (スペースなし) や "問題　N　" など OCR 揺れを許容
_Q_SPLIT_RE = re.compile(r"(?:^|\n)問\s*題\s*(\d+)\s*", re.MULTILINE)

# 事例ブロック: 〔事　例〕〔事例〕【事例】 etc.
_CASE_RE = re.compile(r"〔[^〕]*?例[^〕]*?〕|【事例】", re.MULTILINE)

# 選択肢先頭: 行頭に 1〜5 または全角１〜５ の後にスペース or 非空白文字が直続
# (?=[^\s]) で「, 数字(年号), ASCII字(M氏など)も含めて幅広く対応
_OPT_LEAD_RE = re.compile(
    r"(?:^|\n)\s*([1-5１-５])(?:[ 　]+|(?=[^\s]))",
    re.MULTILINE,
)


def parse_block(block: str) -> dict:
    """1問分のブロックテキストから question_text / case_text / options を抽出"""

    # ── 選択肢の先頭位置を特定 ──
    opt_m = _OPT_LEAD_RE.search(block)
    if opt_m:
        pre = block[: opt_m.start()].strip()
        opts_raw = block[opt_m.start() :]
    else:
        pre = block.strip()
        opts_raw = ""

    # 「...を\n1つ選びなさい。\n1肺の...」のように "Nつ/Nを選びなさい" が
    # 行頭に来て選択肢 1 と誤検出されるケースを修正:
    # opts_raw の先頭が「N(つ|を)選び...。」なら question_text に戻す
    instr_m = re.match(r"([1-5])([つを][選んびで][^。\n]*。?)\s*\n?", opts_raw)
    if instr_m and re.search(r'選び|選んで', instr_m.group(2)):
        pre = pre + instr_m.group(1) + instr_m.group(2)
        opts_raw = opts_raw[instr_m.end():]

    # ── 事例テキスト ──
    case_text = ""
    question_text = pre
    case_header = _CASE_RE.search(pre)
    if case_header:
        question_text = pre[: case_header.start()].strip()
        case_text = pre[case_header.end() :].strip()

    # ── 選択肢 ──
    # re.split でキャプチャグループを使うと [前, 番号, テキスト, 番号, テキスト, ...] になる
    opt_parts = re.split(
        r"(?:^|\n)\s*([1-5１-５])(?:[ 　]+|(?=[^\s]))",
        opts_raw, flags=re.MULTILINE
    )
    # opt_parts[0] は選択肢より前の余剰テキスト（捨てる）
    options: dict[int, str] = {}
    for i in range(1, len(opt_parts) - 1, 2):
        try:
            num = zen2int(opt_parts[i].strip())
            text = opt_parts[i + 1].strip()
            # 次の選択肢区切りが混入した場合に備えて再分割
            text = re.split(r"\n\s*[1-5１-５][ 　]", text)[0].strip()
            if 1 <= num <= 5:
                options[num] = normalize(text)
        except (ValueError, IndexError):
            pass

    return {
        "question_type": "事例" if case_text else "通常",
        "case_text": normalize(case_text),
        "question_text": normalize(question_text),
        "options": [options.get(i, "TODO: 要確認") for i in range(1, 6)],
    }


def parse_full_text(full_text: str) -> dict[int, dict]:
    """全ページ結合テキスト → {問題番号: フィールド辞書}"""
    full_text = normalize(full_text)

    # re.split でキャプチャグループ → [前文, q1_num, q1_body, q2_num, q2_body, ...]
    parts = _Q_SPLIT_RE.split(full_text)

    questions: dict[int, dict] = {}
    # parts[0] は "問題 1" より前の表紙・注意事項テキスト（スキップ）
    for i in range(1, len(parts) - 1, 2):
        try:
            q_num = int(parts[i])
            block = parts[i + 1]
            questions[q_num] = parse_block(block)
        except (ValueError, IndexError):
            pass

    return questions


# ── JSON 更新 ─────────────────────────────────────────────────────────────────

def build_index(json_dir: Path) -> dict[int, tuple[Path, int]]:
    """question_number → (json_path, index_in_array) のインデックスを構築"""
    index: dict[int, tuple[Path, int]] = {}
    for jf in sorted(json_dir.glob("*.json")):
        data = json.loads(jf.read_text(encoding="utf-8"))
        for idx, entry in enumerate(data):
            qnum = entry.get("question_number")
            if qnum is not None:
                index[qnum] = (jf, idx)
    return index


def apply_to_json(parsed: dict[int, dict], index: dict[int, tuple[Path, int]], dry_run: bool):
    """パース結果を JSON に書き込む（dry_run=True の場合は標準出力のみ）"""
    # ファイルごとにまとめて書き込む
    file_data: dict[Path, list] = {}

    for q_num, fields in sorted(parsed.items()):
        if q_num not in index:
            print(f"  [WARN] 問題 {q_num} が JSON に見つかりません（スキップ）")
            continue

        jpath, idx = index[q_num]

        if dry_run:
            print(f"\n=== 問題 {q_num} ({jpath.name}) ===")
            print(f"  question_type : {fields['question_type']}")
            print(f"  question_text : {fields['question_text'][:80]}...")
            if fields["case_text"]:
                print(f"  case_text     : {fields['case_text'][:60]}...")
            for i, opt in enumerate(fields["options"], 1):
                print(f"  option {i}      : {opt[:60]}")
            continue

        if jpath not in file_data:
            file_data[jpath] = json.loads(jpath.read_text(encoding="utf-8"))

        entry = file_data[jpath][idx]
        entry["question_type"] = fields["question_type"]
        entry["case_text"] = fields["case_text"]
        entry["question_text"] = fields["question_text"]
        entry["options"] = fields["options"]

    if not dry_run:
        for jpath, data in file_data.items():
            jpath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  書き込み完了: {jpath.name}")


# ── メイン ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PNG → OCR → scaffold JSON 埋め込み")
    parser.add_argument("--png_dir", required=True, help="PNG ファイルのディレクトリ (例: scratch/34th)")
    parser.add_argument("--json_dir", required=True, help="scaffold JSON のディレクトリ (例: tmp/34th)")
    parser.add_argument("--engine", choices=["ndlocr", "tesseract", "easyocr"], default="ndlocr",
                        help="OCR エンジン (default: tesseract)")
    parser.add_argument("--dump", metavar="PATH", help="OCR 生テキストをファイルに保存")
    parser.add_argument("--dry_run", action="store_true", help="JSON を書き込まず結果を表示のみ")
    parser.add_argument("--pages", nargs=2, type=int, metavar=("START", "END"),
                        help="処理するページ番号の範囲 (例: --pages 3 12)")
    args = parser.parse_args()

    png_dir = Path(args.png_dir)
    json_dir = Path(args.json_dir)

    if not png_dir.exists():
        sys.exit(f"PNG ディレクトリが見つかりません: {png_dir}")
    if not json_dir.exists():
        sys.exit(f"JSON ディレクトリが見つかりません: {json_dir}")

    # PNG ファイル一覧（p01.png, p02.png ... の順）
    all_pngs = sorted(png_dir.glob("p*.png"), key=lambda p: int(re.search(r"\d+", p.stem).group()))
    if args.pages:
        s, e = args.pages
        all_pngs = [p for p in all_pngs if s <= int(re.search(r"\d+", p.stem).group()) <= e]

    if not all_pngs:
        sys.exit("PNG ファイルが見つかりません。")

    print(f"対象 PNG: {len(all_pngs)} ページ ({all_pngs[0].name} 〜 {all_pngs[-1].name})")

    # OCR エンジン初期化
    reader = load_engine(args.engine)

    # OCR 実行
    pages_text: list[str] = []
    for i, png in enumerate(all_pngs, 1):
        print(f"  OCR [{i}/{len(all_pngs)}] {png.name} ...", end="\r")
        text = ocr_page(png, args.engine, reader)
        pages_text.append(text)
    print()

    full_text = "\n\n".join(pages_text)

    if args.dump:
        dump_path = Path(args.dump)
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        dump_path.write_text(full_text, encoding="utf-8")
        print(f"OCR 生テキストを保存: {dump_path}")

    # パース
    parsed = parse_full_text(full_text)
    print(f"パース完了: {len(parsed)} 問検出")

    if not parsed:
        print("問題が検出されませんでした。--dump で生テキストを確認してください。")
        sys.exit(1)

    # JSON インデックス構築
    index = build_index(json_dir)
    print(f"JSON インデックス: {len(index)} 問")

    # 書き込み
    if args.dry_run:
        print("\n--- dry_run モード (JSON は変更しません) ---")
    apply_to_json(parsed, index, dry_run=args.dry_run)

    if not args.dry_run:
        print("完了。")


if __name__ == "__main__":
    main()
