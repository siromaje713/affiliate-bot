"""ライターエージェント：SNSバイラル心理学に基づく20種バズパターン完全実装版

バズパターンの分類（SNS心理学・バイラル研究ベース）：
1. 感情揺さぶり系: 悲報/朗報/衝撃/怒り/安堵
2. 認知ギャップ系: 期待裏切り/逆説/常識覆し
3. 権威×秘密系: 専門家暴露/業界の裏側/禁断情報
4. 時限・FOMO系: 今だけ/季節限定/知らないと損
5. 社会的証明系: みんなやってる/売れすぎ/口コミ爆発
6. 自己投影系: あるある/共感/自分事化
7. 変化・成長系: 時系列変化/ビフォーアフター/続けた結果
8. 疑問提起系: なぜ?/実は?/知ってた?
9. 後悔回避系: 去年知りたかった/やらなきゃよかった/もっと早く
10. 参加誘導系: 教えて/みんなは?/どっちが好き?
"""
import json
import random
from datetime import datetime
from pathlib import Path
from utils.claude_cli import ask_json
from utils.quality_scorer import score_post, similarity_score

HISTORY_PATH = Path(__file__).parent.parent / "data" / "post_history.json"
MAX_HISTORY = 100
SIMILARITY_THRESHOLD = 0.6

