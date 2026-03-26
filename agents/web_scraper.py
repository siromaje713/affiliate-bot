"""Webスクレイパー：Threads Search API（threads_keyword_search）で実データ取得
- いいね数・リプライ数・文字数・画像有無を含む実データ
- HTTPスクレイピング（空振り）から完全移行
"""
import json
import os
import re
import requests
import time
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CACHE_PATH = Path(__file__).parent / "cache" / "competitor_buzz.json"
CACHE_TTL_HOURS = 12

# 検索キーワード（季節に合わせて変える）
SEARCH_KEYWORDS = ["日焼け止め", "美顔器", "スキンケア", "美白", "紫外線対策"]

THREADS_API_BASE = "https://graph.threads.net/v1.0"


def _is_cache_valid() -> bool:
    if not CACHE_PATH.exists():
        return False
    data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    ts = data.get("cached_at") or data.get("collected_at", "2000-01-01")
    try:
        cached_at = datetime.fromisoformat(ts)
    except ValueError:
        return False
    return datetime.now() - cached_at < timedelta(hours=CACHE_TTL_HOURS)


def _load_cache() -> dict:
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def _save_cache(posts: list):
    CACHE_PATH.parent.mkdir(exist_ok=True)
    data = {"cached_at": datetime.now().isoformat(), "posts": posts}
    CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def search_threads_keyword(keyword: str, access_token: str, limit: int = 20) -> list:
    """Threads Search APIでキーワード検索。いいね数・リプライ数・文字数・画像有無を返す"""
    url = f"{THREADS_API_BASE}/threads/search"
    params = {
        "q": keyword,
        "fields": "id,text,timestamp,like_count,replies_count,has_replies,media_type",
        "limit": limit,
        "access_token": access_token,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 403:
            print(f"[WebScraper] {keyword}: 403 - threads_keyword_search権限なし（審査待ちの可能性）")
            return []
        if resp.status_code != 200:
            print(f"[WebScraper] {keyword}: HTTP {resp.status_code} - {resp.text[:100]}")
            return []
        data = resp.json().get("data", [])
        print(f"[WebScraper] {keyword}: {len(data)}件取得")
        return data
    except Exception as e:
        print(f"[WebScraper] {keyword} APIエラー: {e}")
        return []


def enrich_post(post: dict) -> dict:
    """投稿データにメトリクス・分析情報を付加する"""
    text = post.get("text", "")
    like_count = int(post.get("like_count", 0))
    replies_count = int(post.get("replies_count", 0))
    media_type = post.get("media_type", "TEXT")
    has_image = media_type in ("IMAGE", "CAROUSEL_ALBUM", "VIDEO")

    char_count = len(text)
    has_number = bool(re.search(r'\d', text))
    has_question = "?" in text or "？" in text or "どう" in text or "みんな" in text
    has_before_after = bool(re.search(r'\d+[日週ヶ月分回]', text))
    is_first_person = bool(re.search(r'私|わたし|先週|届いた|使った|試した', text))

    # エンゲージメントスコア（いいね×2 + リプライ×5）
    engagement_score = like_count * 2 + replies_count * 5

    return {
        "text": text[:109],  # 109文字で切る
        "like_count": like_count,
        "replies_count": replies_count,
        "has_image": has_image,
        "char_count": char_count,
        "has_number": has_number,
        "has_question": has_question,
        "has_before_after": has_before_after,
        "is_first_person": is_first_person,
        "engagement_score": engagement_score,
        "media_type": media_type,
    }


def analyze_patterns(posts: list) -> dict:
    """収集した投稿からバズパターンを分析する"""
    if not posts:
        return {}

    top_posts = sorted(posts, key=lambda p: p["engagement_score"], reverse=True)[:10]

    # 画像あり vs なし のエンゲージメント平均
    with_img = [p for p in posts if p["has_image"]]
    without_img = [p for p in posts if not p["has_image"]]
    avg_img = sum(p["engagement_score"] for p in with_img) / len(with_img) if with_img else 0
    avg_no_img = sum(p["engagement_score"] for p in without_img) / len(without_img) if without_img else 0

    # 文字数別エンゲージメント
    short = [p for p in posts if p["char_count"] <= 50]
    medium = [p for p in posts if 51 <= p["char_count"] <= 80]
    long_ = [p for p in posts if p["char_count"] > 80]
    avg_short = sum(p["engagement_score"] for p in short) / len(short) if short else 0
    avg_medium = sum(p["engagement_score"] for p in medium) / len(medium) if medium else 0
    avg_long = sum(p["engagement_score"] for p in long_) / len(long_) if long_ else 0

    # 問いかけあり/なし
    with_q = [p for p in posts if p["has_question"]]
    avg_with_q = sum(p["engagement_score"] for p in with_q) / len(with_q) if with_q else 0

    return {
        "total_posts": len(posts),
        "top_posts": top_posts[:5],
        "image_effect": {
            "with_image_avg": round(avg_img, 1),
            "without_image_avg": round(avg_no_img, 1),
            "image_wins": avg_img > avg_no_img,
        },
        "char_count_effect": {
            "short_50_avg": round(avg_short, 1),
            "medium_51_80_avg": round(avg_medium, 1),
            "long_81plus_avg": round(avg_long, 1),
            "best_length": "50以下" if avg_short >= max(avg_medium, avg_long)
                           else "51-80" if avg_medium >= avg_long else "81以上",
        },
        "question_effect": {
            "with_question_avg": round(avg_with_q, 1),
            "question_count": len(with_q),
        },
    }


def run() -> list:
    """競合投稿の実データを返す（キャッシュ有効なら再利用）"""
    if _is_cache_valid():
        print("[WebScraper] キャッシュ使用")
        cached = _load_cache()
        posts = cached.get("posts", [])
        # dict形式（enriched）とstr形式（旧）両対応
        return [p if isinstance(p, dict) else {"text": p, "like_count": 0, "engagement_score": 0}
                for p in posts]

    token = os.environ.get("THREADS_ACCESS_TOKEN")
    if not token:
        print("[WebScraper] THREADS_ACCESS_TOKEN未設定 → スキップ")
        return []

    print("[WebScraper] Threads Search APIで競合投稿を収集中...")
    all_posts = []

    for keyword in SEARCH_KEYWORDS[:3]:  # 1回のrun()で3キーワード（API節約）
        raw_posts = search_threads_keyword(keyword, token, limit=15)
        for post in raw_posts:
            if post.get("text"):
                all_posts.append(enrich_post(post))
        time.sleep(0.5)

    if not all_posts:
        print("[WebScraper] データ取得ゼロ（権限審査待ちか、トークン期限切れの可能性）")
        return []

    # エンゲージメント順でソート・重複除去
    seen = set()
    unique = []
    for p in sorted(all_posts, key=lambda x: x["engagement_score"], reverse=True):
        if p["text"] not in seen:
            seen.add(p["text"])
            unique.append(p)

    # パターン分析を追加して保存
    analysis = analyze_patterns(unique)
    print(f"[WebScraper] {len(unique)}件収集完了")
    print(f"[WebScraper] 画像あり平均スコア: {analysis.get('image_effect', {}).get('with_image_avg', 0)}")
    print(f"[WebScraper] 最適文字数: {analysis.get('char_count_effect', {}).get('best_length', '不明')}")

    _save_cache(unique)
    return unique
