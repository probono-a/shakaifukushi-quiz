import os
import json
import re
import fitz
from bs4 import BeautifulSoup
from pathlib import Path
import argparse

def parse_answer_key_pdf(pdf_path):
    """
    Extracts answer keys from the SSSC results PDF.
    Expects a structure where question numbers and answers are listed in blocks.
    """
    doc = fitz.open(pdf_path)
    # Usually answer keys are on Page 4 or 5 for recent exams. 
    # We'll search for the "正答" or " " pattern across all pages just in case.
    answers = {}
    
    for page in doc:
        text = page.get_text()
        # Look for blocks of numbers. 
        # A common pattern is a row/column of question numbers followed by a row/column of answers.
        # But in text extraction, they often appear as interleaved sequences.
        
        # Heuristic: Find all sequences that look like a question number (1-150)
        # followed by answers (1-5 or combinations like 1,2).
        
        # Let's try a more robust approach: 
        # Find "番号" (Number) and "正答" (Answer) headers and extract numbers below them.
        # Since encoding might be weird, we look for digits.
        
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        current_nums = []
        in_num_block = False
        in_ans_block = False
        
        for i, line in enumerate(lines):
            # Header detection (using regex to be encoding-agnostic for headers if possible)
            if "番号" in line or "ԍ" in line:
                in_num_block = True
                in_ans_block = False
                current_nums = []
                continue
            elif "正答" in line or " " in line:
                in_num_block = False
                in_ans_block = True
                ans_idx = 0
                continue
            
            if in_num_block:
                if line.isdigit():
                    current_nums.append(int(line))
                else:
                    # End of num block
                    in_num_block = False
            elif in_ans_block:
                # Expecting something like "1" or "1,2" or "3,5"
                if re.match(r'^[1-5](,[1-5])*$', line):
                    if ans_idx < len(current_nums):
                        q_num = current_nums[ans_idx]
                        ans_vals = [int(v) for v in line.split(",")]
                        answers[q_num] = ans_vals
                        ans_idx += 1
                else:
                    in_ans_block = False
                    
    return answers

def apply_formatting_rules(text):
    """
    Applies the rule: 'Add a half-width space between full-width characters and half-width alphanumeric characters'.
    Also cleans up multiple spaces.
    """
    if not text:
        return ""
    
    # Rule: [Full-width][Half-width Alphanumeric] -> [Full-width] [Half-width Alphanumeric]
    text = re.sub(r'([\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF])([a-zA-Z0-9])', r'\1 \2', text)
    # Rule: [Half-width Alphanumeric][Full-width] -> [Half-width Alphanumeric] [Full-width]
    text = re.sub(r'([a-zA-Z0-9])([\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF])', r'\1 \2', text)
    
    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_html_exam(html_path, edition):
    """
    Parses the audio-support HTML from SSSC.
    """
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    
    questions = []
    current_subject = "不明"
    
    container = soup.find("div", class_="listen_exam") or soup.body
    
    for element in container.find_all(["h2", "dl"]):
        if element.name == "h2":
            current_subject = apply_formatting_rules(element.get_text().strip())
            continue
        
        if element.name == "dl":
            dt = element.find("dt")
            dds = element.find_all("dd")
            
            if not dt: continue
            
            raw_text = dt.get_text(separator=" ").strip()
            # Extract question number
            match = re.match(r'問題(\d+)\s*(.*)', raw_text, re.DOTALL)
            if not match: continue
            
            q_num = int(match.group(1))
            full_text = match.group(2).strip()
            
            # Case text handling
            case_text = ""
            if "〔事" in full_text and "例〕" in full_text:
                parts = re.split(r'〔事\s*例〕', full_text)
                question_text = parts[0].strip()
                case_text = parts[1].strip()
            else:
                question_text = full_text
            
            # Clean up question and case text
            question_text = apply_formatting_rules(question_text)
            case_text = apply_formatting_rules(case_text)
            
            options = []
            for dd in dds:
                opt_text = dd.get_text().strip()
                # Remove leading number and spaces
                opt_text = re.sub(r'^\d+\s*', '', opt_text)
                # Remove trailing period if present
                opt_text = opt_text.rstrip('。')
                options.append(apply_formatting_rules(opt_text))
            
            questions.append({
                "id": f"{edition}_{q_num}",
                "edition": edition,
                "subject": current_subject,
                "question_number": q_num,
                "question_type": "single", # Default, updated in merge
                "case_text": case_text,
                "question_text": question_text,
                "is_multiple_answers": False, # Updated in merge
                "options": options,
                "correct_options": [], # Updated in merge
                "explanation": "",
                "keywords": [],
                "reference_links": [],
                "image_paths": []
            })
            
    return questions

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", type=int, required=True)
    parser.add_argument("--am_html", type=str)
    parser.add_argument("--pm_html", type=str)
    parser.add_argument("--ans_pdf", type=str)
    args = parser.parse_args()
    
    edition = args.edition
    base_dir = Path(f"data/pdf/{edition}th") # Updated to data/pdf/ based on check
    
    am_path = args.am_html or base_dir / f"listen_ss_am_{edition}.html"
    pm_path = args.pm_html or base_dir / f"listen_ss_pm_{edition}.html"
    ans_path = args.ans_pdf or base_dir / f"20260303_38shakai_happyou.pdf"
    
    print(f"Parsing {edition}th exam...")
    
    # 1. Parse answers
    answers = parse_answer_key_pdf(ans_path)
    print(f"Extracted {len(answers)} answers from PDF.")
    
    # 2. Parse HTML
    all_questions = []
    if os.path.exists(am_path):
        all_questions.extend(parse_html_exam(am_path, edition))
    if os.path.exists(pm_path):
        all_questions.extend(parse_html_exam(pm_path, edition))
    
    print(f"Extracted {len(all_questions)} questions from HTML.")
    
    # 3. Merge
    for q in all_questions:
        q_num = q["question_number"]
        if q_num in answers:
            ans_list = answers[q_num]
            q["correct_options"] = ans_list
            q["is_multiple_answers"] = len(ans_list) > 1
            q["question_type"] = "multiple" if len(ans_list) > 1 else "single"
        else:
            print(f"Warning: No answer found for Question {q_num}")
    
    # 4. Save
    out_dir = Path(f"data/json/{edition}th")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"exam_{edition}th.json"
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=2)
    
    print(f"Saved merged JSON to {out_path}")

if __name__ == "__main__":
    main()
