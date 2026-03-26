#!/usr/bin/env python3
"""LINEユーザーIDをWebhookで取得するサーバー"""
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

CACHE_PATH = Path(__file__).parent.parent / "agents" / "cache" / "line_user_id.json"
found_user_id = None


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        global found_user_id
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        self.send_response(200)
        self.end_headers()

        for event in body.get("events", []):
            uid = event.get("source", {}).get("userId")
            if uid and uid.startswith("U"):
                found_user_id = uid
                print(f"\n✅ ユーザーID取得: {uid}")
                # .envを更新
                env_path = Path(__file__).parent.parent / ".env"
                lines = env_path.read_text().splitlines()
                new_lines = [f"LINE_USER_ID={uid}" if l.startswith("LINE_USER_ID=") else l for l in lines]
                if not any(l.startswith("LINE_USER_ID=") for l in lines):
                    new_lines.append(f"LINE_USER_ID={uid}")
                env_path.write_text("\n".join(new_lines) + "\n")
                print(f"✅ .envのLINE_USER_IDを更新しました: {uid}")

    def log_message(self, format, *args):
        pass  # ログ抑制


if __name__ == "__main__":
    port = 8080
    server = HTTPServer(("0.0.0.0", port), WebhookHandler)
    print(f"Webhookサーバー起動中: http://localhost:{port}")
    print("次のステップ:")
    print("  1. 別ターミナルで: ngrok http 8080")
    print("  2. ngrokのForwarding URL（https://xxxx.ngrok.io）をコピー")
    print("  3. LINE Developers → Messaging API → Webhook URL に設定")
    print("  4. Botに任意のメッセージを送信")
    print("  5. ユーザーIDが自動取得されます\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nサーバー停止")
