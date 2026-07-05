from PIL import Image
import os
import argparse
from pathlib import Path
import math

def create_contact_sheet(image_dir, output_file, grid_size=(4, 4), thumb_size=(400, 565)):
    """
    Create contact sheets (grids of images) from PNG files in a directory.
    """
    image_dir = Path(image_dir)
    images = sorted([f for f in image_dir.glob("*.png") if "contact_sheet" not in f.name])
    
    if not images:
        print(f"No images found in {image_dir}")
        return

    cols, rows = grid_size
    pages_per_sheet = cols * rows
    
    num_sheets = math.ceil(len(images) / pages_per_sheet)
    
    for s in range(num_sheets):
        sheet_images = images[s * pages_per_sheet : (s + 1) * pages_per_sheet]
        
        sheet_width = cols * thumb_size[0]
        sheet_height = rows * thumb_size[1]
        
        contact_sheet = Image.new("RGB", (sheet_width, sheet_height), (255, 255, 255))
        
        for i, img_path in enumerate(sheet_images):
            img = Image.open(img_path)
            img.thumbnail(thumb_size)
            
            x = (i % cols) * thumb_size[0]
            y = (i // cols) * thumb_size[1]
            
            contact_sheet.paste(img, (x, y))
            
        # Format the output filename to include sheet index
        sheet_output = str(output_file).replace(".png", f"_{s+1}.png")
        contact_sheet.save(sheet_output)
        print(f"Saved contact sheet: {sheet_output}")

def main():
    parser = argparse.ArgumentParser(description="Create contact sheets from PNG pages.")
    parser.add_argument("--edition", type=int, required=True, help="Edition number of the exam (e.g., 38)")
    parser.add_argument("--cols", type=int, default=4, help="Number of columns in the grid")
    parser.add_argument("--rows", type=int, default=4, help="Number of rows in the grid")
    
    args = parser.parse_args()

    # Determine project root and base directories
    project_root = Path(__file__).parent.parent
    base_dir = project_root / "data" / "pdf" / f"{args.edition}th"
    image_dir = base_dir / "page_pngs"
    
    if not image_dir.exists():
        print(f"Error: Image directory {image_dir} does not exist.")
        return

    output_file = base_dir / f"contact_sheet_{args.edition}th.png"
    
    create_contact_sheet(
        image_dir, 
        output_file,
        grid_size=(args.cols, args.rows)
    )

if __name__ == "__main__":
    main()
