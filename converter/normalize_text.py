#!/usr/bin/env python3
"""
normalize_text.py
クイズ JSON 用テキスト正規化ユーティリティ

単体実行 (既存 JSON に後がけ):
  python converter/normalize_text.py data/json/37th/listen_ss_am_37.json

フォルダ指定 (フォルダ以下の全 JSON に適用):
  python converter/normalize_text.py tmp/37_pm/

import して使う場合:
  from converter.normalize_text import normalize_text, normalize_question_stem, normalize_option
"""

import json
import re
import sys
from pathlib import Path

_FULL = str.maketrans('0123456789', '０１２３４５６７８９')

# 全角アルファベット・全角ハイフン → 半角: 例) ＭＭＰＩ → MMPI, WAIS－Ⅳ → WAIS-Ⅳ
_WIDE_ALPHA = str.maketrans(
    'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ－',
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-',
)

_CJK = r'぀-鿿'  # ひらがな・カタカナ・漢字 (U+3040–U+9FFF)


def normalize_text(text: str) -> str:
    # ふりがな除去: 例) 誤嚥｛えん｝ → 誤嚥
    text = re.sub(r'｛[^｝]*｝', '', text)
    # ノーブレークスペース → 通常スペース
    text = text.replace('\xa0', ' ')
    # 半角コンマ読点 → 日本語読点: 例) 福祉,介護 / 福祉, 介護 → 福祉、介護（CJK隣接時のみ）
    text = re.sub(rf'(?<=[{_CJK}]),\s*(?=[{_CJK}])', '、', text)
    # 全角アルファベット → 半角: 例) ＭＭＰＩ → MMPI
    text = text.translate(_WIDE_ALPHA)
    # 全角括弧 → 半角: 例) （注） → (注)
    text = text.replace('（', '(').replace('）', ')')
    # 全角コロン → 半角、直後にスペースを補う: 例) DSM-5：主要な変更 → DSM-5: 主要な変更
    # ※ :// (URL) は除外
    text = text.replace('：', ':')
    text = re.sub(r':(?=[^ /\n])', ': ', text)
    # 余分な空白を整理
    text = re.sub(r'[ \t]+', ' ', text)
    # CJK・仮名 ↔ 半角英数字の間にスペース: 例) 第38回 → 第 38 回
    text = re.sub(rf'([{_CJK}])([0-9A-Za-z])', r'\1 \2', text)
    text = re.sub(rf'([0-9A-Za-z])([{_CJK}])', r'\1 \2', text)
    # CJK・仮名 ↔ 半角括弧の間にスペース: 例) 年(昭和38年)の → 年 (昭和 38 年) の
    # ※ 「、」「。」は U+3001/3002 で _CJK 範囲外のため「は、(」などは影響なし
    text = re.sub(rf'([{_CJK}」』〕〉】〗〛〙])\(', r'\1 (', text)
    text = re.sub(rf'\)([{_CJK}])', r') \1', text)
    # 一桁の半角数字 → 全角（英数字コードの一部でないものに限る）
    # 例) 第 1 号 → 第１号, 2 つ → ２つ  ただし DSM-5, pH7 は変換しない
    # ※ CJK スペーシング後に適用することで前後スペースも次工程で除去できる
    text = re.sub(
        r'(?<![0-9A-Za-z\-\.])([1-9])(?![0-9A-Za-z\-\.])',
        lambda m: m.group(1).translate(_FULL),
        text,
    )
    # 全角数字と CJK の間に残ったスペースを除去: 例) の ５ つ → の５つ
    text = re.sub(rf'([{_CJK}]) ([０-９])', r'\1\2', text)
    text = re.sub(rf'([０-９]) ([{_CJK}])', r'\1\2', text)
    return text.strip()


def normalize_question_stem(text: str) -> str:
    text = re.sub(r'^問題\d+[\s　\xa0]+', '', text)
    # 「Nつ選びなさい」の単桁数字を全角に（normalize_text の汎用変換と二重適用になるが無害）
    text = re.sub(r'([1-9])(つ選)', lambda m: m.group(1).translate(_FULL) + m.group(2), text)
    return normalize_text(text)


def normalize_option(text: str) -> str:
    text = re.sub(r'^\d+[\s　\xa0]+', '', text)
    return normalize_text(text)


# ── 既存 JSON への後がけ ───────────────────────────────────────────────────────

_TEXT_FIELDS = ('question_text', 'case_text', 'explanation')


def normalize_question(q: dict) -> dict:
    for field in _TEXT_FIELDS:
        if field in q and isinstance(q[field], str):
            q[field] = normalize_text(q[field])
    if 'options' in q:
        q['options'] = [normalize_text(o) for o in q['options']]
    if 'keywords' in q:
        q['keywords'] = [normalize_text(k) for k in q['keywords']]
    return q


def normalize_file(path: str) -> None:
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, list):
        print(f'ERROR: {path} のルートが配列ではありません')
        sys.exit(1)
    changed_ids = []
    for q in data:
        before = json.dumps(q, ensure_ascii=False)
        normalize_question(q)
        if json.dumps(q, ensure_ascii=False) != before:
            changed_ids.append(q.get('id', '?'))
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if changed_ids:
        print(f'{path}: {len(changed_ids)} 問変更 ({", ".join(changed_ids)})', flush=True)
    else:
        print(f'{path}: 変更なし', flush=True)


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    if len(sys.argv) < 2:
        print('使用法: python converter/normalize_text.py <JSONファイルまたはフォルダ> [...]', flush=True)
        sys.exit(1)

    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.is_dir():
            files = sorted(p.glob('*.json'))
            if not files:
                print(f'警告: {arg} に JSON ファイルが見つかりませんでした', flush=True)
                continue
            print(f'フォルダ {arg}: {len(files)} ファイルを処理します', flush=True)
            for f in files:
                normalize_file(str(f))
        elif p.is_file():
            normalize_file(str(p))
        else:
            print(f'ERROR: {arg} が見つかりません', flush=True)
            sys.exit(1)


if __name__ == '__main__':
    main()