# =====================================================
# 20種バズパターン辞書（SNSバイラル心理学ベース）
# =====================================================
BUZZ_PATTERNS = {

    # ── 感情揺さぶり系 ──────────────────────────────
    "悲報系": {
        "desc": "ネガティブ驚き→共感→解決策",
        "templates": [
            "悲報、{target}してる女性、実は{shocking_fact}だった",
            "悲報、{action}してた私、{period}で{result}になってた",
            "悲報、{product_type}にお金かけてたの、全部意味なかった話",
        ],
        "example": "悲報、美白を目指す女性、実は2026年の紫外線は4月からだった",
    },
    "朗報系": {
        "desc": "ポジティブ発見→期待感→行動促進",
        "templates": [
            "朗報、{problem}で悩んでた私が{period}で{result}した話",
            "朗報、{product}って{price_point}で買えたんだ",
            "朗報、{action}するだけで{benefit}になれるって最高すぎ",
        ],
        "example": "朗報、毎日5分で肌が変わるって、もっと早く知りたかった",
    },
    "衝撃暴露系": {
        "desc": "常識を壊す情報→拡散欲求",
        "templates": [
            "{authority}が教えてくれたこと、{shocking_fact}って本当だった",
            "皮膚科で言われた衝撃の一言、{common_belief}は嘘だったらしい",
            "美容部員に聞いたら、{product_type}は{right_way}が正解って言われた",
        ],
        "example": "皮膚科で言われた衝撃の一言、保湿は量より順番が全てって",
    },

    # ── 認知ギャップ系 ──────────────────────────────
    "期待裏切り系": {
        "desc": "予想と真逆の結果→驚き→共有欲",
        "templates": [
            "{expensive}より{cheap}の方が{result}だった件",
            "{popular_action}より{unexpected_action}の方が{benefit}だった",
            "{period}続けて気づいた、{common_belief}って全然関係なかった",
        ],
        "example": "高い美容液より1000円台のこっちの方が効いた件、正直に話す",
    },
    "逆説系": {
        "desc": "真逆の論理→好奇心→読了率UP",
        "templates": [
            "{benefit}したいなら{unexpected_way}が一番って気づいた",
            "{product_type}をやめたら{benefit}になった話、これ本当",
            "頑張れば頑張るほど{problem}になるって知ってた？",
        ],
        "example": "スキンケアをシンプルにしたら肌荒れが消えた話、これ本当",
    },
    "常識覆し系": {
        "desc": "固定観念の破壊→驚き→シェア",
        "templates": [
            "{year}年の{category}、もう{old_way}の時代じゃなかった",
            "みんながやってる{common_action}、実は{negative_fact}だったらしい",
            "{common_belief}って嘘だって気づいてから{benefit}になった",
        ],
        "example": "2026年の日焼け止め、もうウォータープルーフだけじゃ足りなかった",
    },

    # ── 権威×秘密系 ──────────────────────────────
    "専門家秘密系": {
        "desc": "権威からの裏情報→信頼性×希少性",
        "templates": [
            "{expert}に聞いたら{shocking_fact}って教えてもらった",
            "某{expert}がこっそり教えてくれた{product_type}の選び方",
            "{brand}の中の人が言ってた{secret_tip}、みんな知ってた？",
        ],
        "example": "某皮膚科の先生がこっそり教えてくれた化粧水の選び方、みんな知ってた？",
    },
    "禁断本音系": {
        "desc": "言えなかった本音の解禁→親近感爆発",
        "templates": [
            "ずっと言えなかったけど{popular_product}は正直{honest_opinion}だった",
            "美容系インフルエンサーをやめて気づいた{honest_truth}",
            "{period}使い続けてやっと言える、{product}の{honest_review}",
        ],
        "example": "ずっと言えなかったけど某有名美容液は正直コスパ最悪だった",
    },

    # ── 時限・FOMO系 ──────────────────────────────
    "今すぐやれ系": {
        "desc": "緊急性→即行動→FOMO",
        "templates": [
            "{month}中にやっておかないと{negative_consequence}になる話",
            "{season}前にこれをやってない人、まじで後悔する",
            "今すぐ{action}しないと{period}後に絶対後悔する",
        ],
        "example": "4月中に日焼け止め変えてない人、まじで5月後悔する",
    },
    "季節先取り系": {
        "desc": "季節変化への先手→賢さアピール",
        "templates": [
            "{next_season}の肌を決めるのは{current_season}の{action}",
            "去年{season_action}して大成功したから今年も絶対やる",
            "{year}年{season}先取り、今から{action}しておくべき理由",
        ],
        "example": "夏の肌を決めるのは春の紫外線対策、去年これで差がついた",
    },

    # ── 社会的証明系 ──────────────────────────────
    "口コミ爆発系": {
        "desc": "みんなが使ってる→乗り遅れ感",
        "templates": [
            "これ{period}で{number}人に勧めた、それくらい{benefit}だった",
            "友達に話したら全員{reaction}してた{product}の話",
            "{number}人が買ってるって聞いて試したら本当に{result}だった",
        ],
        "example": "これ1ヶ月で5人に勧めた、それくらい肌が変わったから",
    },
    "比較選択系": {
        "desc": "比較による優位性の実証",
        "templates": [
            "売上1位の{category}より断然こっちが{benefit}だった",
            "{expensive_brand}と{cheap_brand}を比較したら{unexpected_result}だった",
            "みんなが買ってる{popular}より{alternative}の方が{benefit}",
        ],
        "example": "売上1位の化粧水より断然こっちが浸透した話、価格差3倍なのに",
    },

    # ── 自己投影・共感系 ──────────────────────────────
    "あるある系": {
        "desc": "強烈な共感→いいね/RT衝動",
        "templates": [
            "{problem}で悩んでる人って私だけじゃないよね？",
            "{situation}のとき{reaction}になるの、あるあるすぎない？",
            "{age}代で{concern}気になり始めた人、正直に手あげて",
        ],
        "example": "27歳で毛穴が気になり始めた人、正直に手あげて",
    },
    "独白系": {
        "desc": "日記的な本音→フォロワーとの距離縮小",
        "templates": [
            "昨日{action}してみたんだけど、{unexpected_result}すぎて笑った",
            "最近{product}が手放せなくて、{reason}から",
            "今日{situation}で気づいたこと、{insight}",
        ],
        "example": "昨日新しい美顔器試してみたんだけど、翌朝の肌がやばすぎて笑った",
    },

    # ── 変化・成長系 ──────────────────────────────
    "ビフォーアフター系": {
        "desc": "時系列の変化→結果への期待",
        "templates": [
            "{period}前の私に教えてあげたい{lesson}",
            "{product}を始めて{period}、{change}が起きた話",
            "1ヶ月・3ヶ月・半年後の肌が全然違う{product}の話",
        ],
        "example": "美顔器を始めて3ヶ月、輪郭が変わった気がするのは気のせいじゃなかった",
    },
    "継続結果系": {
        "desc": "長期使用→信頼性と説得力",
        "templates": [
            "{period}間毎日使い続けて気づいた{product}の本当の実力",
            "半信半疑で始めた{action}、{period}後に{result}になってた",
            "{number}本リピートして分かった{product}が最強な理由",
        ],
        "example": "半信半疑で始めたRF美顔器、3ヶ月後に友達に顔変わったって言われた",
    },

    # ── 疑問提起系 ──────────────────────────────
    "なぜ系": {
        "desc": "問いかけ→読了率UP→エンゲージ",
        "templates": [
            "なんで{common_product}ってこんなに{problem}なんだろう",
            "{product_type}って結局{question}なの？調べたら{surprising_answer}だった",
            "{situation}のとき{action}するの、みんなも？それとも私だけ？",
        ],
        "example": "なんで高い化粧水ってこんなに使用感が微妙なんだろうってずっと思ってた",
    },
    "知ってた系": {
        "desc": "情報格差の提示→優越感欲求",
        "templates": [
            "{fact}って知ってた？私は{period}前まで全然知らなかった",
            "{product_type}の{right_way}、{percentage}の人が知らないらしい",
            "{season}の{action}、実は{timing}にやるのが正解だって初めて知った",
        ],
        "example": "日焼け止めって塗る量が足りてない人が9割らしい、私もそうだった",
    },

    # ── 後悔回避系 ──────────────────────────────
    "去年の後悔系": {
        "desc": "過去の後悔の共有→学習欲求",
        "templates": [
            "去年{season}に{action}しなかったこと、今でも後悔してる",
            "{period}前の自分に{lesson}って教えてあげたい",
            "去年これ知らなかった自分が本当に惜しい",
        ],
        "example": "去年春に日焼け止め変えなかったこと、夏になってから本当に後悔した",
    },
    "コスト比較系": {
        "desc": "価値の可視化→お得感の最大化",
        "templates": [
            "エステ代{price1}が{period}分に変わった話、これが正解だった",
            "{expensive_action}に使ってたお金を{product}に変えたら{result}",
            "{price}円で{expensive_equivalent}と同じ効果、これ以上ないコスパ",
        ],
        "example": "エステ代1回1万円が美顔器1台で3年分に変わった話",
    },

    # ── 参加誘導系 ──────────────────────────────
    "集合知系": {
        "desc": "読者参加の誘発→コメント数激増",
        "templates": [
            "みんな{category}って何使ってる？最近{concern}で変えたくて",
            "{problem}で悩んでる人、おすすめ教えてほしい",
            "{situation}のとき{action}してる人いる？正直レビュー聞きたい",
        ],
        "example": "みんな日焼け止めって何使ってる？最近焼けやすくて変えたくて",
    },
    "二択投票系": {
        "desc": "意見表明欲求→返信率最大化",
        "templates": [
            "{option_a}派と{option_b}派、どっちが多いんだろう",
            "{question}、みんなはどっち？私は{my_choice}派",
            "{product_a}と{product_b}、正直どっちが{benefit}？",
        ],
        "example": "化粧水先塗り派と美容液先派、どっちが多いんだろう、私は化粧水派",
    },
}


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


def get_pattern_examples(n=6) -> str:
    """毎回ランダムに異なるパターンカテゴリを選んでプロンプトに注入"""
    categories = list(BUZZ_PATTERNS.keys())
    selected = random.sample(categories, min(n, len(categories)))
    lines = []
    for cat in selected:
        p = BUZZ_PATTERNS[cat]
        lines.append(f"【{cat}】（心理：{p['desc']}）")
        lines.append(f"  例：{p['example']}")
    return "\n".join(lines)


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
    pattern_examples = get_pattern_examples(6)

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
