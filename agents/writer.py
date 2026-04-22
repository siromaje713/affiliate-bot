"""ライターエージェント：Threadsバイラル投稿から動的抽出したパターンでコンテンツ生成"""
import json
import random
from datetime import datetime
from pathlib import Path
from utils.claude_cli import ask, ask_json, ask_short, ask_plain
from utils.quality_scorer import score_post, similarity_score

HISTORY_PATH = Path("/tmp/post_history.json")
BUZZ_PATTERNS_PATH = Path(__file__).parent.parent / "data" / "buzz_patterns.json"
RAW_LOG_DIR = Path(__file__).parent.parent / "data" / "llm_raw_logs"
MAX_HISTORY = 100
SIMILARITY_THRESHOLD = 0.6
MAX_POST_CHARS = 109  # Threads投稿ルール（posting-rules.md）
PREAMBLE_PREFIXES = ("こちら", "以下", "投稿案", "いかがでしょう", "ご要望", "承知", "了解")
MARKDOWN_PREFIXES = ("```", "#", "---")

# list型・姉シリーズのテーマ候補（毎回3つランダム選出・1 callに1テーマ）
ANE_THEMES = [
    "スキンケア", "コスメ", "生活習慣", "ヘアケア", "ボディケア",
    "食事・インナーケア", "メイク", "ダイエット・体型管理", "睡眠・回復", "メンタル・ストレスケア",
]

# list型・保存型のテーマ候補
SAVE_THEMES = [
    "毛穴ケア", "乾燥対策", "敏感肌ケア", "UV対策", "ニキビ対策",
    "くすみ対策", "ヘアケア", "メイク直し", "リップケア", "睡眠ケア",
]

# engage型の型定義（109字以内に収まる型のみ採用・G/Jは150〜300字なので除外）
ENGAGE_TYPES = {
    "A": {
        "name": "知識暴露型",
        "pattern": "「[事実]って[数字/根拠]。[返信誘導]？😳」",
        "example": "日焼け止め、量足りてない人9割らしい。知ってた？😳",
        "length": "25〜80字",
    },
    "B": {
        "name": "行動訂正型",
        "pattern": "「[NG行動]してる人まだいる？[正解]が正解。やってた？」",
        "example": "洗顔後すぐ保湿しないとダメ。3分以内にやってる？",
        "length": "25〜80字",
    },
    "C": {
        "name": "やり方暴露型",
        "pattern": "「[方法]って[意外な事実]知ってた？[返信誘導]🙌」",
        "example": "美容液って下から上に押し込むのが正解って知ってた？🙌",
        "length": "25〜80字",
    },
    "H": {
        "name": "独白・本音型",
        "pattern": "「正直に言う。わたし[自虐/失敗/本音]だった。気づいたのが[学び]。同じ人いる？」",
        "example": "正直、化粧水ケチってたら夕方カピカピだった。今は倍つけてる。同じ人いる？",
        "length": "80〜109字",
    },
    "I": {
        "name": "論争型",
        "pattern": "「[賛否分かれるテーマ]って[立場表明]だと思う。これ言うと怒る人いるよね。でも[根拠]。どう思う？」",
        "example": "化粧水いらない説、わたしは反対。乾燥肌が救われたのは確かに化粧水。どう思う？",
        "length": "80〜109字",
    },
    "K": {
        "name": "姉ショート型",
        "pattern": "「姉に[衝撃の一言]って言われた。調べたら[事実]で震えた。」",
        "example": "姉に「夜更かしで肌が老ける」って言われた。調べたら22時以降で糖化3倍で震えた。",
        "length": "30〜60字",
    },
}

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
def validate_post(text: str) -> tuple[bool, str]:
    """投稿本文の最小バリデーション。返値: (OK/NG, 理由文字列)。"""
    if not text or not text.strip():
        return False, "空文字"
    t = text.strip()
    if len(t) > MAX_POST_CHARS:
        return False, f"{len(t)}字（{MAX_POST_CHARS}字超過）"
    for p in PREAMBLE_PREFIXES:
        if t.startswith(p):
            return False, f"前置き検出「{p}」"
    for p in MARKDOWN_PREFIXES:
        if t.startswith(p):
            return False, f"マークダウン検出「{p}」"
    return True, "OK"


