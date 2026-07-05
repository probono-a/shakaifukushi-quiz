import fitz  # PyMuPDF
import os
import argparse
from pathlib import Path

def convert_pdf_to_png(pdf_path, output_dir):
    """
    Convert each page of a PDF file into a PNG image.
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    doc = fitz.open(pdf_path)
    print(f"Processing: {pdf_path.name} ({len(doc)} pages)")
    
    for page_index in range(len(doc)):
        page = doc.load_page(page_index)
        # Output with high resolution (equivalent to ~300dpi)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        
        output_filename = f"{pdf_path.stem}_page_{page_index + 1}.png"
        output_path = output_dir / output_filename
        pix.save(output_path)
        if (page_index + 1) % 10 == 0:
            print(f"  Converted {page_index + 1} pages...")

    print(f"Finished: {pdf_path.name}")
    doc.close()

def main():
    parser = argparse.ArgumentParser(description="Convert exam PDF pages to PNG images.")
    parser.add_argument("--edition", type=int, required=True, help="Edition number of the exam (e.g., 38)")
    parser.add_argument("--input_dir", type=str, help="Custom input directory containing PDFs")
    parser.add_argument("--output_dir", type=str, help="Custom output directory for PNGs")
    
    args = parser.parse_args()

    # Determine project root and base directories
    project_root = Path(__file__).parent.parent
    
    if args.input_dir:
        base_dir = Path(args.input_dir)
    else:
        base_dir = project_root / "data" / "pdf" / f"{args.edition}th"
        
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = base_dir / "page_pngs"
    
    if not base_dir.exists():
        print(f"Error: Input directory {base_dir} does not exist.")
        return

    pdfs = list(base_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDF files found in {base_dir}")
        return

    for pdf in pdfs:
        convert_pdf_to_png(pdf, output_dir)

if __name__ == "__main__":
    main()
