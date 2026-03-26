"""Webスクレイパー：Threads検索ページから競合投稿テキストを取得"""
import json
import re
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path
from bs4 import BeautifulSoup

CACHE_PATH = Path(__file__).parent / "cache" / "competitor_buzz.json"
CACHE_TTL_HOURS = 12

SEARCH_KEYWORDS = ["美顔器", "スキンケア"]  # 2件に絞りタイムアウトを削減
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.9",
}
MIN_TEXT_LENGTH = 20


def _is_cache_valid() -> bool:
    if not CACHE_PATH.exists():
        return False
    data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    # cached_at または collected_at どちらでも有効
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


def _is_japanese(text: str) -> bool:
    return bool(re.search(r'[\u3040-\u9FFF]', text))


def _has_url(text: str) -> bool:
    return bool(re.search(r'https?://', text))


def scrape_keyword(keyword: str) -> list:
    """1キーワードのThreads検索ページからテキストを抽出"""
    url = f"https://www.threads.com/search?q={requests.utils.quote(keyword)}&serp_type=default"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=5)
        if resp.status_code != 200:
            print(f"[WebScraper] {keyword}: HTTP {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # Threads検索結果のテキストノードを抽出（meta/scriptを除く）
        candidates = []
        for tag in soup.find_all(["span", "div", "p"]):
            text = tag.get_text(strip=True)
            if (
                len(text) >= MIN_TEXT_LENGTH
                and _is_japanese(text)
                and not _has_url(text)
                and len(text) <= 300
            ):
                candidates.append(text)

        # 重複除去
        seen = set()
        unique = []
        for t in candidates:
            if t not in seen:
                seen.add(t)
                unique.append(t)

        print(f"[WebScraper] {keyword}: {len(unique)}件取得")
        return unique[:10]

    except Exception as e:
        print(f"[WebScraper] {keyword} スクレイプエラー: {e}")
        return []


def _extract_texts(posts_data: list) -> list:
    """postsフィールドからテキストを抽出（dict形式・str形式両対応）"""
    result = []
    for p in posts_data:
        if isinstance(p, dict):
            result.append(p.get("text", ""))
        elif isinstance(p, str):
            result.append(p)
    return [t for t in result if t]


def run() -> list:
    """競合投稿テキストリストを返す（キャッシュ有効なら再利用）"""
    if _is_cache_valid():
        print("[WebScraper] キャッシュ使用")
        return _extract_texts(_load_cache().get("posts", []))

    print("[WebScraper] Threads検索ページをスクレイプ中...")
    all_posts = []
    for keyword in SEARCH_KEYWORDS:
        posts = scrape_keyword(keyword)
        all_posts.extend(posts)
        time.sleep(1)  # リクエスト間隔

    # 重複除去
    seen = set()
    unique_posts = []
    for p in all_posts:
        if p not in seen:
            seen.add(p)
            unique_posts.append(p)

    _save_cache(unique_posts)
    print(f"[WebScraper] 計{len(unique_posts)}件のテキストを保存")
    return unique_posts