def _clean_response(raw: str) -> str:
    """LLM応答の前後空白・引用符・コードフェンスを除去。"""
    t = raw.strip()
    # コードフェンス除去
    if t.startswith("```"):
        lines = t.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    # 前後の引用符除去
    for q in ('"', "'", "「", "」"):
        t = t.strip(q)
    return t.strip()


def _save_raw_log(label: str, idx: int, prompt: str, raw: str) -> None:
    """生応答をdata/llm_raw_logs/に保存。デバッグ用。失敗しても呼び出し側は継続。"""
    try:
        RAW_LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fpath = RAW_LOG_DIR / f"{ts}_{label}_{idx}.txt"
        fpath.write_text(
            f"[PROMPT]\n{prompt}\n\n[RAW]\n{raw}\n",
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[Writer] raw_log保存失敗: {type(e).__name__}")


def build_ane_prompt(theme: str) -> str:
    """姉シリーズ1件用プロンプト。1テーマのみ渡す。"""
    return (
        f"27歳「わたし」が皮膚科クリニック勤務の姉（32歳・看護師）から仕込まれた"
        f"{theme}のコツを1件だけThreads投稿にする。\n\n"
        "【姉】何百人の肌を見てきたプロ。プチプラもデパコスも成分で判断。妹に口うるさい。\n"
        "【文体】一人称「わたし」。友達にLINEするノリ。絵文字1〜2個。\n"
        "【構成】姉起点のフック（「姉が〜」「姉に〜って言われた」等で始める）"
        "→ 具体的な数字や手順 → 締めは共感/問いかけ/姉への愛情ツッコミのどれか。\n"
        f"【厳守】{MAX_POST_CHARS}字以内。押し売り・商品名プッシュ禁止。"
        "リンク・URL・ハッシュタグ・「続きはリプ欄」禁止。\n\n"
        "本文のみ出力。前置き・説明・JSON・マークダウン・引用符で囲むの一切禁止。"
    )


def build_save_prompt(theme: str) -> str:
    """保存型1件用プロンプト。1テーマのみ渡す。"""
    return (
        f"27歳美容オタク「わたし」が{theme}の「保存用まとめ」を1件だけThreads投稿にする。\n\n"
        "【文体】一人称「わたし」。友達にLINEするノリ。絵文字1〜2個。\n"
        f"【構成】冒頭に「{theme}【保存用】」→ 悩み→解決策 を2〜3項目（1行1項目・矢印→で区切る）"
        "→ 締めは共感か背中押し。\n"
        f"【厳守】{MAX_POST_CHARS}字以内。押し売り・商品名プッシュ禁止。"
        "リンク・URL・ハッシュタグ・「続きはリプ欄」禁止。\n\n"
        "本文のみ出力。前置き・説明・JSON・マークダウン・引用符で囲むの一切禁止。"
    )


def build_engage_prompt(type_key: str) -> str:
    """engage型1件用プロンプト。1型のみ渡す。"""
    td = ENGAGE_TYPES[type_key]
    return (
        f"27歳「わたし」が美容トピックで返信が集まる短文を1件だけThreads投稿にする。\n\n"
        f"【型】{td['name']}：{td['pattern']}\n"
        f"【例】{td['example']}\n"
        f"【文字数目安】{td['length']}\n\n"
        "【文体】友達にLINEするノリ。絵文字1〜2個。例文と全く同じ文は禁止、ネタを差し替える。\n"
        f"【厳守】{MAX_POST_CHARS}字以内。商品名プッシュ・リンク・URL・ハッシュタグ・「続きはリプ欄」禁止。\n\n"
        "本文のみ出力。前置き・説明・JSON・マークダウン・引用符で囲むの一切禁止。"
    )


def _generate_from_prompts(prompts: list, label: str, max_tokens: int = 200) -> list:
    """プロンプトリストを逐次呼び出しし、バリデーション通過分だけ返す。

    3 call全失敗でも例外は上げない。空リストを返す。呼び出し側で判断する。
    """
    accepted = []
    for i, prompt in enumerate(prompts):
        raw = ""
        try:
            raw = ask_plain(prompt, max_tokens=max_tokens)
        except Exception as e:
            print(f"[Writer] {label}{i+1}: API失敗 → {type(e).__name__}: {str(e)[:120]}")
            _save_raw_log(label, i, prompt, f"[EXCEPTION] {type(e).__name__}: {e}")
            continue
        _save_raw_log(label, i, prompt, raw)
        cleaned = _clean_response(raw)
        ok, reason = validate_post(cleaned)
        if ok:
            print(f"[Writer] {label}{i+1}: 採用（{len(cleaned)}字）")
            accepted.append(cleaned)
        else:
            print(f"[Writer] {label}{i+1}: バリデーション失敗 → {reason} / raw頭: {raw[:50]!r}")
    return accepted


def generate_patterns(
    product: dict,
    hook=None,
    win_patterns=None,
    competitor_posts=None,
    post_type: str = "link",
) -> list:
    # list型: 姉シリーズ/保存型をランダム選択・3テーマに対し3 call逐次実行
    if post_type == "list":
        if random.random() < 0.5:
            subtype = "ane"
            print("[Writer] list型サブタイプ: 姉シリーズ")
            themes = random.sample(ANE_THEMES, 3)
            prompts = [build_ane_prompt(t) for t in themes]
            label = "list_ane"
        else:
            subtype = "save"
            print("[Writer] list型サブタイプ: 保存型")
            themes = random.sample(SAVE_THEMES, 3)
            prompts = [build_save_prompt(t) for t in themes]
            label = "list_save"
        texts = _generate_from_prompts(prompts, label, max_tokens=200)
        # 後処理で affiliate_keyword を埋める（保存型は product名、姉シリーズは空）
        aff_kw = product.get("product_name", "") if subtype == "save" else ""
        return [{"text": t, "affiliate_keyword": aff_kw} for t in texts]

    # engage型: 6型からランダム3型選出・3 call逐次実行
    if post_type == "engage":
        type_keys = random.sample(list(ENGAGE_TYPES.keys()), 3)
        print(f"[Writer] engage型: 選出型 {', '.join(type_keys)}")
        prompts = [build_engage_prompt(k) for k in type_keys]
        return _generate_from_prompts(prompts, "engage", max_tokens=200)

    # 以降は buzz/link 型（production未使用・触らない）
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

    if post_type == "buzz":
        prompt = f"""Threadsでバズる投稿を3パターン生成してください。

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

3パターンをJSON配列のみで返してください：
["投稿文1", "投稿文2", ...]"""

    else:
        prompt = f"""楽天アフィリエイト向けThreads投稿を3パターン生成してください。

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

3パターンをJSON配列のみで返してください：
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
    print(f"[Writer] 「{product['product_name']}」{post_type}型 3パターン生成中...")
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
            if length < 20 or length > 350:
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


def generate_self_reply(original_text: str) -> str:
    """投稿直後の自己リプ（補足コメント）を1件生成する。50-80文字・宣伝NG。"""
    prompt = f"""以下のThreads投稿に対して、本文では書ききれなかった補足情報を1つだけリプとして書いてください。

【元投稿】
{original_text}

【厳守ルール】
- 50〜80文字
- 具体例・数字・体験談のどれかを必ず入れる
- 宣伝・商品名プッシュ・リンク・ハッシュタグは絶対NG
- 一人称は「わたし」。友達にLINEするノリ
- 絵文字1個まで

補足リプ本文のみ返してください（説明・カギ括弧不要）。"""
    try:
        text = ask_short(prompt).strip().strip("「」\"'")
        return text
    except Exception as e:
        print(f"[Writer] 自己リプ生成失敗: {type(e).__name__}")
        return ""
