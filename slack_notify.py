import os
import requests

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

def notify(status: str, message: str):
    if not SLACK_WEBHOOK_URL:
        print(f"[Slack] SLACK_WEBHOOK_URL未設定。通知スキップ: {message}")
        return
    payload = {"text": message}
    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"[Slack] 通知送信完了: {status}")
    except Exception as e:
        print(f"[Slack] 通知失敗: {e}")
