"""ライターエージェント：15パターン生成・品質フィルター・類似度チェック"""
import json
from pathlib import Path
from utils.claude_cli import ask_json
from utils.quality_scorer import score_post, similarity_score

HISTORY_PATH = Path(__file__).parent.parent / "data" / "post_history.json"
MAX_HISTORY = 100
SIMILARITY_THRESHOLD = 0.6


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


def generate_patterns(product: dict, hook=None, win_patterns=None, competitor_posts=None, post_type: str = "link") -> list[str]:
    """5パターンの投稿文を生成する"""
    hook_instruction = f"冒頭1行は必ずこのフックで始めること：「{hook}」" if hook else "冒頭1行は疑問形か数字で始める"

    win_section = ""
    if win_patterns:
        examples = "\n".join([f"  ・{p['text'][:60]}（❤️{p['like_count']}）" for p in win_patterns[:2]])
        win_section = f"\n自分の高反応投稿（参考にしてトーンを合わせる）：\n{examples}\n"

    competitor_section = ""
    if competitor_posts:
        examples = "\n".join([f"  ・{t[:60]}" for t in competitor_posts[:3]])
        competitor_section = f"\n競合の人気投稿テキスト（参考のみ・パクリ禁止）：\n{examples}\n"

    if post_type == "buzz":
        prompt = f"""スレッズ向けの会話誘発・共感型投稿を5パターン生成してください。

関連商品（直接宣伝しない・自然に話題に乗せる程度でOK）：
- 商品名：{product['product_name']}
- 読者の悩み：{product['target_pain']}
{win_section}{competitor_section}ルール：
- 109文字以内（必須）
- {hook_instruction}
- 絵文字は2個以内
- URLや商品リンク誘導は一切入れない（絶対禁止）
- 「あなたはどう思う？」「実際やってみたら〜だった」系の問いかけ・体験談スタイル
- 読者がコメントしたくなる終わり方（例：「みんなはどうしてる？」「試した人いる？」）
- 広告・宣伝感ゼロ・リアルな日常会話風
- アカウントトーン：親しみやすい・20〜40代女性向け

5パターンをJSON配列のみで返してください（説明不要）：
["投稿文1", "投稿文2", ...]"""
    else:
        prompt = f"""楽天アフィリエイト向けスレッズ投稿を5パターン生成してください。

商品情報：
- 商品名：{product['product_name']}
- 訴求角度：{product['hook_angle']}
- 読者の悩み：{product['target_pain']}
{win_section}{competitor_section}ルール：
- 109文字以内（必須）
- {hook_instruction}
- 絵文字は2個以内
- URLや「楽天リンク」「リンク」「こちら」等のリンク誘導は一切入れない（絶対禁止）
- 広告臭を出さない・体験談風
- アカウントトーン：親しみやすい・20〜40代女性向け

5パターンをJSON配列のみで返してください（説明不要）：
["投稿文1", "投稿文2", ...]"""

    try:
        return ask_json(prompt)
    except Exception as e:
        print(f"[Writer] パターン生成エラー: {e}")
        return []


def run(product: dict, hook=None, win_patterns=None, competitor_posts=None, post_type: str = "link") -> dict:
    """
    ライター実行。品質・類似度フィルターを通過した最良の投稿文を返す。
    返り値: {"text": "...", "score": 8.2, "product": {...}, "post_type": "buzz"|"link"} or None
    """
    print(f"[Writer] 「{product['product_name']}」の投稿文を5パターン生成中... (タイプ: {post_type})")
    patterns = generate_patterns(product, hook, win_patterns=win_patterns, competitor_posts=competitor_posts, post_type=post_type)
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
                best = {"text": text, "score": score, "product": product, "post_type": post_type}

    if best:
        print(f"[Writer] 最良パターン決定: スコア{best['score']}")
    else:
        print("[Writer] 品質基準を満たすパターンなし")
    return best
