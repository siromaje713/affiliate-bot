import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_slack_notify_no_webhook(monkeypatch):
    import slack_notify
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    assert slack_notify.notify("success", "test message") is False


def test_github_sync_import():
    import github_sync  # noqa: F401


def test_pipeline_csv_has_required_headers():
    p = ROOT / "docs" / "pipeline.csv"
    assert p.exists()
    with p.open(encoding="utf-8") as f:
        headers = next(csv.reader(f))
    assert "atom_id" in headers
    assert "status" in headers


def test_outputs_csv_has_required_headers():
    p = ROOT / "docs" / "outputs.csv"
    assert p.exists()
    with p.open(encoding="utf-8") as f:
        headers = next(csv.reader(f))
    assert "atom_id" in headers
    assert "status" in headers


def test_post_log_is_valid_json():
    p = ROOT / "data" / "post_log.json"
    assert p.exists()
    json.loads(p.read_text(encoding="utf-8"))


def test_buzz_patterns_is_valid_json():
    p = ROOT / "data" / "buzz_patterns.json"
    assert p.exists()
    json.loads(p.read_text(encoding="utf-8"))
