"""インサイト分析エージェント：自分の投稿データから勝ちパターンを抽出"""
import json
import os
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CACHE_PATH = Path(__file__).parent / "cache" / "own_insights.json"
CACHE_TTL_HOURS = 6


def _is_cache_valid() -> bool:
    if not CACHE_PATH.exists():
        return False
    data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
    return datetime.now() - cached_at < timedelta(hours=CACHE_TTL_HOURS)


def _load_cache() -> dict:
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def _save_cache(data: dict):
    CACHE_PATH.parent.mkdir(exist_ok=True)
    data["cached_at"] = datetime.now().isoformat()
    CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_own_posts() -> list:
    """自分の投稿一覧をThreads APIで取得"""
    token = os.environ.get("THREADS_ACCESS_TOKEN")
    user_id = os.environ.get("THREADS_USER_ID")
    if not token or not user_id:
        print("[InsightsAnalyzer] THREADS_ACCESS_TOKEN or THREADS_USER_ID not set")
        return []

    url = f"https://graph.threads.net/v1.0/{user_id}/threads"
    params = {
        "fields": "id,text,timestamp,like_count,replies_count,views",
        "limit": 25,
        "access_token": token,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception as e:
        print(f"[InsightsAnalyzer] 投稿取得エラー: {e}")
        return []


def extract_win_patterns(posts: list) -> list:
    """いいね上位5件を勝ちパターンとして返す"""
    valid = [p for p in posts if p.get("text") and p.get("like_count", 0) >= 0]
    sorted_posts = sorted(valid, key=lambda p: p.get("like_count", 0), reverse=True)
    top5 = sorted_posts[:5]
    return [
        {
            "text": p["text"][:80],
            "like_count": p.get("like_count", 0),
            "replies_count": p.get("replies_count", 0),
            "views": p.get("views", 0),
        }
        for p in top5
    ]


def run() -> list:
    """勝ちパターン投稿リストを返す（キャッシュ有効なら再利用）"""
    if _is_cache_valid():
        print("[InsightsAnalyzer] キャッシュ使用")
        return _load_cache().get("win_patterns", [])

    print("[InsightsAnalyzer] 自分の投稿データを取得中...")
    posts = fetch_own_posts()
    if not posts:
        print("[InsightsAnalyzer] 投稿データなし")
        return []

    win_patterns = extract_win_patterns(posts)
    _save_cache({"win_patterns": win_patterns})
    print(f"[InsightsAnalyzer] 勝ちパターン {len(win_patterns)}件を抽出")
    for p in win_patterns:
        print(f"  ❤️ {p['like_count']} 「{p['text'][:40]}...」")

    # 勝ちパターンをwriter.pyが読めるJSONに書き出す
    import json as _json
    _wp_path = Path(__file__).parent / "cache" / "winning_patterns.json"
    _wp_path.parent.mkdir(exist_ok=True)
    with open(_wp_path, "w", encoding="utf-8") as f:
        _json.dump(win_patterns[:5], f, ensure_ascii=False, indent=2)
    print(f"[InsightsAnalyzer] winning_patterns.json に {min(len(win_patterns),5)}件書き出し完了")
    return win_patterns
