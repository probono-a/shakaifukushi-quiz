#!/usr/bin/env python3
"""
parse_answers_pdf.py
正答 PDF → 科目リスト + 正答辞書

使い方 (単体実行):
  python converter/parse_answers_pdf.py data/pdf/37th/s_kijun_seitou_37.pdf

import して使う場合:
  from converter.parse_answers_pdf import parse_answers_pdf
  subjects, answers = parse_answers_pdf('data/pdf/37th/s_kijun_seitou_37.pdf')
"""

import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

try:
    import fitz
except ImportError:
    print("ERROR: PyMuPDF が必要です。  pip install pymupdf")
    sys.exit(1)

IGNORE = {
    '【社会福祉士・精神保健福祉士共通科目】', '【専門科目】',
    '社会福祉士・精神保健福祉士共通科目', '専門科目',
}


def parse_answers_pdf(pdf_path: str):
    """
    正答 PDF を解析して科目リストと正答辞書を返す。

    Returns:
      subjects : [(科目名, [問番号, ...]), ...]  — PDF 記載順
      answers  : {問番号(int): [正解番号(int), ...]}
    """
    doc = fitz.open(pdf_path)
    raw = ''.join(p.get_text() for p in doc)
    doc.close()

    lines = [l.strip() for l in raw.split('\n') if l.strip()]
    subjects, answers = [], {}
    qnum_positions = [i for i, l in enumerate(lines) if l == '問題番号']

    prev_subject = None
    for pos in qnum_positions:
        subject = None
        for k in range(pos - 1, max(pos - 20, -1), -1):
            l = lines[k]
            if l in IGNORE or l in ('問題番号', '正 答') or re.match(r'^[\d,]+$', l):
                continue
            subject = l
            break
        # 科目名が見つからない場合（前ブロックの続き）は直前の科目を継続
        if subject is None:
            subject = prev_subject

        q_nums, i = [], pos + 1
        while i < len(lines) and lines[i] != '正 答':
            q_nums.extend(int(n) for n in re.findall(r'\d+', lines[i]))
            i += 1

        i += 1  # '正 答' をスキップ
        for qn in q_nums:
            if i < len(lines):
                answers[qn] = [int(x.strip()) for x in lines[i].split(',')]
                i += 1

        if subject:
            # 同じ科目の続きブロックなら既存エントリに問番号を追記
            if subjects and subjects[-1][0] == subject:
                subjects[-1][1].extend(q_nums)
            else:
                subjects.append((subject, list(q_nums)))
            prev_subject = subject

    return subjects, answers


def main():
    if len(sys.argv) < 2:
        print('使用法: python converter/parse_answers_pdf.py <正答PDFパス>')
        sys.exit(1)

    subjects, answers = parse_answers_pdf(sys.argv[1])
    print(f'科目数: {len(subjects)}  問題数: {len(answers)}')
    for name, q_nums in subjects:
        print(f'  {name}: 問{q_nums[0]}〜問{q_nums[-1]} ({len(q_nums)}問)')


if __name__ == '__main__':
    main()
