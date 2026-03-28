"""リプライ投稿エージェント：本文投稿後にアフィリエイトリンクをリプ欄に投稿"""
import json
import time
import os
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Amazon固定（楽天フォールバックは廃止）
_DEFAULT_AMAZON_URL = "https://www.amazon.co.jp/dp/B0CWM6GZTM?tag=rikocosmelab-22"  # アネッサ
BASE_URL = "https://graph.threads.net/v1.0"
COUNTER_PATH = Path("/tmp/reply_count.json")
REPLY_INTERVAL = 1  # 毎回リプする


def _load_counter() -> int:
    if COUNTER_PATH.exists():
        try:
            return json.loads(COUNTER_PATH.read_text(encoding="utf-8")).get("count", 0)
        except Exception:
            pass
    return 0


def _save_counter(count: int):
    COUNTER_PATH.write_text(json.dumps({"count": count}, ensure_ascii=False), encoding="utf-8")


def _should_reply() -> tuple[bool, int]:
    count = _load_counter() + 1
    _save_counter(count)
    return (count % REPLY_INTERVAL == 0), count


def post_reply(post_id: str, text: str) -> str:
    """指定投稿IDへのリプライを投稿してリプライIDを返す"""
    token = os.getenv("THREADS_ACCESS_TOKEN")
    user_id = os.getenv("THREADS_USER_ID")

    resp = requests.post(
        f"{BASE_URL}/{user_id}/threads",
        params={
            "media_type": "TEXT",
            "text": text,
            "reply_to_id": post_id,
            "access_token": token,
        },
    )
    resp.raise_for_status()
    container_id = resp.json()["id"]
    time.sleep(3)

    resp = requests.post(
        f"{BASE_URL}/{user_id}/threads_publish",
        params={"creation_id": container_id, "access_token": token},
    )
    resp.raise_for_status()
    return resp.json()["id"]


def run(post_id: str, dry_run: bool = False, product_name: str = "", affiliate_url: str = "") -> dict:
    """リプライ投稿を実行する。affiliate_urlは必ずorchestratorから渡すこと。"""
    do_reply, count = _should_reply()
    print(f"[ReplyPoster] 投稿カウンター: {count} → {'リプあり' if do_reply else 'スキップ'}")

    if not do_reply:
        return {"skipped": True, "count": count}

    # orchestratorから渡されたURLを使う。未指定ならAmazonデフォルト
    if not affiliate_url:
        affiliate_url = _DEFAULT_AMAZON_URL
        print(f"[ReplyPoster] WARNING: affiliate_url未指定 → デフォルトAmazonURLを使用")

    platform = "Amazon" if "amazon" in affiliate_url.lower() else "楽天"
    reply_text = f"🛒 商品詳細はこちら👇\n{affiliate_url}\n#PR"
    print(f"[ReplyPoster] アフィリエイト: {platform} URL: {affiliate_url}")

    if dry_run:
        print(f"[ReplyPoster][DRY RUN] リプライ予定:\n{reply_text}")
        return {"dry_run": True, "reply_text": reply_text}

    print(f"[ReplyPoster] リプライ投稿中...")
    reply_id = post_reply(post_id, text=reply_text)
    print(f"[ReplyPoster] リプライ完了: reply_id={reply_id}")
    return {"reply_id": reply_id, "reply_text": reply_text, "platform": platform, "url": affiliate_url}
