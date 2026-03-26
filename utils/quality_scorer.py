"""投稿品質スコアリング（claude -p 経由）"""
import json
from utils.claude_cli import ask_json


def score_post(text: str) -> dict:
    """
    投稿文を0〜10でスコアリングする。
    返り値: {"score": 7.5, "reason": "...", "pass": True}
    """
    prompt = f"""以下のスレッズ投稿文を採点してください。
対象読者：20〜40代女性・美容に関心あり
ジャンル：スキンケア・美顔器

採点基準（各2点満点）：
1. フック力（冒頭1行で続きを読みたくなるか）
2. 具体性（数字・体験談・商品名が入っているか）
3. 簡潔さ（109文字以内・余分な言葉がないか）
4. 行動喚起（リンクを踏みたくなるか）
5. 自然さ（広告臭がなく親しみやすいか）

投稿文：
{text}

JSON形式のみで返してください（説明不要）：
{{"score": 数値, "reason": "理由を1文で", "improvements": ["改善点1", "改善点2"]}}"""

    try:
        data = ask_json(prompt)
        data["pass"] = data.get("score", 0) >= 7.0
        return data
    except Exception as e:
        print(f"[Scorer] エラー: {e}")
        return {"score": 0, "reason": "採点失敗", "pass": False}


def similarity_score(text: str, history: list[str]) -> float:
    """
    過去投稿との最大類似度を返す（0〜1）。
    文字n-gramで計算（外部ライブラリ不要）。
    """
    if not history:
        return 0.0

    def ngrams(s: str, n: int = 3) -> set:
        return {s[i: i + n] for i in range(len(s) - n + 1)}

    target = ngrams(text)
    max_sim = 0.0
    for past in history:
        past_ng = ngrams(past)
        union = target | past_ng
        if not union:
            continue
        sim = len(target & past_ng) / len(union)
        max_sim = max(max_sim, sim)
    return max_sim
