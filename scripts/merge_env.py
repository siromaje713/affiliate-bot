import json, os, sys

try:
    with open("/tmp/existing.json") as f:
        existing = json.load(f)
    existing_map = {item["envVar"]["key"]: item["envVar"]["value"] for item in existing}
except Exception:
    existing_map = {}

updates = {
    "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
    "THREADS_ACCESS_TOKEN": os.environ.get("THREADS_ACCESS_TOKEN", ""),
    "THREADS_USER_ID": os.environ.get("THREADS_USER_ID", ""),
    "SLACK_WEBHOOK_URL": os.environ.get("SLACK_WEBHOOK_URL", ""),
    "THREADS_TOKEN_EXPIRES_AT": os.environ.get("THREADS_TOKEN_EXPIRES_AT", ""),
}
existing_map.update({k: v for k, v in updates.items() if v})
result = [{"key": k, "value": v} for k, v in existing_map.items()]

# ファイルに書き出す（シェル変数経由だとクォートが壊れるため）
with open("/tmp/merged.json", "w") as f:
    json.dump(result, f)
print("ok")
