"""会話エージェント：直近24hの自投稿リプに自動返信する"""
import json
import os
import time
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from utils.claude_cli import ask

load_dotenv()

BASE_URL = "https://graph.threads.net/v1.0"
REPLIED_IDS_PATH = Path(__file__).parent / "cache" / "replied_ids.json"
MAX_REPLIES_PER_POST = 3


def _get_token() -> str:
    return os.environ["THREADS_ACCESS_TOKEN"]


def _get_user_id() -> str:
    return os.environ.get("THREADS_USER_ID", "")


def _load_replied_ids() -> set:
    if REPLIED_IDS_PATH.exists():
        try:
            data = json.loads(REPLIED_IDS_PATH.read_text(encoding="utf-8"))
            return set(data.get("ids", []))
        except Exception:
            pass
    return set()


def _save_replied_id(reply_id: str):
    ids = _load_replied_ids()
    ids.add(reply_id)
    REPLIED_IDS_PATH.parent.mkdir(exist_ok=True)
    REPLIED_IDS_PATH.write_text(
        json.dumps({"ids": list(ids)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _get_own_recent_posts() -> list:
    """直近24hの自分の投稿一覧を取得する"""
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    since_ts = int(since.timestamp())

    resp = requests.get(
        f"{BASE_URL}/{_get_user_id()}/threads",
        params={
            "fields": "id,text,timestamp",
            "since": since_ts,
            "access_token": _get_token(),
        },
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def _get_replies(post_id: str) -> list:
    """投稿についたリプライを取得する"""
    resp = requests.get(
        f"{BASE_URL}/{post_id}/replies",
        params={
            "fields": "id,text,username,timestamp",
            "access_token": _get_token(),
        },
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def _generate_reply(original_text: str, reply_text: str, username: str) -> str:
    """りこキャラで自然な返信を生成する"""
    prompt = f"""美容アカウント「りこ」として、フォロワーのコメントに返信してください。

自分の投稿: {original_text}
{username}さんのコメント: {reply_text}

返信ルール:
- 30〜50文字程度で短め
- りこらしく親しみやすい口調
- 絵文字1〜2個使用
- 感謝・共感・一言アドバイスのいずれか
- URLや商品リンクは含めない

返信テキストのみ返してください（説明不要）"""

    return ask(prompt)


def _post_reply(post_id: str, text: str) -> str:
    """リプライを投稿してIDを返す"""
    resp = requests.post(
        f"{BASE_URL}/{_get_user_id()}/threads",
        params={
            "media_type": "TEXT",
            "text": text,
            "reply_to_id": post_id,
            "access_token": _get_token(),
        },
    )
    resp.raise_for_status()
    container_id = resp.json()["id"]

    time.sleep(3)

    resp = requests.post(
        f"{BASE_URL}/{_get_user_id()}/threads_publish",
        params={
            "creation_id": container_id,
            "access_token": _get_token(),
        },
    )
    resp.raise_for_status()
    return resp.json()["id"]


def run_conversation() -> dict:
    """直近24hの投稿リプに最大3件ずつ返信する"""
    replied_ids = _load_replied_ids()
    total_replied = 0

    posts = _get_own_recent_posts()
    print(f"[ConversationAgent] 直近24h投稿: {len(posts)}件")

    for post in posts:
        post_id = post["id"]
        post_text = post.get("text", "")
        replies = _get_replies(post_id)

        new_replies = [r for r in replies if r["id"] not in replied_ids]
        new_replies = new_replies[:MAX_REPLIES_PER_POST]

        if not new_replies:
            continue

        print(f"[ConversationAgent] 投稿 {post_id}: 未返信 {len(new_replies)}件")

        for reply in new_replies:
            reply_id = reply["id"]
            reply_text = reply.get("text", "")
            username = reply.get("username", "ユーザー")

            response_text = _generate_reply(post_text, reply_text, username)
            _post_reply(reply_id, response_text)
            _save_replied_id(reply_id)
            total_replied += 1
            print(f"[ConversationAgent] 返信完了: {reply_id} → {response_text[:30]}...")
            time.sleep(2)

    print(f"[ConversationAgent] 完了: 計{total_replied}件返信")
    return {"total_replied": total_replied}
