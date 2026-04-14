"""バズリサーチエージェント：Threadsバイラル投稿からリアルタイムでパターンを動的抽出"""
import json
import os
import time
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from utils.claude_cli import ask_json, MODEL_OPUS

load_dotenv()

BASE_URL = "https://graph.threads.net/v1.0"
VIRAL_CACHE_PATH = Path(__file__).parent / "cache" / "viral_posts_cache.json"
BUZZ_PATTERNS_PATH = Path(__file__).parent.parent / "data" / "buzz_patterns.json"
CACHE_TTL_HOURS = 6

def _load_benchmark_accounts() -> list:
    """BENCHMARK_ACCOUNT_IDS環境変数からアカウント名/IDを読む"""
    raw = os.getenv("BENCHMARK_ACCOUNT_IDS", "")
    return [e.strip() for e in raw.split(",") if e.strip()]


COMPETITOR_USERNAMES = _load_benchmark_accounts() or ["popo.biyou"]


def _get_token() -> str:
    return os.environ["THREADS_ACCESS_TOKEN"]


def _get_user_id() -> str:
    return os.environ["THREADS_USER_ID"]


def _is_cache_fresh(cache_path: Path) -> bool:
    if not cache_path.exists():
        return False
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(data["cached_at"])
        return datetime.now(timezone.utc) - cached_at < timedelta(hours=CACHE_TTL_HOURS)
    except Exception:
        return False


def _fetch_own_posts() -> list:
    """自分の投稿をいいね+リプ数でスコアリングして返す"""
    try:
        resp = requests.get(
            f"{BASE_URL}/{_get_user_id()}/threads",
            params={
                "fields": "id,text,like_count,replies_count,timestamp",
                "limit": 30,
                "access_token": _get_token(),
            },
            timeout=15,
        )
        resp.raise_for_status()
        posts = resp.json().get("data", [])
        for p in posts:
            p["engagement_score"] = p.get("like_count", 0) + p.get("replies_count", 0) * 2
            p["source"] = "own"
        return posts
    except Exception as e:
        print(f"[BuzzResearcher] 自分の投稿取得エラー: {e}")
        return []


def _fetch_competitor_posts(username: str) -> list:
    """競合アカウントの投稿を取得する（失敗時は空リスト）"""
    try:
        # username → user_id 解決
        resp = requests.get(
            f"{BASE_URL}/{username}",
            params={
                "fields": "id",
                "access_token": _get_token(),
            },
            timeout=10,
        )
        resp.raise_for_status()
        user_id = resp.json().get("id")
        if not user_id:
            return []

        resp = requests.get(
            f"{BASE_URL}/{user_id}/threads",
            params={
                "fields": "id,text,like_count,replies_count,timestamp",
                "limit": 20,
                "access_token": _get_token(),
            },
            timeout=15,
        )
        resp.raise_for_status()
        posts = resp.json().get("data", [])
        for p in posts:
            p["engagement_score"] = p.get("like_count", 0) + p.get("replies_count", 0) * 2
            p["source"] = f"competitor:{username}"
        return posts
    except Exception as e:
        print(f"[BuzzResearcher] 競合 @{username} 取得失敗（スキップ）: {e}")
        return []


def _load_competitor_cache() -> list:
    """既存のcompetitor_buzz.jsonをフォールバックとして読む"""
    cache = Path(__file__).parent / "cache" / "competitor_buzz.json"
    if not cache.exists():
        return []
    try:
        posts_data = json.loads(cache.read_text(encoding="utf-8")).get("posts", [])
        result = []
        for p in posts_data:
            if isinstance(p, dict):
                p["engagement_score"] = p.get("like_count", 0) + p.get("replies_count", 0) * 2
                p["source"] = "competitor_cache"
                result.append(p)
        return result
    except Exception:
        return []


