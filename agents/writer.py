"""ライターエージェント：Threadsバイラル投稿から動的抽出したパターンでコンテンツ生成"""
import json
import random
from datetime import datetime
from pathlib import Path
from utils.claude_cli import ask_json
from utils.quality_scorer import score_post, similarity_score

HISTORY_PATH = Path("/tmp/post_history.json")
BUZZ_PATTERNS_PATH = Path(__file__).parent.parent / "data" / "buzz_patterns.json"
MAX_HISTORY = 100
SIMILARITY_THRESHOLD = 0.6

# フォールバック用パターン（buzz_patterns.jsonが空/取得失敗時に使用）
_FALLBACK_PATTERNS = [
    {"name": "悲報系", "hook_structure": "悲報、〇〇してた私が△△だった", "ending_pattern": "…って知らなかった", "example": "悲報、美白頑張ってた私、実は紫外線対策が全然足りてなかった"},
    {"name": "朗報系", "hook_structure": "朗報、〇〇で悩んでた私が△△した話", "ending_pattern": "もっと早く知りたかった", "example": "朗報、毛穴の開きで悩んでた私が3日で変わった話"},
    {"name": "衝撃暴露系", "hook_structure": "皮膚科で言われた衝撃の一言、〇〇は嘘だった", "ending_pattern": "って本当だった", "example": "皮膚科で言われた衝撃の一言、保湿は量より順番が全てって"},
    {"name": "ビフォーアフター系", "hook_structure": "〇〇を始めて△△、□□が起きた話", "ending_pattern": "気のせいじゃなかった", "example": "美顔器を始めて3ヶ月、輪郭が変わった気がするのは気のせいじゃなかった"},
    {"name": "あるある系", "hook_structure": "〇〇で悩んでる人って私だけじゃないよね？", "ending_pattern": "正直に手あげて", "example": "27歳で毛穴が気になり始めた人、正直に手あげて"},
    {"name": "知ってた系", "hook_structure": "〇〇って知ってた？私は△△前まで全然知らなかった", "ending_pattern": "知らなかった", "example": "日焼け止めって塗る量が足りてない人が9割らしい、私もそうだった"},
    {"name": "コスト比較系", "hook_structure": "エステ代〇〇が△△分に変わった話", "ending_pattern": "これが正解だった", "example": "エステ代1回1万円が美顔器1台で3年分に変わった話"},
    {"name": "今すぐやれ系", "hook_structure": "〇〇前にこれをやってない人、まじで後悔する", "ending_pattern": "まじで後悔する", "example": "4月中に日焼け止め変えてない人、まじで5月後悔する"},
]


def _load_buzz_patterns() -> list:
    """data/buzz_patterns.jsonから動的パターンをロードする。
    dict型/list型/ネスト形式など全形式を安全にlist[dict]へ正規化する。"""
    if not BUZZ_PATTERNS_PATH.exists():
        return []
    try:
        data = json.loads(BUZZ_PATTERNS_PATH.read_text(encoding="utf-8"))
        # top-levelがdictでなければ諦める
        if not isinstance(data, dict):
            return []
        patterns = data.get("patterns") or data  # "patterns"キーがなければ全体を試みる
        if not patterns:
            return []

        # dict型（旧形式: {"before_after型": ["例文1", ...], ...}）→ list[dict]に変換
        if isinstance(patterns, dict):
            result = []
            for k, v in patterns.items():
                if isinstance(v, list):
                    example = str(v[0]) if v else ""
                elif isinstance(v, str):
                    example = v
                else:
                    example = ""
                result.append({
                    "name": str(k),
                    "hook_structure": example,
                    "ending_pattern": "",
                    "example": example,
                })
            return result

        # list型（新形式）→ 各要素をdictに正規化
        if isinstance(patterns, list):
            result = []
            for item in patterns:
                if not isinstance(item, dict):
                    continue
                result.append({
                    "name": str(item.get("name", "")),
                    "hook_structure": str(item.get("hook_structure", "")),
                    "ending_pattern": str(item.get("ending_pattern", "")),
                    "example": str(item.get("example", "")),
                })
            return result

    except Exception:
        pass
    return []


