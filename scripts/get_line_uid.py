#!/usr/bin/env python3
"""LINEからWebhookを受け取り、送信者のuserIdを取得して保存する"""
import json
from pathlib import Path
from flask import Flask, request

app = Flask(__name__)
SAVE_PATH = Path(__file__).parent.parent / "agents" / "cache" / "line_user_id.json"

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json(silent=True) or {}
    for event in body.get("events", []):
        uid = event.get("source", {}).get("userId", "")
        if uid.startswith("U"):
            print(f"\n✅ userId取得: {uid}\n")
            SAVE_PATH.parent.mkdir(exist_ok=True)
            SAVE_PATH.write_text(json.dumps({"userId": uid}, ensure_ascii=False))
            print(f"✅ 保存完了: {SAVE_PATH}")
    return "OK", 200

if __name__ == "__main__":
    print("Webhookサーバー起動: http://localhost:8080/webhook")
    print("別ターミナルで: npx localtunnel --port 8080")
    app.run(host="0.0.0.0", port=8080)
