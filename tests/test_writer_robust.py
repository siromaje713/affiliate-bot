"""writer.py Phase 1（JSON廃止・3 call分割）の単体テスト。

- プロンプト長・テーマ単一性の構造検証
- validate_post の正常/異常判定
- モックLLM で3 call 中1 call 失敗しても候補が返る動作検証
"""
import random
from unittest.mock import patch

import pytest

from agents import writer


# ------------------------------------------------------------
# プロンプト構造
# ------------------------------------------------------------
class TestPromptStructure:
    def test_ane_prompt_under_700_chars(self):
        for theme in writer.ANE_THEMES:
            p = writer.build_ane_prompt(theme)
            assert len(p) <= 700, f"ane[{theme}] {len(p)}字（>700）"

    def test_save_prompt_under_700_chars(self):
        for theme in writer.SAVE_THEMES:
            p = writer.build_save_prompt(theme)
            assert len(p) <= 700, f"save[{theme}] {len(p)}字（>700）"

    def test_engage_prompt_under_700_chars(self):
        for k in writer.ENGAGE_TYPES:
            p = writer.build_engage_prompt(k)
            assert len(p) <= 700, f"engage[{k}] {len(p)}字（>700）"

    def test_ane_prompt_contains_only_one_theme(self):
        """プロンプト内で1テーマだけが言及されることを確認。他テーマが混入していたらNG"""
        target = "スキンケア"
        p = writer.build_ane_prompt(target)
        assert target in p
        # 他のテーマは含まれない（タイトル/見出しレベルで）
        for other in writer.ANE_THEMES:
            if other == target:
                continue
            assert other not in p, f"他テーマ「{other}」が混入: {p}"

    def test_save_prompt_contains_only_one_theme(self):
        target = "毛穴ケア"
        p = writer.build_save_prompt(target)
        assert target in p
        for other in writer.SAVE_THEMES:
            if other == target:
                continue
            assert other not in p, f"他テーマ「{other}」が混入"

    def test_engage_prompt_contains_only_one_type(self):
        target = "A"
        p = writer.build_engage_prompt(target)
        td = writer.ENGAGE_TYPES[target]
        assert td["name"] in p
        # 他の型の name は含まれない
        for other_key, other_td in writer.ENGAGE_TYPES.items():
            if other_key == target:
                continue
            assert other_td["name"] not in p, f"他型「{other_td['name']}」が混入"

    def test_prompts_forbid_json_and_markdown(self):
        """プロンプトに「JSON禁止」「マークダウン禁止」の明文指示があることを確認"""
        for builder, arg in [
            (writer.build_ane_prompt, "スキンケア"),
            (writer.build_save_prompt, "毛穴ケア"),
            (writer.build_engage_prompt, "A"),
        ]:
            p = builder(arg)
            assert "JSON" in p
            assert "マークダウン" in p
            assert "109字以内" in p


# ------------------------------------------------------------
# validate_post
# ------------------------------------------------------------
class TestValidatePost:
    def test_empty_rejected(self):
        ok, _ = writer.validate_post("")
        assert ok is False

    def test_whitespace_only_rejected(self):
        ok, _ = writer.validate_post("   \n  ")
        assert ok is False

    def test_109_chars_ok(self):
        ok, _ = writer.validate_post("あ" * 109)
        assert ok is True

    def test_110_chars_rejected(self):
        ok, reason = writer.validate_post("あ" * 110)
        assert ok is False
        assert "超過" in reason

    def test_preamble_rejected(self):
        for prefix in ("こちら", "以下", "投稿案", "いかがでしょう"):
            ok, reason = writer.validate_post(f"{prefix}投稿です。姉が〜")
            assert ok is False, f"前置き「{prefix}」が通過"
            assert "前置き" in reason

    def test_markdown_rejected(self):
        for prefix in ("```", "#", "---"):
            ok, reason = writer.validate_post(f"{prefix}本文")
            assert ok is False, f"マークダウン「{prefix}」が通過"
            assert "マークダウン" in reason

    def test_normal_post_accepted(self):
        text = "姉に「夜更かしで肌が老ける」って言われた。調べたら22時以降で糖化3倍で震えた😳"
        ok, reason = writer.validate_post(text)
        assert ok is True
        assert reason == "OK"


# ------------------------------------------------------------
# _generate_from_prompts の部分失敗許容
# ------------------------------------------------------------
class TestPartialFailureTolerance:
    def test_one_success_out_of_three_calls(self):
        """3 call 中 2 call が失敗しても、1 call成功分が返ることを確認"""
        call_count = {"n": 0}

        def fake_ask_plain(prompt, max_tokens=200):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("mock API failure")
            if call_count["n"] == 2:
                return "こちらが投稿案です"  # 前置き検出で破棄される
            return "姉に日焼け対策教わった。朝のUVは出かける15分前がベスト💪"

        with patch("agents.writer.ask_plain", side_effect=fake_ask_plain):
            prompts = ["p1", "p2", "p3"]
            accepted = writer._generate_from_prompts(prompts, "test", max_tokens=200)

        assert len(accepted) == 1, f"期待1件 got {len(accepted)}"
        assert "姉に日焼け対策教わった" in accepted[0]

    def test_all_three_fail_returns_empty(self):
        """3 call 全失敗時は空リストを返す（呼び出し側で判断）"""
        def always_fail(prompt, max_tokens=200):
            raise RuntimeError("mock total failure")

        with patch("agents.writer.ask_plain", side_effect=always_fail):
            accepted = writer._generate_from_prompts(["p1", "p2", "p3"], "test", max_tokens=200)
        assert accepted == []

    def test_all_three_succeed(self):
        texts = [
            "姉に「スキンケアは順番が命」って言われた。洗顔→化粧水1分以内だって🌸",
            "UV対策まとめ【保存用】\n朝15分前→塗布\n2時間→塗り直し",
            "正直化粧水ケチってた。倍つけたら夕方のカピカピ消えた。同じ人いる？",
        ]
        idx = {"i": 0}

        def fake_ask_plain(prompt, max_tokens=200):
            t = texts[idx["i"]]
            idx["i"] += 1
            return t

        with patch("agents.writer.ask_plain", side_effect=fake_ask_plain):
            accepted = writer._generate_from_prompts(["p1", "p2", "p3"], "test", max_tokens=200)
        assert len(accepted) == 3


# ------------------------------------------------------------
# generate_patterns(post_type="engage") の統合モック
# ------------------------------------------------------------
class TestGeneratePatternsIntegration:
    def test_engage_returns_list_of_str(self):
        """engage型は str のリストを返す"""
        def fake(prompt, max_tokens=200):
            return "姉に聞いた、朝の日焼け止めは15分前がベスト。みんな守ってる？😳"

        with patch("agents.writer.ask_plain", side_effect=fake):
            random.seed(42)
            result = writer.generate_patterns({}, post_type="engage")
        assert isinstance(result, list)
        assert all(isinstance(x, str) for x in result)
        # 3 call 全部通るはず
        assert len(result) == 3

    def test_list_returns_dict_with_text_and_aff_kw(self):
        """list型は {text, affiliate_keyword} dict のリストを返す"""
        def fake(prompt, max_tokens=200):
            return "姉に日焼け対策教わった。朝のUVは15分前がベスト💪"

        product = {"product_name": "テスト商品"}
        with patch("agents.writer.ask_plain", side_effect=fake):
            random.seed(1)  # ane分岐
            result = writer.generate_patterns(product, post_type="list")
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, dict)
            assert "text" in item
            assert "affiliate_keyword" in item


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
