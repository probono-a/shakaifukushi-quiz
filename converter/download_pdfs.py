import os
import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import argparse

def download_file(url, download_dir):
    try:
        # URL を解析してファイル名を取得
        parsed_url = urllib.parse.urlparse(url)
        filename = os.path.basename(parsed_url.path)
        if not filename:
            return False

        # ファイルパスを作成
        filepath = os.path.join(download_dir, filename)

        # 既に存在する場合はスキップ (再ダウンロード防止)
        if os.path.exists(filepath):
            print(f"Skipping already downloaded file: {filename}")
            return True

        print(f"Downloading: {url} -> {filename}")
        
        # ファイルのダウンロード
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        # サーバーへの負荷軽減のため少し待機
        time.sleep(1)
        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False

def scrape_jaswe_pdfs(download_dir, edition=None):
    print("--- 日本ソーシャルワーク教育学校連盟 (jaswe.jp) からのダウンロード ---")
    base_url = "https://jaswe.jp/kokushiinfo.html"
    try:
        response = requests.get(base_url, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # PDF リンクを抽出
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if href.lower().endswith('.pdf'):
                full_url = urllib.parse.urljoin(base_url, href)
                
                # 社会福祉士関連のファイル名パターン (csw, shakai, shakaifukushishi など)
                lower_url = full_url.lower()
                is_social_work = 'csw' in lower_url or 'shakai' in lower_url
                
                if not is_social_work:
                    continue

                # 回数が指定されている場合、URL に回数が含まれているか確認
                if edition:
                    # 例: 38th, 38shakai のようなパターンに一致するか
                    if f"{edition}th" not in lower_url and f"{edition}shakai" not in lower_url:
                        continue

                download_file(full_url, download_dir)
                
    except Exception as e:
        print(f"Error accessing jaswe.jp: {e}")

def main():
    parser = argparse.ArgumentParser(description="社会福祉士国家試験の過去問 PDF をダウンロードします")
    parser.add_argument("--edition", type=int, help="ダウンロードする試験の回数 (例: 38)")
    args = parser.parse_args()

    # ダウンロード先ディレクトリの作成
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base_pdf_dir = os.path.join(project_root, 'data', 'pdf')
    
    if args.edition:
        print(f"Target edition: 第 {args.edition} 回")
        pdf_dir = os.path.join(base_pdf_dir, f"{args.edition}th")
    else:
        pdf_dir = base_pdf_dir

    os.makedirs(pdf_dir, exist_ok=True)
    print(f"Download directory: {pdf_dir}")
    
    # sssc.or.jp からのダウンロードは jaswe.jp に一本化するため廃止
    scrape_jaswe_pdfs(pdf_dir, edition=args.edition)
    
    print("ダウンロード処理が完了しました")

if __name__ == "__main__":
    main()
