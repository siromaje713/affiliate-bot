#!/usr/bin/env python3
"""
Threadsアクセストークン自動更新スクリプト
- Threads refresh API でトークンを更新
- Render API で両サービスの環境変数を更新
- Slack通知を送信
- ローカル実行時は .env を更新

使用方法:
  python3 scripts/refresh_threads_token.py

環境変数（必須）:
  THREADS_ACCESS_TOKEN  現在のトークン
  RENDER_API_KEY        Render APIキー
  SLACK_WEBHOOK_URL     Slack通知URL

環境変数（任意）:
  DRY_RUN=1             実際に更新しない（確認用）
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta, timezone

RENDER_SERVICE_IDS = [
    "crn-d72ovqm3jp1c7386q0fg",  # postモード
    "crn-d741a6q4d50c73bvbavg",  # replyモード
]

RENDER_API_BASE = "https://api.render.com/v1"
THREADS_REFRESH_URL = "https://graph.threads.net/refresh_access_token"


def slack_notify(webhook_url, message):
    if not webhook_url:
        return
    payload = json.dumps({"text": message}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[Slack] 通知失敗: {e}")


def refresh_threads_token(current_token):
    params = urllib.parse.urlencode({
        "grant_type": "th_refresh_token",
        "access_token": current_token,
    })
    url = f"{THREADS_REFRESH_URL}?{params}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data


def get_render_env_vars(service_id, api_key):
    url = f"{RENDER_API_BASE}/services/{service_id}/env-vars"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def update_render_env_vars(service_id, api_key, updates):
    existing = get_render_env_vars(service_id, api_key)
    env_map = {item["envVar"]["key"]: item["envVar"]["value"] for item in existing}
    env_map.update(updates)
    env_vars_list = [{"key": k, "value": v} for k, v in env_map.items()]
    payload = json.dumps(env_vars_list).encode("utf-8")
    url = f"{RENDER_API_BASE}/services/{service_id}/env-vars"
    req = urllib.request.Request(
        url,
        data=payload,
        method="PUT",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def update_local_env(env_path, key, value):
    if not os.path.exists(env_path):
        return
    with open(env_path, "r") as f:
        lines = f.readlines()
    new_lines = []
    replaced = False
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"{key}={value}\n")
    with open(env_path, "w") as f:
        f.writelines(new_lines)
    print(f"[LocalEnv] {key} を .env に更新しました")


def main():
    current_token = os.environ.get("THREADS_ACCESS_TOKEN", "").strip()
    render_api_key = os.environ.get("RENDER_API_KEY", "").strip()
    slack_url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    dry_run = os.environ.get("DRY_RUN", "0") == "1"

    if not current_token:
        print("[Error] THREADS_ACCESS_TOKEN が未設定です")
        slack_notify(slack_url, "❌ Threadsトークン更新失敗: THREADS_ACCESS_TOKEN未設定")
        sys.exit(1)

    if not render_api_key:
        print("[Error] RENDER_API_KEY が未設定です")
        slack_notify(slack_url, "❌ Threadsトークン更新失敗: RENDER_API_KEY未設定")
        sys.exit(1)

    print("[Token] Threads refresh API を呼び出し中...")
    if dry_run:
        print("[DryRun] 実際の更新はスキップします")
        print(f"[DryRun] 現在のトークン先頭20文字: {current_token[:20]}...")
        return

    try:
        result = refresh_threads_token(current_token)
    except Exception as e:
        msg = f"❌ Threadsトークン更新失敗\nrefresh API エラー: {e}"
        print(f"[Error] {msg}")
        slack_notify(slack_url, msg)
        sys.exit(1)

    new_token = result.get("access_token")
    expires_in = result.get("expires_in", 0)
    token_type = result.get("token_type", "")

    if not new_token:
        msg = f"❌ Threadsトークン更新失敗\nAPIレスポンス: {result}"
        print(f"[Error] {msg}")
        slack_notify(slack_url, msg)
        sys.exit(1)

    jst = timezone(timedelta(hours=9))
    expires_at = datetime.now(jst) + timedelta(seconds=expires_in)
    expires_at_ts = str(int(expires_at.timestamp()))[:10]
    expires_at_str = expires_at.strftime("%Y-%m-%d %H:%M JST")

    print(f"[Token] 新トークン取得成功 (有効期限: {expires_at_str})")

    updates = {
        "THREADS_ACCESS_TOKEN": new_token,
        "THREADS_TOKEN_EXPIRES_AT": expires_at_ts,
    }

    for service_id in RENDER_SERVICE_IDS:
        print(f"[Render] {service_id} の環境変数を更新中...")
        try:
            update_render_env_vars(service_id, render_api_key, updates)
            print(f"[Render] {service_id} 更新完了")
        except Exception as e:
            msg = f"❌ Render環境変数更新失敗\nservice: {service_id}\n{e}"
            print(f"[Error] {msg}")
            slack_notify(slack_url, msg)

    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        update_local_env(env_path, "THREADS_ACCESS_TOKEN", new_token)
        update_local_env(env_path, "THREADS_TOKEN_EXPIRES_AT", expires_at_ts)

    msg = f"✅ Threadsトークン自動更新完了\n新しい有効期限: {expires_at_str}"
    print(f"[Done] {msg}")
    slack_notify(slack_url, msg)


if __name__ == "__main__":
    main()
