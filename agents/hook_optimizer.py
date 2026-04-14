"""フック最適化エージェント：4パターン生成・重み付きスコアリング・再生成"""
import re
from utils.claude_cli import ask_json, MODEL_OPUS
from agents.buzz_analyzer import HOOK_SCORE_WEIGHTS

MAX_RETRIES = 2
MIN_SCORE = 7.0


def apply_weights(hook: str, base_score: float) -> float:
    """フックテキストを解析して重みボーナスを加算する"""
    score = base_score

    # before/after型：変化を示す数字＋期間ワード
    if re.search(r'\d+[日週ヶ月分回]', hook):
        score += HOOK_SCORE_WEIGHTS["before_after"]

    # 価格破壊型：価格表記あり
    if re.search(r'[\d,，]+円', hook):
        score += HOOK_SCORE_WEIGHTS["price_shock"]

    # 一人称型：一人称ワード
    if re.search(r'私|私が|先週|届いた|使ってみた|試したら|やってみた', hook):
        score += HOOK_SCORE_WEIGHTS["first_person"]

    # 数字あり（期間以外の数字も含む）
    if re.search(r'\d', hook):
        score += HOOK_SCORE_WEIGHTS["has_number"]

    # リンクなし
    if 'http' not in hook and 'リンク' not in hook:
        score += HOOK_SCORE_WEIGHTS["no_link"]

    return min(score, 10.0)


def generate_hooks(product: dict, buzz_patterns) -> list:
    """4タイプのフックを生成する"""
    # buzz_patternsがlistでもdictでも動作するよう正規化
    if isinstance(buzz_patterns, list):
        items = [(p.get("name", ""), [p.get("example", "")]) for p in buzz_patterns if isinstance(p, dict)]
    elif isinstance(buzz_patterns, dict):
        items = list(buzz_patterns.items())
    else:
        items = []

    pattern_examples = "\n".join([
        f"【{t}】" + " / ".join([str(e) for e in examples[:2]])
        for t, examples in items
        if examples
    ]) if items else "（パターンなし）"

    _hook_angle = product.get("hook_angle", product["product_name"] + "の訴求")
    _target_pain = product.get("target_pain", "肌悩みを抱える方")
    prompt = f"""スレッズ美容投稿の冒頭1行（フック）を4パターン生成してください。

商品：{product['product_name']}
訴求角度：{_hook_angle}
読者の悩み：{_target_pain}

参考バズパターン（10万インプ超え実績）：
{pattern_examples}

条件：
- 各25文字以内
- URLやリンク誘導は絶対に入れない
- 「最安値」「絶対」「必ず」は禁止
- 1つ目：before/after型（変化を数字で示す。例：「3日で毛穴が消えた」）
- 2つ目：価格破壊型（コスパの驚き。例：「9,900円が2,300円って何事」）
- 3つ目：共感・悩み型（冒頭で悩みを語る。例：「毛穴が気になって夏のファンデ諦めてた」）
- 4つ目：実体験型（一人称で語る。例：「先週届いたんだけど正直ビビった」）

JSONのみで返してください（説明不要）：
[
  {{"type": "before_after型", "hook": "フック文", "score": スコア(0-10), "reason": "1文で理由"}},
  {{"type": "価格破壊型", "hook": "フック文", "score": スコア(0-10), "reason": "1文で理由"}},
  {{"type": "共感・悩み型", "hook": "フック文", "score": スコア(0-10), "reason": "1文で理由"}},
  {{"type": "実体験型", "hook": "フック文", "score": スコア(0-10), "reason": "1文で理由"}}
]"""
    return ask_json(prompt, model=MODEL_OPUS)


def run(product: dict, buzz_patterns: dict) -> dict:
    """重み付きスコア最高のフックを返す。スコア7未満なら最大2回再生成。"""
    best = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            hooks = generate_hooks(product, buzz_patterns)

            # 重みボーナスを適用
            for h in hooks:
                h["weighted_score"] = apply_weights(h["hook"], h.get("score", 0))

            best = max(hooks, key=lambda h: h["weighted_score"])

            for h in hooks:
                print(f"[HookOptimizer] {h['type']}: 基礎{h['score']}→重み{h['weighted_score']:.1f} 「{h['hook']}」")

            if best["weighted_score"] >= MIN_SCORE:
                print(f"[HookOptimizer] 採用: {best['type']} スコア{best['weighted_score']:.1f} 「{best['hook']}」")
                return best

            print(f"[HookOptimizer] スコア不足({best['weighted_score']:.1f}) 再生成 {attempt + 1}/{MAX_RETRIES}")
        except Exception as e:
            print(f"[HookOptimizer] エラー: {e}")

    print("[HookOptimizer] 最大リトライ到達。最後のベストを使用")
    return best
