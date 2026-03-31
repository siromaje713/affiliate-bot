"""ベンチマーク投稿を手動でwinning_patterns.jsonに追記する

使い方:
  python3 scripts/import_benchmark.py <threads_url> [like_count]

例:
  python3 scripts/import_benchmark.py https://www.threads.com/@popo.biyou/post/xxxxx 604
"""
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

WINNING_PATTERNS_PATH = Path(__file__).parent.parent / "agents" / "cache" / "winning_patterns.json"


def _get_token() -> str:
    token = os.environ.get("THREADS_ACCESS_TOKEN")
    if not token:
        raise SystemExit("THREADS_ACCESS_TOKEN が未設定です")
    return token


def _parse_url(url: str) -> tuple:
    """ThreadsのURLからpost_idとaccountを抽出する"""
    # https://www.threads.com/@account/post/POSTID
    # https://www.threads.net/@account/post/POSTID
    m = re.search(r'/@([^/]+)/post/([A-Za-z0-9_-]+)', url)
    if not m:
        raise SystemExit(f"URLからpost_idを抽出できませんでした: {url}")
    account = m.group(1)
    post_id_str = m.group(2)
    return account, post_id_str


def _shortcode_to_id(shortcode: str) -> str:
    """Base64urlエンコードされたshortcodeを数値IDに変換する"""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    n = 0
    for c in shortcode:
        n = n * 64 + alphabet.index(c)
    return str(n)


def _fetch_post(post_id: str) -> dict:
    token = _get_token()
    resp = requests.get(
        f"https://graph.threads.net/v1.0/{post_id}",
        params={"fields": "id,text,timestamp", "access_token": token},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def _load_patterns() -> list:
    if WINNING_PATTERNS_PATH.exists():
        try:
            return json.loads(WINNING_PATTERNS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_patterns(patterns: list):
    WINNING_PATTERNS_PATH.parent.mkdir(parents=True, exist_ok=True)
    WINNING_PATTERNS_PATH.write_text(
        json.dumps(patterns, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    url = sys.argv[1]
    like_count = int(sys.argv[2]) if len(sys.argv) >= 3 else 0

    account, post_id_str = _parse_url(url)

    # shortcode（文字列）を数値IDに変換して投稿を取得
    try:
        numeric_id = _shortcode_to_id(post_id_str)
        post = _fetch_post(numeric_id)
    except Exception as e:
        print(f"API取得失敗（shortcode変換後ID: {numeric_id}）: {e}")
        print("post_idを直接数値で指定してください")
        sys.exit(1)

    text = post.get("text", "")
    post_date = post.get("timestamp", datetime.now().isoformat())

    entry = {
        "source": "manual",
        "account": account,
        "like_count": like_count,
        "hook_text": text[:50],
        "full_text": text,
        "post_date": post_date,
    }

    patterns = _load_patterns()
    # 重複チェック（同じfull_textがあればスキップ）
    if any(p.get("full_text") == text for p in patterns):
        print(f"既に登録済みです: {text[:40]}...")
        sys.exit(0)

    patterns.append(entry)
    _save_patterns(patterns)
    print(f"追記完了: ❤️{like_count} @{account}")
    print(f"  hook: {text[:50]}")
    print(f"  合計: {len(patterns)}件")


if __name__ == "__main__":
    main()
