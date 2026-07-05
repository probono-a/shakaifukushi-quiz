import os
import requests
from pathlib import Path

# Base directory for downloads
BASE_DIR = Path(r"c:\dev\kentaro-anno\shakaifukushi-quiz\data\pdf")

# Mapping of exam files to download
# Format: { exam_id: { filename: url } }
# 第36回以降の問題ファイルは sssc.or.jp の音声読み上げ用 HTML を使用
EXAMS = {
    "38th": {
        "listen_ss_am_38.html": "https://www.sssc.or.jp/shakai/past_exam/pdf/no38/listen_ss_am_38.html",
        "listen_ss_pm_38.html": "https://www.sssc.or.jp/shakai/past_exam/pdf/no38/listen_ss_pm_38.html",
        "s_kijun_seitou_38.pdf": "https://www.sssc.or.jp/goukaku/SZSpLiR4XL7ARHp3RbF26PeSuRg29p/pdf/s_kijun_seitou.pdf",
    },
    "37th": {
        "listen_ss_am_37.html": "https://www.sssc.or.jp/shakai/past_exam/pdf/no37/listen_ss_am_37.html",
        "listen_ss_pm_37.html": "https://www.sssc.or.jp/shakai/past_exam/pdf/no37/listen_ss_pm_37.html",
        "s_kijun_seitou_37.pdf": "https://www.sssc.or.jp/shakai/past_exam/pdf/no37/s_kijun_seitou.pdf",
    },
    "36th": {
        "listen_sp_am_36.html": "https://www.sssc.or.jp/shakai/past_exam/pdf/no36/listen_sp_am_36.html",
        "listen_sp_pm_36.html": "https://www.sssc.or.jp/shakai/past_exam/pdf/no36/listen_sp_pm_36.html",
        "s_kijun_seitou_36.pdf": "https://www.sssc.or.jp/shakai/past_exam/pdf/no36/s_kijun_seitou.pdf",
    },
    "35th": {
        "35th_common.pdf": "https://jaswe.jp/TEST/2022nendo_35th25th_cswmhsw_test.pdf",
        "35th_specialized.pdf": "https://jaswe.jp/TEST/2022nendo_35th_csw_test.pdf",
        "35th_answer.pdf": "https://jaswe.jp/doc/20230307_35shakai_happyou.pdf"
    },
    "34th": {
        "34th_common.pdf": "https://jaswe.jp/TEST/2021nendo_34th24th_cswmhsw_test.pdf",
        "34th_specialized.pdf": "https://jaswe.jp/TEST/2021nendo_34th_csw_test.pdf",
        "34th_answer.pdf": "https://jaswe.jp/doc/20220315_34shakai_happyou.pdf"
    },
    "33rd": {
        "33rd_common.pdf": "https://jaswe.jp/TEST/33th_cswmhsw_test_am.pdf",
        "33rd_specialized.pdf": "https://jaswe.jp/TEST/33th_csw_test_pm.pdf",
        "33rd_answer.pdf": "https://jaswe.jp/doc/20210315_33shakai_happyou.pdf"
    },
    "32nd": {
        "32nd_am.pdf": "https://jaswe.jp/TEST/32th_cswpsw_test_am.pdf",
        "32nd_pm.pdf": "https://jaswe.jp/TEST/32th_csw_test_pm.pdf",
        "32nd_answer.pdf": "https://jaswe.jp/doc/20200313_32shakai_happyou.pdf.pdf"
    },
    "31st": {
        "31st_am.pdf": "https://jaswe.jp/TEST/31th_cswpsw_test_am.pdf",
        "31st_pm.pdf": "https://jaswe.jp/TEST/31th_csw_test_pm.pdf",
        "31st_answer.pdf": "https://jaswe.jp/doc/20190315_31shakai_happyou.pdf"
    },
    "30th": {
        "30th_am.pdf": "https://jaswe.jp/TEST/30th_cswpsw_test_am.pdf",
        "30th_pm.pdf": "https://jaswe.jp/TEST/30th_csw_test_pm.pdf",
        "30th_answer.pdf": "https://jaswe.jp/TEST/30th_happyou/30th_goukakuhappyou.pdf"
    },
    "29th": {
        "29th_am.pdf": "https://jaswe.jp/TEST/29th_shakaifukushishi_test_am.pdf",
        "29th_pm.pdf": "https://jaswe.jp/TEST/29th_shakaifukushishi_test_pm.pdf",
        "29th_answer.pdf": "https://jaswe.jp/TEST/29th_happyou/29th_goukakuhappyou.pdf"
    },
    "28th": {
        "28th_am.pdf": "https://jaswe.jp/TEST/28th_shakaifukushishi_test_am.pdf",
        "28th_pm.pdf": "https://jaswe.jp/TEST/28th_shakaifukushishi_test_pm.pdf",
        "28th_answer.pdf": "https://jaswe.jp/TEST/28th_happyou/28th_goukakuhappyou.pdf"
    },
    "27th": {
        "27th_am.pdf": "https://jaswe.jp/TEST/27th_shakaifukushishi_test_am.pdf",
        "27th_pm.pdf": "https://jaswe.jp/TEST/27th_shakaifukushishi_test_pm.pdf",
        "27th_answer.pdf": "https://jaswe.jp/TEST/27th_happyou/27th_goukakuhappyou.pdf"
    },
    "26th": {
        "26th_am.pdf": "https://jaswe.jp/TEST/26th_shakaifukushishi_test_am.pdf",
        "26th_pm.pdf": "https://jaswe.jp/TEST/26th_shakaifukushishi_test_pm.pdf",
        "26th_answer.pdf": "https://jaswe.jp/TEST/26th_happyou/26th_goukakuhappyou.pdf"
    }
}

# Add 18th - 25th based on pattern (approximate, might need adjustment)
for i in range(18, 26):
    exam_id = f"{i}th"
    EXAMS[exam_id] = {
        f"{exam_id}_am.pdf": f"https://jaswe.jp/TEST/{i}th_shakaifukushishi_test_am.pdf",
        f"{exam_id}_pm.pdf": f"https://jaswe.jp/TEST/{i}th_shakaifukushishi_test_pm.pdf"
    }
    if i >= 19: # Answer keys available for 19+ based on subagent report
        EXAMS[exam_id][f"{exam_id}_answer.pdf"] = f"https://jaswe.jp/TEST/{i}th_happyou/{i}th_goukakuhappyou.pdf"

def download_file(url, dest_path):
    print(f"Downloading {url} to {dest_path}...")
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Success.")
    except Exception as e:
        print(f"Failed to download {url}: {e}")

if __name__ == "__main__":
    for exam_id, files in EXAMS.items():
        exam_dir = BASE_DIR / exam_id
        for filename, url in files.items():
            dest_path = exam_dir / filename
            if not dest_path.exists():
                download_file(url, dest_path)
            else:
                print(f"Skipping {filename}, already exists.")
