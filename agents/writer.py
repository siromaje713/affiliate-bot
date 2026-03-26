"""ライターエージェント：季節バズ構造・悲報朗報パターン強制版"""
import json
from datetime import datetime
from pathlib import Path
from utils.claude_cli import ask_json
from utils.quality_scorer import score_post, similarity_score

HISTORY_PATH = Path(__file__).parent.parent / "data" / "post_history.json"
MAX_HISTORY = 100
SIMILARITY_THRESHOLD = 0.6

# バズる投稿の構造パターン（あなたの例を直接埋め込み）
BUZZ_HOOK_PATTERNS = [
    "悲報、{target}してる人、実は{shocking_fact}だった",
    "朗報、{product}を使い始めて{period}で{result}した話",
    "{year}年の{keyword}は{month}からが本番って知ってた？",
    "去年{action}して大成功したから今年も絶対やる",
    "{number}年間デパコス買ってた私が{pricepoint}のこれに変えた理由",
    "露出の多い{season}、{benefit}の秘訣は{timing}からの肌ケア",
    "美白を目指す女性、実は{shocking_fact}",
    "{period}で{result}。もっと早く知りたかった",
]


def get_season_context():
    now = datetime.now()
    month = now.month
    season_map = {
        (3, 4, 5): "春",
        (6, 7, 8): "夏",
        (9, 10, 11): "秋",
        (12, 1, 2): "冬",
    }
    season = "春"
    for months, s in season_map.items():
        if month in months:
            season = s
            break
    return {"month": month, "year": now.year, "season": season,
            "date": now.strftime("%Y年%m月")}


def load_history() -> list[str]:
    if not HISTORY_PATH.exists():
        return []
    return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))


def save_to_history(text: str):
    history = load_history()
    history.insert(0, text)
    HISTORY_PATH.write_text(
        json.dumps(history[:MAX_HISTORY], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def generate_patterns(product: dict, hook=None, win_patterns=None,
                      competitor_posts=None, post_type: str = "link") -> list[str]:
    hook_instruction = f"冒頭1行は必ずこのフックで始めること：「{hook}」" if hook else ""
    win_section = ""
    if win_patterns:
        examples = "\n".join([f"  ・{p['text'][:60]}（❤️{p['like_count']}）"
                               for p in win_patterns[:2]])
        win_section = f"\n自分の高反応投稿（参考）：\n{examples}\n"
    competitor_section = ""
    if competitor_posts:
        examples = "\n".join([f"  ・{t[:60]}" for t in competitor_posts[:3]])
        competitor_section = f"\n競合の人気投稿（参考のみ）：\n{examples}\n"

    ctx = get_season_context()
    seasonal_hook = product.get("seasonal_hook", "")
    urgency = product.get("urgency", "")
    hook_angle = product.get("hook_angle", "")

    seasonal_info = f"""
【今の季節・時事コンテキスト】
- 現在：{ctx['date']}・{ctx['season']}
- 季節フレーズ（必ず活用）：{seasonal_hook}
- 今すぐ感：{urgency}
- 訴求角度：{hook_angle}
"""

    buzz_examples = """
【バズる投稿パターン（必ずこの構造を使う）】
✅ 悲報系：「悲報、美白を目指す女性、実は2026年の紫外線は4月からだった」
✅ 先取り系：「2026年夏先取り、去年使って大成功した日焼け止めをお得に」
✅ 朗報系：「露出の多い夏、美白の秘訣は4月からの肌ケア」
✅ 数字系：「3日で毛穴が半分になった。もっと早く知りたかった」
✅ 体験談：「5年間デパコス買ってた私が2000円以下に変えた理由」
✅ 比較系：「みんな日焼け止め何使ってる？去年これに変えたら差が出すぎた」
❌ NGパターン：「〇〇がおすすめです」「〇〇を使ってみました」（広告感が出るのでNG）
"""

    if post_type == "buzz":
        prompt = f"""スレッズでバズる会話誘発・共感型投稿を6パターン生成してください。

商品（直接宣伝しない）：
- 商品名：{product['product_name']}
- 読者の悩み：{product['target_pain']}
{seasonal_info}{buzz_examples}{win_section}{competitor_section}
ルール：
- 109文字以内（必須・超えたらNG）
- {hook_instruction if hook_instruction else "冒頭は上記バズパターンのどれかで必ず始める"}
- 絵文字は1〜2個以内
- URLや商品リンク誘導は絶対禁止
- 「みんなはどうしてる？」「試した人いる？」系でコメント誘発必須
- 広告感ゼロ・リアルな体験談スタイル
- 27歳女性の本音トーン
- 季節感ゼロの投稿は絶対NG

6パターンをJSON配列のみで返してください（説明不要）：
["投稿文1", "投稿文2", ...]"""
    else:
        prompt = f"""楽天アフィリエイト向けスレッズ投稿を6パターン生成してください。

商品情報：
- 商品名：{product['product_name']}
- 訴求角度：{hook_angle}
- 読者の悩み：{product['target_pain']}
{seasonal_info}{buzz_examples}{win_section}{competitor_section}
ルール：
- 109文字以内（必須・超えたらNG）
- {hook_instruction if hook_instruction else "冒頭は上記バズパターンのどれかで必ず始める"}
- 絵文字は1〜2個以内
- URLや「楽天リンク」「リンク」「こちら」等の誘導は絶対禁止
- 27歳女性の体験談スタイル
- 季節感・今すぐ感を必ず入れる
- 商品名は必ず本文中に入れる（読者がリプライで商品名検索できるように）
- 広告感ゼロ

6パターンをJSON配列のみで返してください（説明不要）：
["投稿文1", "投稿文2", ...]"""

    try:
        return ask_json(prompt)
    except Exception as e:
        print(f"[Writer] パターン生成エラー: {e}")
        return []


def run(product: dict, hook=None, win_patterns=None,
        competitor_posts=None, post_type: str = "link") -> dict:
    print(f"[Writer] 「{product['product_name']}」{post_type}型 6パターン生成中...")
    patterns = generate_patterns(product, hook, win_patterns=win_patterns,
                                 competitor_posts=competitor_posts, post_type=post_type)
    print(f"[Writer] {len(patterns)}パターン生成完了")

    history = load_history()
    best = None
    for i, text in enumerate(patterns):
        if len(text) > 109:
            print(f"[Writer] パターン{i+1}: 文字数超過({len(text)}文字) → スキップ")
            continue
        sim = similarity_score(text, history)
        if sim >= SIMILARITY_THRESHOLD:
            print(f"[Writer] パターン{i+1}: 類似度{sim:.2f} → スキップ")
            continue
        result = score_post(text)
        score = result.get("score", 0)
        print(f"[Writer] パターン{i+1}: スコア{score} - {result.get('reason', '')}")
        if result["pass"]:
            if best is None or score > best["score"]:
                best = {"text": text, "score": score,
                        "product": product, "post_type": post_type}

    if best:
        print(f"[Writer] 最良パターン: スコア{best['score']}")
        save_to_history(best["text"])
    else:
        print("[Writer] 品質基準を満たすパターンなし")
    return best悲報朗報バズパターン強制・季節フック・パターン生成
