import os
import requests
import argparse
from pathlib import Path

def download_file(url, save_path):
    print(f"Downloading {url} to {save_path}...")
    response = requests.get(url)
    response.raise_for_status()
    with open(save_path, "wb") as f:
        f.write(response.content)

def main():
    parser = argparse.ArgumentParser(description="Fetch Social Welfare Exam HTML and PDF files.")
    parser.add_argument("--edition", type=int, required=True, help="Exam edition number (e.g., 38)")
    parser.add_argument("--am_url", type=str, help="Optional specific AM HTML URL")
    parser.add_argument("--pm_url", type=str, help="Optional specific PM HTML URL")
    parser.add_argument("--ans_url", type=str, help="Optional specific Answer Key PDF URL")
    
    args = parser.parse_args()
    edition = args.edition
    
    # Base directory
    base_dir = Path(f"data/source/{edition}th")
    base_dir.mkdir(parents=True, exist_ok=True)
    
    # Default URLs
    am_url = args.am_url or f"https://www.sssc.or.jp/shakai/past_exam/pdf/no{edition}/listen_ss_am_{edition}.html"
    pm_url = args.pm_url or f"https://www.sssc.or.jp/shakai/past_exam/pdf/no{edition}/listen_ss_pm_{edition}.html"
    ans_url = args.ans_url or f"https://www.sssc.or.jp/shakai/past_exam/pdf/no{edition}/s_kijun_seitou.pdf"
    
    # Download
    try:
        download_file(am_url, base_dir / f"listen_ss_am_{edition}.html")
        download_file(pm_url, base_dir / f"listen_ss_pm_{edition}.html")
        download_file(ans_url, base_dir / f"answer_key_{edition}.pdf")
        print(f"Successfully fetched 38th exam data to {base_dir}")
    except Exception as e:
        print(f"Error fetching data: {e}")
        if edition == 38:
            print("Note: 38th exam answer key might be at a temporary URL. Try passing --ans_url explicitly.")

if __name__ == "__main__":
    main()
