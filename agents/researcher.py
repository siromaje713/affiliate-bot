"""リサーチャーエージェント：毎回フレッシュな商品アイデア・ローテーション管理"""
import json
from datetime import datetime
from pathlib import Path
from utils.claude_cli import ask_json, MODEL_OPUS

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

LAST_USED_PATH = Path("/tmp/last_used_products.json")


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


def load_last_used() -> list:
    if not LAST_USED_PATH.exists():
        return []
    try:
        return json.loads(LAST_USED_PATH.read_text(encoding="utf-8")).get("products", [])
    except Exception:
        return []


def record_used(product_name: str):
    """使用した商品名を記録（直近10件保持）"""
    used = load_last_used()
    if product_name and product_name not in used:
        used.insert(0, product_name)
    LAST_USED_PATH.write_text(
        json.dumps({"updated_at": datetime.now().isoformat(), "products": used[:10]}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def generate_product_ideas(season_ctx: dict, last_used: list) -> list:
    last_used_str = "、".join(last_used[:5]) if last_used else "なし"
    prompt = f"""あなたは日本のThreads美容アカウントのコンテンツ戦略家です。

【現在の日時・季節コンテキスト】
- 今日：{season_ctx['date_str']}
- 季節：{season_ctx['season']}
- 今月の超ホットなキーワード：{', '.join(season_ctx['hot_keywords'])}

【実績ベンチマーク（siro_beauty7 2.2万フォロワー・riri____.beauty等）のバズ法則】
1. 権威型: 「美容クリニックの友達が〇〇って言ってた」「皮膚科医が推すやつ」で信頼性付与
2. 悩み直撃型: 商品名より先に悩みを言う（「カラコンつけられない人」「乾燥でマスクが貼り付く」）
3. 驚き型: 「これ、名品中の名品」「逆に怖いくらい効いた」「1000円台でこの効果は正気か」
4. コスパ訴求型: 「1回3万のレーザーより1000円台の美容液の方が効いた」「エステ代1回分で一生使える」
5. リスト型: 「肌悩み別おすすめTOP5【保存推奨】」で保存数を稼ぐ

【アカウント情報】
- @riko_cosme_lab（27歳女性キャラ・20〜40代向け）
- 取り扱い可能商品：日焼け止め・美顔器・スキンケア・美容液・化粧水・ヘアケア

【最近使った商品（必ず除外・重複厳禁）】
{last_used_str}

今の季節に最も刺さる商品アイデアを8件生成してください。
・上記の最近使った商品は絶対に出さないこと
・各アイデアは上記5つのバズ法則のどれかを活かすこと
・季節感ゼロ・時期外れのアイデアは絶対NG

JSON配列のみで返してください：
[
  {{
    "product_name": "具体的な商品名",
    "keyword": "メインキーワード",
    "hook_angle": "上記バズ法則のどれかを使った具体的な訴求",
    "target_pain": "読者の具体的な悩み（商品名より先に伝えたい悩み）",
    "seasonal_hook": "季節先取り系フレーズ",
    "urgency": "今すぐ感"
  }}
]"""
    try:
        return ask_json(prompt, model=MODEL_OPUS)
    except Exception as e:
        print(f"[Researcher] アイデア生成エラー: {e}")
        return []


def run():
    season_ctx = get_current_season_context()
    print(f"[Researcher] 季節コンテキスト: {season_ctx['season']}")
    last_used = load_last_used()
    if last_used:
        print(f"[Researcher] 除外商品（最近使用）: {', '.join(last_used[:3])}")
    print("[Researcher] 商品アイデア生成中（毎回フレッシュ・重複防止）...")
    ideas = generate_product_ideas(season_ctx, last_used)
    print(f"[Researcher] {len(ideas)}件のアイデアを生成")
    return ideas
