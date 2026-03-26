#!/usr/bin/env python3
"""LINE通知スクリプト: 投稿完了/失敗をLINEに送信"""
import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


def notify(status: str, message: str) -> bool:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if not token or not user_id:
        print("[LineNotify] LINE_CHANNEL_ACCESS_TOKEN or LINE_USER_ID未設定 → スキップ", file=sys.stderr)
        return False

    if status == "success":
        text = f"✅ 投稿完了\n📝 {message}"
    else:
        text = f"❌ 投稿失敗\n⚠️ {message}"

    try:
        resp = requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "to": user_id,
                "messages": [{"type": "text", "text": text}],
            },
            timeout=5,
        )
        resp.raise_for_status()
        print(f"[LineNotify] 送信完了: {status}")
        return True
    except Exception as e:
        print(f"[LineNotify] 送信エラー: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: line_notify.py <success|error> <message>")
        sys.exit(1)
    notify(sys.argv[1], sys.argv[2])