def _get_or_generate_patterns() -> list:
    """パターンをロード、なければbuzz_researcherで生成、それも失敗ならフォールバックを返す"""
    patterns = _load_buzz_patterns()
    if patterns:
        return patterns
    try:
        from agents import buzz_researcher
        print("[Writer] buzz_patterns.jsonが空のため動的生成します...")
        context = buzz_researcher.get_buzz_context()
        patterns = context.get("patterns", [])
        if patterns:
            return patterns
    except Exception as e:
        print(f"[Writer] パターン動的生成失敗: {e}")
    print("[Writer] フォールバックパターンを使用します")
    return _FALLBACK_PATTERNS


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
    # 必ずlist[dict]に正規化（予期しない型が来てもクラッシュしない）
    if not isinstance(dynamic_patterns, list):
        dynamic_patterns = []
    pattern_section = ""
    if dynamic_patterns:
        lines = []
        for p in dynamic_patterns[:8]:
            if not isinstance(p, dict):
                continue
            example = str(p.get("example", ""))[:50]
            lines.append(
                f"・【{p.get('name','')}】冒頭: {p.get('hook_structure','')} / 語尾: {p.get('ending_pattern','')} / 例: {example}"
            )
        if lines:
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
    _target_pain = product.get("target_pain", "肌悩みを抱える方")

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

    # 7パターンテンプレート（20アカウントリサーチ実データ）
    seven_patterns = f"""
【必須：以下7パターンからランダムに選んで使うこと（各パターンで1投稿ずつ生成）】
商品名「{product['product_name']}」を必ず本文中に1回入れること。

パターン1【専門家ゾッと型】
「[皮膚科医/美容クリニックの友達/美容師の知り合い]に言われてゾッとした話。
『[{product['product_name']}に関連する常識を破る一言]』って。これ心当たりない？」

パターン2【悩み直撃型】
「私[{_target_pain}]人なんだけど、{product['product_name']}のおかげで[解決した体験]。
同じ悩みの人いる？」

パターン3【話題便乗型】
「[小田切ヒロ/紗栄子/千賀健永/TWICEのメンバー]が[{product['product_name']}のカテゴリ]使ってるって聞いて試した。
[衝撃の結果]。みんな試した？」

パターン4【情報訂正型】
「[間違いやすい美容知識]で[間違った行動]してた。{product['product_name']}試して初めて気づいた。
みんなちゃんと調べてる？」

パターン5【断言命令型】
「[{_target_pain}]の人、全員これ見て。
{product['product_name']}が[衝撃的な理由]で最強なの、知らなきゃ損！」

パターン6【DM要請型】
「[{product['product_name']}のカテゴリ]何使ってるか聞かれすぎるから正直に言う。
[期間]ずっとリピートしてる{product['product_name']}の話」

パターン7【自虐キャラ型】
「また{product['product_name']}の話だけど、[本数/期間]使い切って確信した。
愛用品はそう簡単に変わらない理由→」
"""

    buzz_guide = f"""
{pattern_examples}
{seven_patterns}

【絶対NG】
❌ 「〇〇がおすすめです」→広告感
❌ 「〇〇を使ってみました」→レポート感
❌ 冒頭が商品名→販促感
❌ 商品名が本文に入っていない→具体性ゼロ
❌ 質問なし→コメント誘発できない

【感情温度を上げる必須ルール】
✅ 感嘆符(!、！)を1〜2個使う
✅ 絵文字を1〜2個使う
✅ 必ず質問で締める（「みんなは？」「試した人いる？」「心当たりない？」）
✅ 商品名「{product['product_name']}」を必ず1回入れる
✅ 27歳女性の等身大・感情的な言葉遣い
"""

    if post_type == "engage":
        # buzz_patterns.jsonからinfo_factを抽出してプロンプトに渡す
        info_facts_section = ""
        try:
            _bp = _load_buzz_patterns()
            facts = []
            # 生JSONからinfo_factも拾う（_load_buzz_patternsは正規化で落とすため再読込）
            if BUZZ_PATTERNS_PATH.exists():
                _raw = json.loads(BUZZ_PATTERNS_PATH.read_text(encoding="utf-8"))
                _patterns = _raw.get("patterns", []) if isinstance(_raw, dict) else []
                if isinstance(_patterns, list):
                    for p in _patterns:
                        if isinstance(p, dict):
                            f = p.get("info_fact") or ""
                            if f:
                                facts.append(str(f))
            if facts:
                info_facts_section = "\n【最新info_factネタ（毎回どれか1つを必ず使う・連続使用禁止）】\n" + "\n".join(f"- {x}" for x in facts[:15]) + "\n"
        except Exception:
            pass

        prompt = f"""Threadsで返信往復を最大化する有益情報×煽り口調の短文投稿を6パターン生成してください。

テーマ：美容・スキンケア・メイク（特定商品名は入れない）
{seasonal_info}{info_facts_section}

【目的】返信往復を最大化する。有益情報×煽り口調。

【厳守ルール】
- 50〜80文字（厳守。短く鋭く）
- 絵文字1〜2個
- リンク・商品名・「続きはリプ欄」は絶対NG
- ハッシュタグ（#）絶対NG
- 必ず返信を誘う問いかけで終わる
- フォロワー以外からのリプを引き出す設計

【黄金パターン（必ずこの3型のうちいずれかを使う・6パターン全体で型を散らす）】

型A. 知識暴露型：
「[事実]って[数字や根拠]。[返信誘導]？😳」
例：「日焼け止めって量が足りてない人が9割らしい。500円玉大って聞いたことある？知ってた？😳」

型B. 行動訂正型：
「[NG行動]してる人まだいる？[正解]が正解。やってた？」
例：「洗顔後すぐ保湿しないと肌が空気から水分奪われてく。3分以内にやってる人どのくらいいる？」

型C. やり方暴露型：
「[方法]って[意外な事実]知ってた？[返信誘導]🙌」
例：「美容液って浸透させる方向あるの知ってた？下から上に押し込むのが正解。やってた人いる？🙌」

【絶対条件】
- 上記info_factを毎回参照して新ネタを使う
- 同じ型を連続させない（A→B→C→A→B→C のようにバラす）
- 例文と全く同じ文は禁止。事実部分を新ネタに差し替える

6パターンをJSON配列のみで返してください：
["投稿文1", "投稿文2", "投稿文3", "投稿文4", "投稿文5", "投稿文6"]"""

    elif post_type == "list":
        # list型30%枠の中で50%を姉シリーズ、50%を既存の保存リスト型に振り分け
        if random.random() < 0.5:
            print("[Writer] list型サブタイプ: 姉シリーズ")
            prompt = f"""Threadsで保存・共感される「姉シリーズ」投稿を6パターン生成してください。

【コンセプト】
27歳の「りこ」が、30代の姉の実体験・習慣・アドバイスを引用する形の投稿。
姉=美容に詳しい身近なロールモデル。20代の自分が真似して変化があった、という構成。
リンク・商品名プッシュはしない。保存されるための純粋な有益情報。
{seasonal_info}{win_section}

【厳守構成（5〜6文）】
1文目: 姉起点のフック（例：「姉が〜」「姉に〜って言われた」「姉が30代で急に〜」）
2〜5文目: 具体的な習慣/アイテムを4項目（必ず「・」始まりの箇条書き）
最終文: 以下3要素を自然に盛り込む（硬い命令調NG）
  - 自分(20代)の体験・気づき or 姉への愛情/ツッコミ（「姉よありがとう」「うるさいと思ってたけど本当だった」「去年サボって後悔した」）
  - 読者への問いかけ or 共感誘導（「みんなは？」「これ知らなかった人いる？」「やってた人教えて！」「同じ人いる？」）
  - 絵文字1〜2個（🌸😂🙌😭🌙😳 など自然に）
硬い例NG：「保存して真似してみて」
柔らかい例OK：「これ知らんかった〜😂 姉よありがとう。みんなも保存して春のうちから試してみて🌸」

【テーマ候補（10種から6つ選んでバラけさせる）】
G-1 スキンケア軸 / G-2 コスメ軸 / G-3 習慣軸 / G-4 ヘアケア軸 / G-5 ボディケア軸
G-6 食事・インナーケア軸 / G-7 メイク軸 / G-8 ダイエット・体型管理軸 / G-9 睡眠・回復軸 / G-10 メンタル・ストレスケア軸

【参考例（このトーン・構成を必ず踏襲すること）】

G-1（スキンケア軸）
姉が30代で急にきれいになった理由を聞いたら全部スキンケアの順番だった
・洗顔後すぐ化粧水（1分以内）
・化粧水はハンドプレスで3回重ねる
・乳液で蓋をしてから保湿クリーム
・週2でビタミンCの美容液
うるさいと思ってたけど本当だった。みんなもやってる？🌸

G-2（コスメ軸）
姉に「そのコスメ買い続けてる理由」聞いたら全部コスパ重視だった
・日焼け止めはアネッサ一択（崩れにくい）
・口紅よりティントの方が長持ち
・アイシャドウは単色2色で十分
・ベースはクッションファンデで時短
姉よセンスの塊すぎん？これ知らなかった人いる？😂

G-3（習慣軸）
姉が「これだけはやれ」って言ってくる美容習慣が地味に全部効いてた
・朝起きたら白湯を飲む
・スマホは寝る1時間前にやめる
・お風呂は湯船に浸かる（週3でいい）
・鏡を見るたびに姿勢を正す
お金かかるケアより無料の習慣の方が変わった。やってた人いたら教えて🙌

G-4（ヘアケア軸）
姉が美容院で「髪質いいですね」って言われまくってる秘密聞いたら全部習慣だった
・シャンプーは頭皮だけ、毛先にはつけない
・タオルドライはゴシゴシNG、挟んでポンポン
・ドライヤーは上から下に風を当てる
・週1でヘアオイルパック（寝る前に塗って朝流す）
35歳でカラーもパーマもしてるのにツヤツヤ。姉よありがとう😭 みんなは何やってる？

G-5（ボディケア軸）
姉に「体の保湿サボるな」って怒られてから始めたケアが良すぎた
・お風呂出て3分以内にボディクリーム塗る
・ひじ・ひざ・かかとは週1でスクラブ
・背中ニキビにはサリチル酸のボディソープ
・二の腕のブツブツにはピーリングジェル
去年サボって後悔した。夏もやれって言われた意味わかった😂 みんなも保存して試してみて🌸

G-6（食事・インナーケア軸）
姉が「肌は食べ物で決まる」って言い張るから1ヶ月真似してみた
・朝イチに白湯を1杯飲む
・タンパク質を毎食手のひら1枚分
・おやつをナッツかハイカカオチョコに替える
・寝る前にビタミンCのサプリ
正直スキンケアより食事の方が効いた。姉の言う通りだった…😭 同じ人いる？

G-7（メイク軸）
姉に「そのメイク古い」って言われて直されたポイントが的確すぎた
・下地は顔全体じゃなくTゾーンと頬だけ
・ファンデは薄く、気になるとこだけコンシーラー
・眉毛は描くより「整える」が先
・チークは笑った頬の高い位置にだけ
引き算にしたら「肌きれいになった？」って言われた😂 足してたの私だけ？

G-8（ダイエット・体型管理軸）
姉が30代で太らなくなったの「食べないダイエット」じゃなかった
・食べる順番を変える（野菜→タンパク質→炭水化物）
・夜20時以降は固形物を食べない
・エレベーターやめて階段にする
・月1で体重じゃなくて体脂肪率を記録
姉の「体重計の数字より服のサイズ」って名言すぎん？わかる人いる？🙌

G-9（睡眠・回復軸）
姉が「睡眠ケチると全部終わる」って力説してくる理由がわかった
・寝る1時間前にスマホやめる（枕元に置かない）
・部屋を真っ暗にする（遮光カーテン必須）
・寝る前のカフェインは14時まで
・休みの日も起きる時間は同じにする
肌荒れ減ったし朝のむくみなくなった。睡眠が最強の美容液だった🌙 みんなは何時間寝てる？

G-10（メンタル・ストレスケア軸）
姉が「メンタル荒れると肌も荒れる」って言ってたの科学的にガチだった
・週1で「何もしない日」を作る
・SNS見すぎたら1日デジタルデトックス
・嫌なことあった日は湯船+アロマ
・朝3分だけ深呼吸する（瞑想じゃなくていい）
ストレスでフェイスラインにニキビ出てたの全部消えた😳 肌より先にメンタルだった。これ知らなかった人いる？

【絶対ルール】
- 必ず「姉」起点（姉が〜 / 姉に〜 / 姉から〜）で始める
- 箇条書きは必ず4項目（3項目も5項目もNG）
- 締めの1文は「自分の体験/気づき or 姉への愛情ツッコミ」+「読者への問いかけ」+「絵文字1〜2個」で柔らかく終わる
- リンク・URL・商品名プッシュ・ハッシュタグ絶対NG
- 「続きはリプ欄」「DMで聞いて」もNG
- 6パターンで使うテーマは必ず6種バラす（同じG-番号を重複させない）
- 参考例の文を丸コピせず、事実部分を差し替えて新規生成

【出力形式】
6パターンを以下のJSON形式のみで返してください（説明不要）：
{{
  "posts": [
    {{"text": "投稿本文1", "affiliate_keyword": ""}},
    {{"text": "投稿本文2", "affiliate_keyword": ""}}
  ]
}}"""
        else:
            print("[Writer] list型サブタイプ: 既存保存リスト型")
            prompt = f"""Threadsで保存・リポストされる「保存リスト型」投稿を6パターン生成してください。

商品名：{product['product_name']}（本文中に出さなくてよい。アフィリエイトキーワードは別フィールドで返す）
読者の悩み：{_target_pain}
{seasonal_info}{win_section}{competitor_section}

【目的】保存・リポスト最大化＋アフィ自然訴求

【厳守ルール】
- 冒頭1行目は「[テーマ]【保存用】」（例：「成分覚えられない人向け【保存用】」「春の毛穴対策【保存用】」）
- 続いて空行
- 悩み→解決策の対応表を5〜8項目（「悩み → 解決策」の形式・1行1項目）
- 締めは共感・背中押し系（例：「全部じゃなくていい。気になるとこからゆっくり試してみてね🌿」「完璧にやらなくていい。今いちばん気になるやつだけ、まず試してみて♡」）
- 109文字超えはOK（保存型なのでスレッド1/2形式可・長文歓迎）
- リンク・URL・「続きはリプ欄」は絶対NG
- ハッシュタグ（#）絶対NG

【参考フォーマット】
成分覚えられない人向け【保存用】

毛穴 → レチノール
ゴワつき → AHA
毛穴詰まり → BHA
乾燥・敏感 → セラミド
シミ → トラネキサム酸
皮脂・テカリ → ナイアシンアミド
くすみ → ビタミンC

全部じゃなくていい。気になるとこからゆっくり試してみてね🌿

【出力形式】
6パターンを以下のJSON形式のみで返してください（説明不要）：
{{
  "posts": [
    {{"text": "投稿本文1", "affiliate_keyword": "アフィURL取得用キーワード（例: メラノCC）"}},
    {{"text": "投稿本文2", "affiliate_keyword": "..."}}
  ]
}}"""

    elif post_type == "buzz":
        prompt = f"""Threadsでバズる投稿を6パターン生成してください。

商品：{product['product_name']}
読者の悩み：{_target_pain}
{seasonal_info}{buzz_guide}{win_section}{competitor_section}

生成ルール：
- 109文字以内（必須）
- {hook_instruction if hook_instruction else '上記7パターンから6つ選んで、各パターンを1投稿ずつ作る'}
- 商品名「{product['product_name']}」を必ず本文中に1回入れる
- URLや商品リンク誘導は禁止
- 投稿の最後に「続きはリプ欄👇」を必ず入れる
- 感嘆符と絵文字で感情温度を上げる

トレンドフック（最優先）：
話題便乗型フックを最優先で使う。その週のトレンド美容ネタ（YouTuber名・ドラマ・季節イベント）を冒頭に絡める。
例：「小田切ヒロさんが紹介してたアレ試した」「春になって敏感肌が爆発した人↑」

厳守ルール：
- ハッシュタグ（#）は絶対に使うな
- 冒頭1行目で読者を絞れ
- 商品の固有名詞を必ず入れる
- 今買う理由を自然に入れる
- リンクは本文に入れるな

6パターンをJSON配列のみで返してください：
["投稿文1", "投稿文2", ...]"""

    else:
        prompt = f"""楽天アフィリエイト向けThreads投稿を6パターン生成してください。

商品名：{product['product_name']}
訴求角度：{hook_angle}
読者の悩み：{_target_pain}
{seasonal_info}{buzz_guide}{win_section}{competitor_section}

生成ルール：
- 109文字以内（必須）
- {hook_instruction if hook_instruction else '上記7パターンから6つ選んで、各パターンを1投稿ずつ作る'}
- 商品名「{product['product_name']}」を必ず本文中に1回入れる（これが最重要）
- URLや「リンク」「こちら」等の誘導は禁止
- 投稿の最後に「続きはリプ欄👇」を必ず入れる
- 感嘆符と絵文字で感情温度を上げる
- 季節感・数字を入れる

厳守ルール：
- ハッシュタグ（#）は絶対に使うな
- 冒頭1行目で読者を絞れ
- 商品の固有名詞を必ず入れる
- 今買う理由を自然に入れる
- リンクは本文に入れるな

6パターンをJSON配列のみで返してください：
["投稿文1", "投稿文2", ...]"""

    try:
        result = ask_json(prompt)
        # list型は{"posts":[{"text":..,"affiliate_keyword":..}]}形式
        if post_type == "list" and isinstance(result, dict):
            return result.get("posts", [])
        return result
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

    # list型は{text,affiliate_keyword}のdict・109文字制限なし
    if post_type == "list":
        for i, item in enumerate(patterns):
            if isinstance(item, dict):
                text = item.get("text", "")
                aff_kw = item.get("affiliate_keyword", "")
            else:
                text = str(item)
                aff_kw = ""
            if not text or not text.strip():
                continue
            sim = similarity_score(text, history)
            if sim >= SIMILARITY_THRESHOLD:
                print(f"[Writer] list{i+1}: 類似度{sim:.2f} → スキップ")
                continue
            # list型は保存型なので品質スコアを通さず長さだけチェック（500文字以内）
            if len(text) > 500:
                print(f"[Writer] list{i+1}: 文字数超過({len(text)}字) → スキップ")
                continue
            print(f"[Writer] list{i+1}: 採用候補（{len(text)}字・キーワード:{aff_kw}）")
            if best is None:
                best = {
                    "text": text,
                    "score": 100,
                    "product": product,
                    "post_type": post_type,
                    "affiliate_keyword": aff_kw,
                }
        if best:
            print(f"[Writer] list型: 最良パターン決定（{len(best['text'])}字）")
            save_to_history(best["text"])
        return best

    # engage型は50〜80字、品質スコアは通さず短文ルールで採用
    if post_type == "engage":
        for i, text in enumerate(patterns):
            if not isinstance(text, str):
                continue
            length = len(text)
            if length < 30 or length > 100:
                print(f"[Writer] engage{i+1}: 文字数範囲外({length}字) → スキップ")
                continue
            sim = similarity_score(text, history)
            if sim >= SIMILARITY_THRESHOLD:
                print(f"[Writer] engage{i+1}: 類似度{sim:.2f} → スキップ")
                continue
            print(f"[Writer] engage{i+1}: 採用候補（{length}字）")
            if best is None:
                best = {"text": text, "score": 100, "product": product, "post_type": post_type}
        if best:
            print(f"[Writer] engage型: 最良パターン決定")
            save_to_history(best["text"])
        return best

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
        if result["pass"] or post_type in ("engage", "list"):
            if best is None or score > best["score"]:
                best = {"text": text, "score": score, "product": product, "post_type": post_type}

    if best:
        print(f"[Writer] 最良パターン決定: スコア{best['score']}")
        save_to_history(best["text"])
    else:
        print("[Writer] 品質基準を満たすパターンなし")

    return best
