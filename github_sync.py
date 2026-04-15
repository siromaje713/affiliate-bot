"""
github_sync.py - 学習データをGitHubに永続化するモジュール
Renderはエフェエラルストレージなので、winning_patterns.jsonなど
重要なJSONをGitHub上のファイルとして保存・読み込みする。

必要なenv var:
  GH_PAT  - repo権限付きPAT
  GITHUB_REPO   - 例: siromaje713/affiliate-bot
"""
import base64
import json
import os
import requests
from pathlib import Path

GH_PAT = os.environ.get("GH_PAT", "")
GITHUB_REPO  = os.environ.get("GITHUB_REPO", "siromaje713/affiliate-bot")
API_BASE     = f"https://api.github.com/repos/{GITHUB_REPO}/contents"

MANAGED_FILES = {
    "winning_patterns": "data/winning_patterns.json",
    "buzz_patterns":    "data/buzz_patterns.json",
    "cycle_counter":    "data/cycle_counter.json",
}

def _headers():
    return {
        "Authorization": f"token {GH_PAT}",
        "Accept": "application/vnd.github.v3+json",
    }

def load_from_github(key: str):
    path = MANAGED_FILES.get(key)
    if not path:
        return None
    try:
        r = requests.get(f"{API_BASE}/{path}", headers=_headers(), timeout=10)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        content = base64.b64decode(r.json()["content"]).decode("utf-8")
        return json.loads(content)
    except Exception as e:
        print(f"[GithubSync] load failed ({key}): {type(e).__name__}")
        return None

def save_to_github(key: str, data, message: str = "") -> bool:
    if not GH_PAT:
        print("[GithubSync] GH_PAT未設定。スキップ。")
        return False
    path = MANAGED_FILES.get(key)
    if not path:
        return False
    if not message:
        message = f"auto: update {key}"
    content_b64 = base64.b64encode(
        json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("utf-8")
    sha = None
    try:
        r = requests.get(f"{API_BASE}/{path}", headers=_headers(), timeout=10)
        if r.status_code == 200:
            sha = r.json().get("sha")
    except Exception:
        pass
    body = {"message": message, "content": content_b64}
    if sha:
        body["sha"] = sha
    try:
        r = requests.put(f"{API_BASE}/{path}", headers=_headers(), json=body, timeout=15)
        r.raise_for_status()
        print(f"[GithubSync] saved: {path}")
        return True
    except Exception as e:
        print(f"[GithubSync] save failed ({key}): {type(e).__name__}")
        return False
