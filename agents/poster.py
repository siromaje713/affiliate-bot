"""ポスターエージェント：Threads API自動投稿（時間帯スケジューリング）"""
import json
import re
import time
import random
from datetime import datetime, timedelta
from pathlib import Path
from utils import threads_api
from agents.writer import save_to_history

HISTORY_PATH = Path("/tmp/post_history.json")
LOG_PATH = Path("/tmp/post_log.json")

# 投稿時間帯（時）とゆらぎ（分）
SCHEDULE_HOURS = [6, 12, 21]
JITTER_MINUTES = 30  # ±30分のランダムゆらぎ


def load_log() -> list:
    if not LOG_PATH.exists():
        return []
    return json.loads(LOG_PATH.read_text(encoding="utf-8"))


def save_log(entry: dict):
    log = load_log()
    log.insert(0, entry)
    LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def next_post_time() -> datetime:
    """次の投稿予定時刻を計算する（ゆらぎ込み）"""
    now = datetime.now()
    for hour in SCHEDULE_HOURS:
        scheduled = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        jitter = random.randint(-JITTER_MINUTES, JITTER_MINUTES)
        scheduled += timedelta(minutes=jitter)
        if scheduled > now:
            return scheduled
    # 今日の全スロットが過ぎていたら翌日6時
    tomorrow = now + timedelta(days=1)
    jitter = random.randint(-JITTER_MINUTES, JITTER_MINUTES)
    return tomorrow.replace(hour=6, minute=0) + timedelta(minutes=jitter)


def strip_links(text: str) -> str:
    """本文からURLとリンクプレースホルダーを除去する"""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'→?\s*\[楽天リンク\]', '', text)
    return text.strip()


def post_now(post_data: dict) -> dict:
    """即時投稿して結果を返す"""
    text = strip_links(post_data["text"])
    image_url = post_data.get("image_url")
    print(f"[Poster] 投稿中({'画像付き' if image_url else 'テキスト'}): {text[:30]}...")

    container_id = threads_api.create_post_container(text, image_url=image_url)
    time.sleep(3)  # Meta推奨: コンテナ作成後3秒待つ
    post_id = threads_api.publish_post(container_id)

    entry = {
        "post_id": post_id,
        "text": text,
        "score": post_data.get("score"),
        "product": post_data.get("product", {}).get("product_name"),
        "post_type": post_data.get("post_type"),
        "posted_at": datetime.now().isoformat(),
    }
    save_log(entry)
    save_to_history(text)
    print(f"[Poster] 投稿完了: post_id={post_id}")
    return entry


def post_self_reply(reply_to_id: str, text: str) -> str:
    """自分の投稿に対して補足リプを投稿。リプのpost_idを返す。失敗時は空文字。"""
    try:
        container_id = threads_api.create_post_container(text, reply_to_id=reply_to_id)
        time.sleep(3)
        reply_post_id = threads_api.publish_post(container_id)
        print(f"[Poster] 自己リプ完了: {reply_post_id}")
        return reply_post_id
    except Exception as e:
        print(f"[Poster] 自己リプ失敗: {type(e).__name__}")
        return ""


def run(post_data: dict, dry_run: bool = False) -> dict:
    """
    ポスター実行。
    dry_run=True の場合は投稿せず内容だけ表示する。
    """
    if dry_run:
        text = strip_links(post_data["text"])
        print(f"[Poster][DRY RUN] 投稿予定テキスト:\n{text}")
        print(f"[Poster][DRY RUN] 品質スコア: {post_data.get('score')}")
        return {"dry_run": True, **post_data}

    return post_now(post_data)
