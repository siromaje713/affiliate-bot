import json
from pathlib import Path
import pytest


def test_import_orchestrator():
    import orchestrator  # noqa: F401


def test_strip_links_removes_urls():
    import orchestrator
    text = "美白の話 https://example.com/a?x=1 続きは後で"
    out = orchestrator.strip_links(text)
    assert "http" not in out
    assert "美白の話" in out


def test_strip_links_removes_rakuten():
    import orchestrator
    out = orchestrator.strip_links("良かった → [楽天リンク]")
    assert "楽天" not in out
    assert "[" not in out


def test_strip_links_preserves_plain_text():
    import orchestrator
    text = "今日はいい天気ですね"
    assert orchestrator.strip_links(text) == text


def test_strip_links_empty():
    import orchestrator
    assert orchestrator.strip_links("") == ""


def test_strip_links_compresses_newlines():
    import orchestrator
    out = orchestrator.strip_links("A\n\n\nB")
    assert "\n\n" not in out
    assert "A" in out and "B" in out


def test_get_affiliate_url_known_product():
    import orchestrator
    url = orchestrator.get_affiliate_url("キュレル泡洗顔")
    assert url.startswith("https://www.amazon.co.jp/")
    assert "tag=rikocosmelab-22" in url


def test_get_affiliate_url_unknown_returns_default():
    import orchestrator
    url = orchestrator.get_affiliate_url("存在しない商品XYZ_zzz")
    assert url == orchestrator._DEFAULT_URL


def test_counter_roundtrip(monkeypatch, tmp_path):
    import orchestrator
    p = tmp_path / "counter.txt"
    monkeypatch.setattr(orchestrator, "COUNTER_PATH", p)
    orchestrator.write_counter(7)
    assert orchestrator.read_counter() == 7


def test_counter_missing_returns_zero(monkeypatch, tmp_path):
    import orchestrator
    p = tmp_path / "nope.txt"
    monkeypatch.setattr(orchestrator, "COUNTER_PATH", p)
    assert orchestrator.read_counter() == 0


def test_cycle_counter_roundtrip(monkeypatch, tmp_path):
    import orchestrator
    p = tmp_path / "cycle.json"
    monkeypatch.setattr(orchestrator, "CYCLE_COUNTER_PATH", p)
    orchestrator.write_cycle_counter(3)
    assert orchestrator.read_cycle_counter() == 3


def test_cycle_counter_missing_fallback(monkeypatch, tmp_path):
    import orchestrator
    p = tmp_path / "missing.json"
    monkeypatch.setattr(orchestrator, "CYCLE_COUNTER_PATH", p)
    val = orchestrator.read_cycle_counter()
    assert isinstance(val, int)
    assert val >= 0


def test_winning_patterns_is_valid_json():
    root = Path(__file__).resolve().parent.parent
    candidates = [root / "winning_patterns.json", root / "agents" / "cache" / "winning_patterns.json"]
    found = [p for p in candidates if p.exists()]
    assert found, "winning_patterns.json not found"
    for p in found:
        json.loads(p.read_text(encoding="utf-8"))
