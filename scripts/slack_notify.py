#!/usr/bin/env python3
"""Slack通知スクリプト: 投稿成功/失敗をSlackに送信"""
import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


def notify(status: str, message: str) -> bool:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("[SlackNotify] SLACK_WEBHOOK_URL未設定 → スキップ", file=sys.stderr)
        return False

    if status == "success":
        text = f"✅ 投稿完了\n📝 {message}"
    else:
        text = f"❌ 投稿失敗\n⚠️ {message}"

    try:
        resp = requests.post(webhook_url, json={"text": text}, timeout=5)
        resp.raise_for_status()
        print(f"[SlackNotify] 送信完了: {status}")
        return True
    except Exception as e:
        print(f"[SlackNotify] 送信エラー: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: slack_notify.py <success|error> <message>")
        sys.exit(1)
    notify(sys.argv[1], sys.argv[2])
