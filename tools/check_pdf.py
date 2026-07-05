import sys
import fitz
from pathlib import Path


def analyze_pdfs(folder_path: str):
    folder = Path(folder_path)
    if not folder.exists():
        print(f"エラー: フォルダが見つかりません: {folder_path}")
        sys.exit(1)

    pdf_files = sorted(folder.glob("**/*.pdf"))
    if not pdf_files:
        print(f"PDF ファイルが見つかりません: {folder_path}")
        sys.exit(1)

    print(f"{'ファイル名':<50} {'総ページ':>6} {'テキスト':>8} {'画像':>6}")
    print("-" * 75)

    for pdf_path in pdf_files:
        doc = fitz.open(pdf_path)
        text_pages = 0
        image_pages = 0

        for page in doc:
            text = page.get_text().strip()
            if len(text) > 50:
                text_pages += 1
            else:
                image_pages += 1

        print(f"{pdf_path.name:<50} {len(doc):>6} {text_pages:>8} {image_pages:>6}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("使い方: python analyze_pdfs.py <フォルダパス>")
        print("例:     python analyze_pdfs.py data/pdf")
        sys.exit(1)

    analyze_pdfs(sys.argv[1])