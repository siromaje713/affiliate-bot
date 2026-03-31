"""インサイト分析エージェント：自分の投稿データとベンチマークアカウントから勝ちパターンを抽出"""
import json
import os
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CACHE_PATH = Path(__file__).parent / "cache" / "own_insights.json"
CACHE_TTL_HOURS = 6
BENCHMARK_LIKE_THRESHOLD = 100


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

    benchmark_patterns = fetch_benchmark_patterns()

    _wp_path = Path(__file__).parent / "cache" / "winning_patterns.json"
    _wp_path.parent.mkdir(exist_ok=True)
    all_patterns = win_patterns[:5] + benchmark_patterns
    with open(_wp_path, "w", encoding="utf-8") as f:
        json.dump(all_patterns, f, ensure_ascii=False, indent=2)
    print(f"[InsightsAnalyzer] winning_patterns.json に 自分{min(len(win_patterns),5)}件+ベンチマーク{len(benchmark_patterns)}件 書き出し完了")
    return win_patterns


def _lookup_user_id(username: str, token: str) -> str:
    """ユーザー名から数値IDを取得する"""
    try:
        resp = requests.get(
            "https://graph.threads.net/v1.0/search",
            params={"q": username, "type": "USER", "fields": "id,username", "access_token": token},
            timeout=10,
        )
        resp.raise_for_status()
        for u in resp.json().get("data", []):
            if u.get("username", "").lower() == username.lower():
                return u["id"]
    except Exception as e:
        print(f"[InsightsAnalyzer] ユーザーID検索失敗 {username}: {e}")
    return ""


def fetch_benchmark_patterns() -> list:
    """BENCHMARK_ACCOUNT_IDSのアカウントからいいね100超え投稿を取得する"""
    token = os.environ.get("THREADS_ACCESS_TOKEN")
    if not token:
        return []

    raw = os.getenv("BENCHMARK_ACCOUNT_IDS", "")
    accounts = [e.strip() for e in raw.split(",") if e.strip()]
    if not accounts:
        return []

    results = []
    for account in accounts:
        user_id = account if account.isdigit() else _lookup_user_id(account, token)
        if not user_id:
            print(f"[InsightsAnalyzer] {account}: ID取得失敗 → スキップ")
            continue
        try:
            resp = requests.get(
                f"https://graph.threads.net/v1.0/{user_id}/threads",
                params={"fields": "id,text,like_count,timestamp", "limit": 30, "access_token": token},
                timeout=10,
            )
            resp.raise_for_status()
            posts = resp.json().get("data", [])
            hit = 0
            for p in posts:
                text = p.get("text", "")
                like_count = p.get("like_count", 0)
                if text and like_count >= BENCHMARK_LIKE_THRESHOLD:
                    results.append({
                        "source": "benchmark",
                        "account": account,
                        "like_count": like_count,
                        "hook_text": text[:50],
                        "full_text": text,
                        "post_date": p.get("timestamp", ""),
                    })
                    hit += 1
            print(f"[InsightsAnalyzer] {account}: {hit}件（いいね{BENCHMARK_LIKE_THRESHOLD}+）取得")
        except Exception as e:
            print(f"[InsightsAnalyzer] {account}: 取得失敗 {e}")

    results.sort(key=lambda x: x["like_count"], reverse=True)
    return results
