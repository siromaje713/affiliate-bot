"""ポスターエージェント：Threads API自動投稿（時間帯スケジューリング）"""
import json
import re
import time
import random
from datetime import datetime, timedelta
from pathlib import Path
from utils import threads_api
from agents.writer import save_to_history

HISTORY_PATH = Path(__file__).parent.parent / "data" / "post_history.json"
LOG_PATH = Path(__file__).parent.parent / "data" / "post_log.json"

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
    print(f"[Poster] 投稿中: {text[:30]}...")

    container_id = threads_api.create_post_container(text)
    time.sleep(3)  # Meta推奨: コンテナ作成後3秒待つ
    post_id = threads_api.publish_post(container_id)

    entry = {
        "post_id": post_id,
        "text": text,
        "score": post_data.get("score"),
        "product": post_data.get("product", {}).get("product_name"),
        "posted_at": datetime.now().isoformat(),
    }
    save_log(entry)
    save_to_history(text)
    print(f"[Poster] 投稿完了: post_id={post_id}")
    return entry


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
