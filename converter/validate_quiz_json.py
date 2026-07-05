import json
import sys
import re

# Windowsのコンソール出力でのUnicodeEncodeError対策
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def validate_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ エラー: JSON ファイルの読み込みに失敗しました ({e})")
        return False

    if not isinstance(data, list):
        print("❌ エラー: JSON のルートが配列(list)ではありません。")
        return False

    required_keys = [
        "id", "edition", "subject", "question_number", "question_type", 
        "case_text", "question_text", "is_multiple_answers", "options", 
        "correct_options", "explanation", "keywords", "reference_links", "image_paths"
    ]

    has_error = False
    total_questions = len(data)
    print(f"📊 対象ファイル: {file_path}")
    print(f"📊 総問題数: {total_questions}問\n")

    for i, q in enumerate(data):
        q_id = q.get('id', f'Unknown (Index {i})')
        errors = []

        # 1. 必須キーの確認
        for key in required_keys:
            if key not in q:
                errors.append(f"必須キー '{key}' が不足しています。")

        # 以降のチェックは必須キーが存在する場合のみ
        if not errors:
            # 2. IDフォーマットの確認
            expected_id = f"{q['edition']}_{q['question_number']}"
            if q['id'] != expected_id:
                errors.append(f"ID のフォーマットが不正です。期待値: '{expected_id}', 実際: '{q['id']}'")

            # 3. 複数解答フラグの整合性
            correct_opts = q.get('correct_options', [])
            is_multi = q.get('is_multiple_answers', False)
            if len(correct_opts) > 1 and not is_multi:
                errors.append("正解が複数あるのに `is_multiple_answers` が false になっています。")
            elif len(correct_opts) == 1 and is_multi:
                errors.append("正解が1つのみなのに `is_multiple_answers` が true になっています。")
            
            # 4. 正解番号の範囲チェック
            options = q.get('options', [])
            for c_opt in correct_opts:
                if c_opt < 1 or c_opt > len(options):
                    errors.append(f"正解番号 '{c_opt}' が選択肢の数（{len(options)}）の範囲外です。")

            # 5. 全角半角スペースのチェック（簡易的：数字と全角文字が隣接していないか）
            # 対象テキストフィールドを結合してチェック
            text_fields = [
                q.get('subject', ''),
                q.get('question_text', ''),
                q.get('explanation', '')
            ] + options
            
            # 正規表現：(半角英数字と全角文字が直接隣接している箇所を検出)
            # 全角文字（ひらがな、カタカナ、漢字等）を適度に含む簡易正規表現
            pattern = re.compile(r'([a-zA-Z0-9][\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF])|([\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF][a-zA-Z0-9])')
            for text in text_fields:
                if pattern.search(text):
                    errors.append("全角文字と半角英数字の間に半角スペースが不足している箇所があります。（要目視確認）")
                    break # 1つの問題につき1回だけ警告

        # エラー表示
        if errors:
            has_error = True
            print(f"⚠️ 問題 {q_id} でエラーが検出されました:")
            for err in errors:
                print(f"  - {err}")
            print()

    if not has_error:
        print("✅ すべてのバリデーションをクリアしました！問題ありません。")
        return True
    else:
        print("❌ いくつかの問題でエラーが検出されました。JSON を確認してください。")
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("使用法: python validate_quiz_json.py <JSONファイルのパス>")
        sys.exit(1)
    
    validate_json(sys.argv[1])
