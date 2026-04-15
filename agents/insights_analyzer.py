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
    """自分の投稿一覧をThreads APIで取得し、各投稿の/insightsからviews/likes/repliesを取る"""
    token = os.environ.get("THREADS_ACCESS_TOKEN")
    user_id = os.environ.get("THREADS_USER_ID")
    if not token or not user_id:
        print("[InsightsAnalyzer] THREADS_ACCESS_TOKEN or THREADS_USER_ID not set")
        return []

    url = f"https://graph.threads.net/v1.0/{user_id}/threads"
    params = {
        "fields": "id,text,timestamp,like_count,replies_count",
        "limit": 25,
        "access_token": token,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        posts = resp.json().get("data", [])
    except Exception as e:
        print(f"[InsightsAnalyzer] 投稿取得エラー: {type(e).__name__}")
        return []

    # 各投稿のinsights APIを叩いてviews取得
    for p in posts:
        media_id = p.get("id")
        if not media_id:
            continue
        try:
            iresp = requests.get(
                f"https://graph.threads.net/v1.0/{media_id}/insights",
                params={"metric": "views,likes,replies", "access_token": token},
                timeout=10,
            )
            if iresp.status_code == 200:
                for item in iresp.json().get("data", []):
                    name = item.get("name")
                    val = 0
                    if "values" in item and item["values"]:
                        val = item["values"][0].get("value", 0)
                    elif "total_value" in item:
                        val = item["total_value"].get("value", 0)
                    if name == "views":
                        p["views"] = val
                    elif name == "likes":
                        p["like_count"] = max(p.get("like_count", 0), val)
                    elif name == "replies":
                        p["replies_count"] = max(p.get("replies_count", 0), val)
        except Exception as e:
            print(f"[InsightsAnalyzer] insights取得失敗 {media_id}: {type(e).__name__}")
        if "views" not in p:
            p["views"] = 0
    return posts


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
        print(f"  ❤️ {p['like_count']} 👁{p.get('views',0)} 「{p['text'][:40]}...」")

    # views上位3件の冒頭をbuzz_patterns.jsonに「実績フック」として追記
    try:
        _bp_path = Path(__file__).parent.parent / "data" / "buzz_patterns.json"
        if _bp_path.exists():
            _bp_data = json.loads(_bp_path.read_text(encoding="utf-8"))
        else:
            _bp_data = {"patterns": []}
        if not isinstance(_bp_data, dict):
            _bp_data = {"patterns": []}
        _existing = _bp_data.get("patterns", [])
        if not isinstance(_existing, list):
            _existing = []
        # 既存の「実績フック」を一旦除外（重複防止）
        _existing = [p for p in _existing if isinstance(p, dict) and p.get("name") != "実績フック"]
        top_views = sorted(posts, key=lambda x: x.get("views", 0), reverse=True)[:3]
        for tp in top_views:
            text = tp.get("text", "")
            if not text:
                continue
            head = text.split("\n")[0][:40]
            _existing.append({
                "name": "実績フック",
                "hook_structure": head,
                "ending_pattern": "",
                "info_fact": "",
                "example": text[:100],
                "views": tp.get("views", 0),
            })
        _bp_data["patterns"] = _existing
        _bp_path.parent.mkdir(parents=True, exist_ok=True)
        _bp_path.write_text(json.dumps(_bp_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[InsightsAnalyzer] buzz_patterns.json に実績フック{len(top_views)}件追記")
    except Exception as e:
        print(f"[InsightsAnalyzer] buzz_patterns.json更新失敗: {type(e).__name__}")

    benchmark_patterns = fetch_benchmark_patterns()

    _wp_path = Path(__file__).parent / "cache" / "winning_patterns.json"
    _wp_path.parent.mkdir(exist_ok=True)
    all_patterns = win_patterns[:5] + benchmark_patterns
    with open(_wp_path, "w", encoding="utf-8") as f:
        json.dump(all_patterns, f, ensure_ascii=False, indent=2)
    # GitHubに永続化（Renderリセット対策）
    try:
        import sys as _sys, pathlib as _pl
        _sys.path.insert(0, str(_pl.Path(__file__).parent.parent))
        from github_sync import save_to_github
        save_to_github("winning_patterns", all_patterns, "auto: update winning_patterns")
    except Exception as _e:
        print(f"[InsightsAnalyzer] GitHub sync skipped: {type(_e).__name__}")
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
        print(f"[InsightsAnalyzer] ユーザーID検索失敗 {username}: {type(e).__name__}")
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
        if account.isdigit():
            user_id = account
        else:
            # 検索API(/search)は400エラーのため使わない
            print(f"[InsightsAnalyzer] {account}: 数値IDではないためスキップ（dynamic_benchmarks.jsonのuser_idに手動設定）")
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
            print(f"[InsightsAnalyzer] {account}: 取得失敗 {type(e).__name__}")

    results.sort(key=lambda x: x["like_count"], reverse=True)
    return results
