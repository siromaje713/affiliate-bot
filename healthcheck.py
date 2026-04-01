"""
healthcheck.py - 投稿停止を自動検知してSlack通知
Renderのcronで毎時実行。最終投稿から5時間以上経過したらアラート。
"""
import os
import requests
from datetime import datetime, timedelta
from pathlib import Path

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID = os.environ.get("THREADS_USER_ID", "")
ALERT_HOURS = 5

def notify(msg):
    if not SLACK_WEBHOOK_URL:
        print(f"[Healthcheck] Slack未設定: {msg}")
        return
    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": msg}, timeout=10)
    except Exception as e:
        print(f"[Healthcheck] Slack通知失敗: {e}")

def check():
    if not THREADS_ACCESS_TOKEN or not THREADS_USER_ID:
        print("[Healthcheck] THREADS env未設定")
        return
    try:
        r = requests.get(
            f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads",
            params={"fields": "timestamp", "limit": 1, "access_token": THREADS_ACCESS_TOKEN},
            timeout=10
        )
        data = r.json()
        posts = data.get("data", [])
        if not posts:
            notify("⚠️ Healthcheck: 投稿が1件もありません")
            return
        last_ts = datetime.fromisoformat(posts[0]["timestamp"].replace("Z", "+00:00"))
        elapsed = datetime.now().astimezone() - last_ts
        hours = elapsed.total_seconds() / 3600
        print(f"[Healthcheck] 最終投稿: {last_ts} ({hours:.1f}時間前)")
        if hours > ALERT_HOURS:
            notify(f"🚨 投稿停止アラート\n最終投稿: {last_ts}\n経過: {hours:.1f}時間\nRenderのcronログを確認してください")
        else:
            print(f"[Healthcheck] OK ({hours:.1f}時間以内)")
    except Exception as e:
        notify(f"❌ Healthcheck エラー: {e}")

if __name__ == "__main__":
    check()
