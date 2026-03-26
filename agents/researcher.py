"""リサーチャーエージェント：季節・時事・ベンチマーク対応版"""
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from utils.claude_cli import ask_json

BENCHMARK_ACCOUNTS = [
    "cosme_tokyo_lab", "skincarebymai", "bijin_recipe",
    "hada_research", "cosme_junkie_jp", "uv_care_navi",
    "korean_cosme_fan", "petit_pla_cosme", "kireini_naru_hi", "hifucare_lab"
]

SEASONAL_KEYWORDS = {
    1:  ["乾燥対策", "保湿", "冬肌ケア", "ヒアルロン酸", "バリア機能"],
    2:  ["花粉対策", "敏感肌", "乾燥", "美白準備", "インナーケア"],
    3:  ["UV対策開始", "春肌ケア", "毛穴ケア", "日焼け止め", "美白"],
    4:  ["紫外線対策", "日焼け止め", "毛穴", "春コスメ", "新生活スキンケア"],
    5:  ["UV本番", "日焼け止め", "皮脂ケア", "スキンケア見直し", "美顔器"],
    6:  ["梅雨肌ケア", "ベタつき", "皮脂コントロール", "美白", "日焼け止め"],
    7:  ["夏肌ケア", "美白", "UV", "汗ケア", "毛穴"],
    8:  ["日焼けアフターケア", "美白", "保湿", "夏肌ダメージ", "美顔器"],
    9:  ["秋肌ケア", "乾燥始まり", "美白仕上げ", "毛穴ケア", "スキンケア切替"],
    10: ["乾燥対策", "保湿", "角質ケア", "美容液", "美顔器"],
    11: ["乾燥本番", "保湿", "ヒアルロン酸", "美容液", "スキンケア強化"],
    12: ["年末美容", "保湿", "乾燥対策", "来年美肌準備", "美顔器"],
}

CACHE_PATH = Path(__file__).parent.parent / "data" / "trends_cache.json"
CACHE_TTL_HOURS = 6
TRENDS_TIMEOUT = 15


def get_current_season_context():
    now = datetime.now()
    month = now.month
    keywords = SEASONAL_KEYWORDS.get(month, ["スキンケア", "美容"])
    season_map = {
        (3, 4, 5): "春（UV対策・新生活・毛穴ケアが超ホット）",
        (6, 7, 8): "夏（日焼け・汗・美白が最優先）",
        (9, 10, 11): "秋（乾燥ケア・美白仕上げ・スキンケア切替）",
        (12, 1, 2): "冬（保湿・バリア機能・インナーケア）",
    }
    season = "不明"
    for months, label in season_map.items():
        if month in months:
            season = label
            break
    return {
        "month": month,
        "year": now.year,
        "season": season,
        "hot_keywords": keywords,
        "date_str": now.strftime("%Y年%m月%d日"),
    }


def _fetch_trends_in_thread(keywords, container):
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
    container = []
    t = threading.Thread(target=_fetch_trends_in_thread, args=(keywords, container), daemon=True)
    t.start()
    t.join(timeout=TRENDS_TIMEOUT)
    if t.is_alive():
        print(f"[Researcher] Google Trends タイムアウト → フォールバック")
        return []
    return container[0] if container else []


def _is_cache_valid():
    if not CACHE_PATH.exists():
        return False
    data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
    return datetime.now() - cached_at < timedelta(hours=CACHE_TTL_HOURS)


def generate_product_ideas(trends, season_ctx):
    top_keywords = [t["keyword"] for t in trends[:5]] if trends else season_ctx["hot_keywords"]
    benchmark_str = "、".join(BENCHMARK_ACCOUNTS[:5])
    prompt = f"""あなたは日本のThreads美容アカウントのコンテンツ戦略家です。

【現在の日時・季節コンテキスト】
- 今日：{season_ctx['date_str']}
- 季節：{season_ctx['season']}
- 今月の超ホットなキーワード：{', '.join(season_ctx['hot_keywords'])}
- Googleトレンド上位：{', '.join(top_keywords)}

【ベンチマーク視点】
伸びている美容Threadsアカウント（{benchmark_str}等）の共通パターン：
- 季節の先取り情報（「もう始まってる」「今からやらないと手遅れ」系）
- 数字で驚かせる（「4月から紫外線量30%増」「3日で変わった」）
- 悲報・朗報系フック（「悲報、〇〇してる人は損してる」「神コスメ発見」）
- 体験談リアル系（「実際使ったら〜」「買って後悔した/しなかった」）

【アカウント情報】
- @riko_cosme_lab（27歳女性キャラ・20〜40代向け・楽天アフィリエイト）
- 取り扱い可能商品：日焼け止め・美顔器・スキンケア・美容液・化粧水

今の季節に最も刺さる商品アイデアを8件生成してください。
季節感ゼロ・時期外れのアイデアは絶対NG。

JSON配列のみで返してください：
[
  {{
    "product_name": "具体的な商品名",
    "keyword": "メインキーワード",
    "hook_angle": "今の季節に刺さる具体的な訴求",
    "target_pain": "読者の具体的な悩み",
    "seasonal_hook": "季節先取り系フレーズ",
    "urgency": "今すぐ感"
  }}
]"""
    try:
        return ask_json(prompt)
    except Exception as e:
        print(f"[Researcher] アイデア生成エラー: {e}")
        return []


def run():
    season_ctx = get_current_season_context()
    print(f"[Researcher] 季節コンテキスト: {season_ctx['season']}")
    if _is_cache_valid():
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        trends = data.get("trends", [])
        print(f"[Researcher] トレンドキャッシュ使用")
    else:
        print("[Researcher] Google Trendsからトレンド収集中...")
        trends = fetch_google_trends(season_ctx["hot_keywords"])
        CACHE_PATH.parent.mkdir(exist_ok=True)
        CACHE_PATH.write_text(
            json.dumps({"cached_at": datetime.now().isoformat(), "trends": trends}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    print("[Researcher] 商品アイデア生成中...")
    ideas = generate_product_ideas(trends, season_ctx)
    print(f"[Researcher] {len(ideas)}件のアイデアを生成")
    return ideas
