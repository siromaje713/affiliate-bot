"""ライターエージェント：Threadsバイラル投稿から動的抽出したパターンでコンテンツ生成"""
import json
from datetime import datetime
from pathlib import Path
from utils.claude_cli import ask_json
from utils.quality_scorer import score_post, similarity_score

HISTORY_PATH = Path(__file__).parent.parent / "data" / "post_history.json"
BUZZ_PATTERNS_PATH = Path(__file__).parent.parent / "data" / "buzz_patterns.json"
MAX_HISTORY = 100
SIMILARITY_THRESHOLD = 0.6


def _load_buzz_patterns() -> list:
    """data/buzz_patterns.jsonから動的パターンをロードする"""
    if BUZZ_PATTERNS_PATH.exists():
        try:
            data = json.loads(BUZZ_PATTERNS_PATH.read_text(encoding="utf-8"))
            patterns = data.get("patterns", [])
            if patterns:
                return patterns
        except Exception:
            pass
    return []


def _get_or_generate_patterns() -> list:
    """パターンをロード、なければbuzz_researcherで生成する"""
    patterns = _load_buzz_patterns()
    if patterns:
        return patterns
    try:
        from agents import buzz_researcher
        print("[Writer] buzz_patterns.jsonが空のため動的生成します...")
        context = buzz_researcher.get_buzz_context()
        return context.get("patterns", [])
    except Exception as e:
        print(f"[Writer] パターン動的生成失敗: {e}")
        return []


def get_season_context():
    now = datetime.now()
    month = now.month
    season_map = {
        (3, 4, 5): ("春", "桜・新生活・花粉・紫外線始まり"),
        (6, 7, 8): ("夏", "UV・汗・湿気・海・露出・夏バテ肌"),
        (9, 10, 11): ("秋", "乾燥・日焼けダメージケア・衣替え・秋冬準備"),
        (12, 1, 2): ("冬", "極乾燥・保湿・赤み・マスク肌・年末年始"),
    }
    next_map = {"春": "夏", "夏": "秋", "秋": "冬", "冬": "春"}

    season = "春"
    season_keywords = ""
    for months, (s, kw) in season_map.items():
        if month in months:
            season = s
            season_keywords = kw
            break

    return {
        "month": month,
        "year": now.year,
        "season": season,
        "next_season": next_map[season],
        "season_keywords": season_keywords,
        "date": now.strftime("%Y年%m月"),
    }


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


def get_pattern_examples() -> str:
    """動的バズパターン + 実績バズ投稿をプロンプト用文字列で返す"""
    from pathlib import Path as _Path

    # 動的パターン（buzz_researcher由来）
    dynamic_patterns = _get_or_generate_patterns()
    pattern_section = ""
    if dynamic_patterns:
        lines = []
        for p in dynamic_patterns[:8]:
            lines.append(
                f"・【{p.get('name','')}】冒頭: {p.get('hook_structure','')} / 語尾: {p.get('ending_pattern','')} / 例: {p.get('example','')[:50]}"
            )
        pattern_section = "【Threadsバイラル投稿から動的抽出したパターン（最優先）】\n" + "\n".join(lines) + "\n"

    # 自分の実績バズ投稿
    _wp_path = _Path(__file__).parent / "cache" / "winning_patterns.json"
    winning_section = ""
    if _wp_path.exists():
        try:
            import json as _json
            wps = _json.loads(_wp_path.read_text(encoding="utf-8"))
            if wps:
                winning_section = "\n【実際にThreadsでバズった投稿（いいね数順・最重要参考）】\n"
                for i, p in enumerate(wps[:5], 1):
                    winning_section += f"{i}. ❤️{p.get('like_count',0)} 「{p.get('text','')[:60]}」\n"
                winning_section += "↑これらのパターン・フック・言葉選びを最優先で参考にしてください。\n"
        except Exception:
            pass

    return (
        "あなたはSNSバイラル構造の専門家です。\n"
        f"{pattern_section}"
        "上記パターンを優先しつつ、あなたが知るあらゆるバズ構造・心理技法も自由に駆使してください。\n\n"
        "【参考：バズを生む心理トリガー（補助）】\n"
        "認知的不協和 / FOMO / 社会的証明 / 権威×秘密暴露 / 共感・あるある\n"
        "後悔回避 / 好奇心ギャップ / 逆説・常識覆し / 数字の具体性 / ビフォーアフター\n"
        f"{winning_section}"
    )
