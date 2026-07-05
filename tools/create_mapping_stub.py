import os
import json
import argparse
import fitz  # PyMuPDF
from pathlib import Path

def create_mapping_stub(edition):
    """
    Scans PDF files and creates a basic mapping JSON stub.
    """
    project_root = Path(__file__).parent.parent
    pdf_dir = project_root / "data" / "pdf" / f"{edition}th"
    output_dir = project_root / "data" / "json" / f"{edition}th"
    output_path = output_dir / f"mapping_{edition}th.json"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not pdf_dir.exists():
        print(f"Error: PDF directory {pdf_dir} not found.")
        return

    pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith(".pdf")]
    
    # This stub will be populated by the AI agent during Phase 1
    mapping_stub = {
        "edition": edition,
        "files": [],
        "subjects_found_hint": [], # Heuristic hints
        "mapping": [] # To be filled
    }
    
    # Common and Specialized subjects for Social Welfare exam
    known_subjects = [
        "人体の構造と機能及び疾病", "心理学理論と心理的支援", "社会理論と社会システム",
        "現代社会と福祉", "地域福祉の理論と方法", "福祉行財政と福祉計画", "社会保障", 
        "低所得者に対する支援と生活保護制度", "保健医療サービス", "権利擁護を支える法制度",
        "社会調査の基礎", "相談援助の基盤と専門職", "相談援助の理論と方法",
        "障害者に対する支援と障害者自立支援制度", "高齢者に対する支援と介護保険制度",
        "児童や家庭に対する支援と児童家庭福祉制度", "就労支援サービス", "更生保護制度"
    ]

    markdown_dir = pdf_dir / "page_markdowns"
    
    for pdf_file in pdf_files:
        is_answer_key = any(k in pdf_file.lower() for k in ["happyou", "seikai", "answer"])
        if is_answer_key:
            continue
            
        doc = fitz.open(pdf_dir / pdf_file)
        pdf_stem = Path(pdf_file).stem
        
        file_info = {
            "name": pdf_file,
            "page_count": len(doc),
            "markdown_pages_found": 0
        }
        mapping_stub["files"].append(file_info)
        
        # Simple heuristic to find subjects
        for i in range(len(doc)):
            page_num = i + 1
            md_file = markdown_dir / f"{pdf_stem}_page_{page_num}.md"
            
            text = ""
            if md_file.exists():
                file_info["markdown_pages_found"] += 1
                with open(md_file, "r", encoding="utf-8") as f:
                    text = f.read()
            else:
                # Fallback to PDF text extraction (works for text-based PDFs)
                page = doc.load_page(i)
                text = page.get_text()
            
            for subject in known_subjects:
                if subject in text[:1000]: # Look further down for OCR variability
                    if subject not in mapping_stub["subjects_found_hint"]:
                        mapping_stub["subjects_found_hint"].append(subject)
        
        doc.close()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(mapping_stub, f, ensure_ascii=False, indent=2)
    
    print(f"Created mapping stub at: {output_path}")
    print("Next: Use AI vision to refine this into a complete mapping_Xth.json.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a mapping JSON stub from exam PDFs.")
    parser.add_argument("--edition", type=int, required=True, help="Edition number (e.g., 38)")
    args = parser.parse_args()
    
    create_mapping_stub(args.edition)