def fetch_viral_posts() -> list:
    """自分+競合のバイラル投稿上位10件を取得・キャッシュする（6時間TTL）"""
    if _is_cache_fresh(VIRAL_CACHE_PATH):
        print("[BuzzResearcher] バイラルキャッシュ使用（TTL内）")
        return json.loads(VIRAL_CACHE_PATH.read_text(encoding="utf-8")).get("posts", [])

    print("[BuzzResearcher] バイラル投稿をリアルタイム取得中...")
    all_posts = _fetch_own_posts()

    for username in COMPETITOR_USERNAMES:
        comp_posts = _fetch_competitor_posts(username)
        if comp_posts:
            all_posts.extend(comp_posts)
        else:
            all_posts.extend(_load_competitor_cache())
            break

    if not all_posts:
        print("[BuzzResearcher] 投稿取得失敗")
        return []

    top10 = sorted(all_posts, key=lambda x: x.get("engagement_score", 0), reverse=True)[:10]

    VIRAL_CACHE_PATH.parent.mkdir(exist_ok=True)
    VIRAL_CACHE_PATH.write_text(
        json.dumps(
            {"cached_at": datetime.now(timezone.utc).isoformat(), "posts": top10},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[BuzzResearcher] バイラル投稿 {len(top10)}件キャッシュ保存")
    return top10


def extract_patterns_from_viral(posts: list) -> list:
    """バイラル投稿をClaudeに渡してバズパターンを動的抽出する"""
    if not posts:
        return []

    posts_text = "\n".join([
        f"{i+1}. ❤️{p.get('like_count',0)} 💬{p.get('replies_count',0)} 「{p.get('text','')[:80]}」"
        for i, p in enumerate(posts)
    ])

    prompt = f"""以下はThreads美容アカウントの実際にエンゲージメントが高かった投稿です。

{posts_text}

これらを分析して、バズっている投稿の「型」をJSON形式で10〜15パターン抽出してください。
固定のテンプレートではなく、実際の投稿から観察できる冒頭の型・感情トリガー・構成・語尾パターンを抽出すること。

【追加要件】
- 各投稿から「info_fact（有益情報の核心1文）」を抽出してパターンに含めること
  例: 「日焼け止めは500円玉大が必要量」「洗顔後3分以内に保湿しないと水分が空気に奪われる」
- 返信が10往復以上来るような「会話設計」（問いかけ・行動訂正・知識ギャップ）を優先する
- 上記の実投稿パターンに加えて、2026年4月現在のThreadsで美容ジャンルでバズっている
  フック構造を推測でさらに10パターン追加すること（合計20〜25パターン目標）

{{
  "patterns": [
    {{
      "name": "パターン名（例: 知識暴露型・行動訂正型・やり方暴露型など）",
      "hook_structure": "冒頭の型（例: 〜って〇〇らしい）",
      "emotion_trigger": "使われている感情トリガー",
      "ending_pattern": "語尾・締め方の特徴",
      "info_fact": "有益情報の核心1文（必須・新ネタを推測でも入れる）",
      "example": "このパターンで書いた美容投稿の例文（100文字以内）"
    }}
  ]
}}

JSONのみ返してください（説明不要）。"""

    try:
        result = ask_json(prompt, model=MODEL_OPUS)
        patterns = result.get("patterns", [])
        print(f"[BuzzResearcher] {len(patterns)}パターン動的抽出完了")

        BUZZ_PATTERNS_PATH.write_text(
            json.dumps(
                {"updated_at": datetime.now(timezone.utc).isoformat(), "patterns": patterns},
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
        return patterns
    except Exception as e:
        print(f"[BuzzResearcher] パターン抽出エラー: {e}")
        return []


def get_buzz_context() -> dict:
    """バイラル投稿取得→パターン抽出を実行してbuzz_patternsを返す（外部インターフェース）"""
    posts = fetch_viral_posts()
    patterns = extract_patterns_from_viral(posts)
    return {"posts": posts, "patterns": patterns}


def run() -> list:
    """後方互換: バズネタリスト形式で返す"""
    context = get_buzz_context()
    posts = context.get("posts", [])
    return [
        {
            "product_name": p.get("text", "")[:20],
            "keyword": "バイラル投稿",
            "hook_angle": "実績バズパターン",
            "target_pain": "",
            "buzz_factor": f"❤️{p.get('like_count',0)}",
        }
        for p in posts[:5]
    ]