def generate_patterns(
    product: dict,
    hook=None,
    win_patterns=None,
    competitor_posts=None,
    post_type: str = "link",
) -> list[str]:
    hook_instruction = (
        f"冒頭1行は必ずこのフックで始めること：「{hook}」" if hook else ""
    )

    win_section = ""
    if win_patterns:
        examples = "\n".join(
            [f"  ・{p['text'][:60]}（❤️{p['like_count']}）" for p in win_patterns[:2]]
        )
        win_section = f"\n自分の高反応投稿（参考）：\n{examples}\n"

    competitor_section = ""
    if competitor_posts:
        if isinstance(competitor_posts[0], dict):
            tops = sorted(competitor_posts, key=lambda x: x.get("engagement_score", 0), reverse=True)[:3]
            examples = "\n".join([
                f"  ・{p.get('text','')[:60]}（❤️{p.get('like_count',0)} 文字{p.get('char_count',0)} 画像{'あり' if p.get('has_image') else 'なし'}）"
                for p in tops
            ])
        else:
            examples = "\n".join([f"  ・{t[:60]}" for t in competitor_posts[:3]])
        competitor_section = f"\n競合バズ投稿（構造を参考に）：\n{examples}\n"

    ctx = get_season_context()
    seasonal_hook = product.get("seasonal_hook", "")
    urgency = product.get("urgency", "")
    hook_angle = product.get("hook_angle", "")

    # 毎回ランダムに6種のバズパターンを選択（マンネリ防止）
    pattern_examples = get_pattern_examples()

    seasonal_info = f"""
【今の季節・時事コンテキスト】
- 現在：{ctx['date']}・{ctx['season']}（次は{ctx['next_season']}）
- キーワード：{ctx['season_keywords']}
- 商品の季節フレーズ：{seasonal_hook}
- 今すぐ感：{urgency}
- 訴求角度：{hook_angle}
"""

    buzz_guide = f"""
【今回使うバズパターン候補（ランダム選択・毎回変わる）】
{pattern_examples}

【絶対NGパターン】
❌ 「〇〇がおすすめです」→広告感
❌ 「〇〇を使ってみました」→レポート感
❌ 「良かったです」→薄い
❌ 冒頭が商品名→販促感
❌ 季節感ゼロ→刺さらない
❌ 結論から始まる→読まれない

【バズる構造の法則】
✅ 冒頭で感情を揺さぶる（驚き/共感/FOMO/秘密）
✅ 途中で「これ自分のことだ」と思わせる
✅ 最後にコメントしたくなる余白を残す
✅ 27歳女性の等身大の言葉遣い
✅ 季節・時事・数字を必ず入れる
"""

    if post_type == "buzz":
        prompt = f"""スレッズでバズる会話誘発・共感型投稿を6パターン生成してください。

商品（直接宣伝しない）：
- 商品名：{product['product_name']}
- 読者の悩み：{product['target_pain']}
{seasonal_info}{buzz_guide}{win_section}{competitor_section}

ルール：
- 109文字以内（必須）
- {hook_instruction if hook_instruction else '上記バズパターンから毎回違う種類を選んで使う（同じパターン連用NG）'}
- 絵文字1〜2個
- URLや商品リンク誘導は絶対禁止
- コメント誘発必須（「みんなは？」「教えて」「どう思う？」等）
- 広告感ゼロ・リアルな体験談スタイル

6パターンをJSON配列のみで返してください（説明不要）：
["投稿文1", "投稿文2", ...]"""

    else:
        prompt = f"""楽天アフィリエイト向けスレッズ投稿を6パターン生成してください。

商品情報：
- 商品名：{product['product_name']}
- 訴求角度：{hook_angle}
- 読者の悩み：{product['target_pain']}
{seasonal_info}{buzz_guide}{win_section}{competitor_section}

ルール：
- 109文字以内（必須）
- {hook_instruction if hook_instruction else '上記バズパターンから毎回違う種類を選ぶ（悲報・朗報に偏らない）'}
- 絵文字1〜2個
- URLや「楽天リンク」「リンク」「こちら」等の誘導は絶対禁止
- 27歳女性の体験談スタイル
- 季節感・今すぐ感を必ず入れる
- 商品名は本文中に必ず入れる
- 広告感ゼロ
- 6パターンは全て異なるバズパターンカテゴリを使うこと

6パターンをJSON配列のみで返してください（説明不要）：
["投稿文1", "投稿文2", ...]"""

    try:
        return ask_json(prompt)
    except Exception as e:
        print(f"[Writer] パターン生成エラー: {e}")
        return []


def run(
    product: dict,
    hook=None,
    win_patterns=None,
    competitor_posts=None,
    post_type: str = "link",
) -> dict:
    print(f"[Writer] 「{product['product_name']}」{post_type}型 6パターン生成中...")
    patterns = generate_patterns(
        product,
        hook,
        win_patterns=win_patterns,
        competitor_posts=competitor_posts,
        post_type=post_type,
    )
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
        save_to_history(best["text"])
    else:
        print("[Writer] 品質基準を満たすパターンなし")

    return best
