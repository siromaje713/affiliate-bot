"""リサーチャーエージェント：美容トレンド収集"""
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from utils.claude_cli import ask_json

BEAUTY_KEYWORDS = [
    "スキンケア", "美顔器", "日焼け止め", "美容液", "化粧水",
]

CACHE_PATH = Path(__file__).parent.parent / "data" / "trends_cache.json"
CACHE_TTL_HOURS = 12
TRENDS_TIMEOUT = 15


def _fetch_trends_in_thread(keywords, container):
    """別スレッドでpytrendsを実行"""
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="ja-JP", tz=540, timeout=(3, 8))
        pytrends.build_payload(keywords[:5], geo="JP", timeframe="now 7-d")
        data = pytrends.interest_over_time()
        results = []
        if not data.empty:
            for kw in keywords[:5]:
                if kw in data.columns:
                    results.append({"keyword": kw, "trend_score": int(data[kw].mean())})
        container.append(sorted(results, key=lambda x: x["trend_score"], reverse=True))
    except Exception as e:
        print(f"[Researcher] Google Trends エラー: {e}")
        container.append([])


def fetch_google_trends(keywords):
    """Google Trendsをタイムアウト付きで取得。失敗時は空リストを返す"""
    container = []
    t = threading.Thread(target=_fetch_trends_in_thread, args=(keywords, container), daemon=True)
    t.start()
    t.join(timeout=TRENDS_TIMEOUT)
    if t.is_alive():
        print(f"[Researcher] Google Trends タイムアウト({TRENDS_TIMEOUT}秒) → フォールバック")
        return []
    return container[0] if container else []


def _is_cache_valid():
    if not CACHE_PATH.exists():
        return False
    data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
    return datetime.now() - cached_at < timedelta(hours=CACHE_TTL_HOURS)


def generate_product_ideas(trends):
    """トレンドキーワードから商品アイデアを生成する"""
    top_keywords = [t["keyword"] for t in trends[:5]] or BEAUTY_KEYWORDS[:5]
    prompt = f"""美容系アフィリエイトの投稿ネタを考えてください。
今週のトレンドキーワード：{', '.join(top_keywords)}
アカウント：@riko_cosme_lab（20〜40代女性向け・スキンケア・美顔器）

JSON配列で5件返してください（説明不要）：
[
  {{
    "product_name": "商品名",
    "keyword": "関連キーワード",
    "hook_angle": "訴求角度（例：コスパ・時短・プチプラ）",
    "target_pain": "読者の悩み"
  }}
]"""
    try:
        return ask_json(prompt)
    except Exception as e:
        print(f"[Researcher] アイデア生成エラー: {e}")
        return []


def run():
    """リサーチャー実行。商品アイデアリストを返す。"""
    # 12時間以内のキャッシュがあれば再利用
    if _is_cache_valid():
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        trends = data.get("trends", [])
        print(f"[Researcher] トレンドキャッシュ使用: {[t['keyword'] for t in trends[:3]]}")
    else:
        print("[Researcher] Google Trendsからトレンド収集中...")
        trends = fetch_google_trends(BEAUTY_KEYWORDS)
        print(f"[Researcher] トップトレンド: {[t['keyword'] for t in trends[:3]]}")
        CACHE_PATH.parent.mkdir(exist_ok=True)
        CACHE_PATH.write_text(
            json.dumps({"cached_at": datetime.now().isoformat(), "trends": trends},
                       ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    print("[Researcher] 商品アイデア生成中...")
    ideas = generate_product_ideas(trends)
    print(f"[Researcher] {len(ideas)}件のアイデアを生成")
    return ideas
