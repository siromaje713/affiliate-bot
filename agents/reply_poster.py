"""リプライ投稿エージェント：本文投稿後にアフィリエイトリンクをリプ欄に投稿（3回に1回）"""
import json
import time
import os
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

RAKUTEN_URL = "https://a.r10.to/h5yZS4"
BASE_URL = "https://graph.threads.net/v1.0"
COUNTER_PATH = Path("/tmp/reply_count.json")
REPLY_INTERVAL = 1  # 毎回リプする

# 商品キーワード → Amazon環境変数名マッピング
_AMAZON_ENV_MAP = {
    "RF美顔器": "AMAZON_RF_FACIAL_URL",
    "美顔器": "AMAZON_RF_FACIAL_URL",
    "日焼け止め": "AMAZON_SUNSCREEN_URL",
    "ダルバ": "AMAZON_DALBA_URL",
    "ORBIS": "AMAZON_ORBIS_URL",
    "オルビス": "AMAZON_ORBIS_URL",
    "MISSHA": "AMAZON_MISSHA_URL",
    "ミシャ": "AMAZON_MISSHA_URL",
    "肌ラボ": "AMAZON_HADALABO_URL",
    "ヒアルロン": "AMAZON_HADALABO_URL",
    "アネッサ": "AMAZON_ANESSA_URL",
    "ANESSA": "AMAZON_ANESSA_URL",
}


def _get_amazon_url(product_name: str) -> str:
    """商品名から対応するAmazon URLを環境変数から取得する"""
    for keyword, env_key in _AMAZON_ENV_MAP.items():
        if keyword.lower() in product_name.lower():
            url = os.environ.get(env_key, "")
            if url:
                return url
    return ""


def _get_affiliate_url(count: int, product_name: str = "") -> str:
    """偶数カウントは楽天、奇数はAmazon（未設定なら楽天）で交互に使う"""
    if count % 2 == 1:
        amazon_url = _get_amazon_url(product_name)
        if amazon_url:
            return amazon_url
    return RAKUTEN_URL


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
    """リプするかどうかとインクリメント後のカウンターを返す"""
    count = _load_counter() + 1
    _save_counter(count)
    return (count % REPLY_INTERVAL == 0), count


def post_reply(post_id: str, text: str = "") -> str:
    """指定投稿IDへのリプライを投稿してリプライIDを返す"""
    token = os.getenv("THREADS_ACCESS_TOKEN")
    user_id = os.getenv("THREADS_USER_ID")

    # リプライコンテナ作成
    resp = requests.post(
        f"{BASE_URL}/{user_id}/threads",
        params={
            "media_type": "TEXT",
            "text": text or f"🛒 商品詳細はこちら👇\n{RAKUTEN_URL}",
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


def run(post_id: str, dry_run: bool = False, product_name: str = "", affiliate_url: str = "") -> dict:
    """リプライ投稿を実行する。affiliate_urlが指定されればそれを使う。"""
    do_reply, count = _should_reply()
    print(f"[ReplyPoster] 投稿カウンター: {count} → {'リプあり' if do_reply else 'スキップ'}")

    if not do_reply:
        return {"skipped": True, "count": count}

    if not affiliate_url:
        affiliate_url = _get_affiliate_url(count, product_name)

    platform = "Amazon" if "amazon" in affiliate_url.lower() or "amzn" in affiliate_url.lower() else "楽天"
    reply_text = f"🛒 商品詳細はこちら👇\n{affiliate_url}\n#PR"
    print(f"[ReplyPoster] アフィリエイト: {platform} URL: {affiliate_url[:60]}")

    if dry_run:
        print(f"[ReplyPoster][DRY RUN] リプライ予定:\n{reply_text}")
        return {"dry_run": True, "reply_text": reply_text}

    print(f"[ReplyPoster] リプライ投稿中...")
    reply_id = post_reply(post_id, text=reply_text)
    print(f"[ReplyPoster] リプライ完了: reply_id={reply_id}")
    return {"reply_id": reply_id, "reply_text": reply_text, "platform": platform, "url": affiliate_url}
