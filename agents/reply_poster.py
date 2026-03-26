"""リプライ投稿エージェント：本文投稿後にアフィリエイトリンクをリプ欄に投稿（3回に1回）"""
import json
import time
import os
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

AFFILIATE_URL = "https://a.r10.to/h5yZS4"
REPLY_TEXT = f"🛒 商品詳細はこちら👇\n{AFFILIATE_URL}"
BASE_URL = "https://graph.threads.net/v1.0"
COUNTER_PATH = Path(__file__).parent / "cache" / "reply_count.json"
REPLY_INTERVAL = 3  # 何回に1回リプするか


def _load_counter() -> int:
    if COUNTER_PATH.exists():
        try:
            return json.loads(COUNTER_PATH.read_text(encoding="utf-8")).get("count", 0)
        except Exception:
            pass
    return 0


def _save_counter(count: int):
    COUNTER_PATH.parent.mkdir(exist_ok=True)
    COUNTER_PATH.write_text(json.dumps({"count": count}, ensure_ascii=False), encoding="utf-8")


def _should_reply() -> tuple[bool, int]:
    """リプするかどうかとインクリメント後のカウンターを返す"""
    count = _load_counter() + 1
    _save_counter(count)
    return (count % REPLY_INTERVAL == 0), count


def post_reply(post_id: str) -> str:
    """指定投稿IDへのリプライを投稿してリプライIDを返す"""
    token = os.getenv("THREADS_ACCESS_TOKEN")
    user_id = os.getenv("THREADS_USER_ID")

    # リプライコンテナ作成
    resp = requests.post(
        f"{BASE_URL}/{user_id}/threads",
        params={
            "media_type": "TEXT",
            "text": REPLY_TEXT,
            "reply_to_id": post_id,
            "access_token": token,
        },
    )
    resp.raise_for_status()
    container_id = resp.json()["id"]

    time.sleep(3)

    # 公開
    resp = requests.post(
        f"{BASE_URL}/{user_id}/threads_publish",
        params={
            "creation_id": container_id,
            "access_token": token,
        },
    )
    resp.raise_for_status()
    return resp.json()["id"]


def run(post_id: str, dry_run: bool = False) -> dict:
    """リプライ投稿を実行する（3回に1回のみ）"""
    do_reply, count = _should_reply()
    print(f"[ReplyPoster] 投稿カウンター: {count} → {'リプあり' if do_reply else 'スキップ'}")

    if not do_reply:
        return {"skipped": True, "count": count}

    if dry_run:
        print(f"[ReplyPoster][DRY RUN] リプライ予定:\n{REPLY_TEXT}")
        return {"dry_run": True, "reply_text": REPLY_TEXT}

    print(f"[ReplyPoster] リプライ投稿中...")
    reply_id = post_reply(post_id)
    print(f"[ReplyPoster] リプライ完了: reply_id={reply_id}")
    return {"reply_id": reply_id, "reply_text": REPLY_TEXT}
