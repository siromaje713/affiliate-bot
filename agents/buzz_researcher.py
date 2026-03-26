"""バズリサーチエージェント：SNSトレンド・売れ筋からバズネタを収集"""
from pytrends.request import TrendReq
from utils.claude_cli import ask_json

BEAUTY_KEYWORDS = [
    "スキンケア", "美顔器", "日焼け止め", "美容液", "化粧水",
    "クレンジング", "保湿クリーム", "毛穴ケア", "シワ対策", "美白",
    "マスク", "アイクリーム", "化粧下地", "UVケア", "エイジングケア",
]

VIRAL_ANGLES = [
    "コスパ最強", "プチプラ", "デパコス級", "時短", "毛穴レス",
    "翌朝もちもち", "マスク蒸れ対策", "日焼け止め焼けしない",
    "40代でも若見え", "皮膚科医おすすめ",
]


def fetch_rising_keywords() -> list[dict]:
    """Google Trendsから急上昇キーワードを取得する"""
    pytrends = TrendReq(hl="ja-JP", tz=540)
    results = []
    for i in range(0, len(BEAUTY_KEYWORDS), 5):
        chunk = BEAUTY_KEYWORDS[i:i + 5]
        try:
            pytrends.build_payload(chunk, geo="JP", timeframe="now 7-d")
            data = pytrends.interest_over_time()
            if data.empty:
                continue
            for kw in chunk:
                if kw in data.columns:
                    score = int(data[kw].mean())
                    if score > 0:
                        results.append({"keyword": kw, "trend_score": score})
        except Exception as e:
            print(f"[BuzzResearcher] Google Trends エラー: {e}")
    return sorted(results, key=lambda x: x["trend_score"], reverse=True)


def generate_buzz_ideas(trends: list[dict]) -> list[dict]:
    """トレンド×バズ角度からバズりやすい投稿ネタを生成する"""
    top_keywords = [t["keyword"] for t in trends[:5]] or BEAUTY_KEYWORDS[:5]
    prompt = f"""スレッズ(@riko_cosme_lab)でバズりやすい美容アフィリエイト投稿ネタを考えてください。

今週の急上昇キーワード：{', '.join(top_keywords)}
バズりやすい角度：{', '.join(VIRAL_ANGLES)}
アカウント：20〜40代女性・スキンケア・美顔器メイン

以下の条件でJSONを5件返してください（説明不要）：
- バズ角度を必ず1つ使う
- 「最安値」「絶対」「必ず」は使わない
- 楽天で買える商品に絞る

[
  {{
    "product_name": "商品名",
    "keyword": "検索キーワード",
    "hook_angle": "訴求角度",
    "target_pain": "読者の悩み",
    "buzz_factor": "バズりやすい理由"
  }}
]"""
    try:
        return ask_json(prompt)
    except Exception as e:
        print(f"[BuzzResearcher] アイデア生成エラー: {e}")
        return []


def run() -> list[dict]:
    """バズリサーチャー実行。バズネタリストを返す。"""
    print("[BuzzResearcher] 急上昇キーワードを収集中...")
    trends = fetch_rising_keywords()
    print(f"[BuzzResearcher] トップトレンド: {[t['keyword'] for t in trends[:3]]}")

    print("[BuzzResearcher] バズネタ生成中...")
    ideas = generate_buzz_ideas(trends)
    print(f"[BuzzResearcher] {len(ideas)}件のバズネタを生成")
    return ideas
