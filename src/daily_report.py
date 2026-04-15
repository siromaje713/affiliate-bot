"""affiliate-bot 日次パフォーマンスレポートを Slack に送信する。

データソース:
- Threads API: フォロワー数 / 投稿エンゲージメント
- data/post_log.json: 今日の投稿type/score
- data/search_keywords.json: あれば集計（無ければスキップ）
- data/dynamic_distribution.json: あれば差分計算（無ければスキップ）
- agents.conversation_agent / replied users: あればエンゲージリプ集計

データ取得失敗箇所はスキップし、レポートは可能な範囲で送る。
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, date, timedelta
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

API_BASE = "https://graph.threads.net/v1.0"
DATA_DIR = ROOT / "data"
POST_LOG = DATA_DIR / "post_log.json"
SEARCH_KW = DATA_DIR / "search_keywords.json"
DYN_DIST = DATA_DIR / "dynamic_distribution.json"
DYN_DIST_SNAPSHOT = DATA_DIR / "dynamic_distribution_yesterday.json"
FOLLOWERS_SNAPSHOT = DATA_DIR / "followers_yesterday.json"
REPLIED_USERS = DATA_DIR / "replied_users.json"
CONVERSATIONS = DATA_DIR / "conversations.json"

POST_TYPE_LABEL = {
    "engage": "engage型",
    "list": "list型（保存型リスト）",
    "link": "アフィリ型",
    "buzz": "buzz型",
    "knowledge": "知識暴露型",
    "correction": "行動訂正型",
    "method": "やり方暴露型",
    "ane": "姉シリーズ",
}


def _safe_load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, data) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logger.exception("snapshot保存失敗 %s", path)


def _token() -> str | None:
    return os.environ.get("THREADS_ACCESS_TOKEN")


def _get_followers() -> int | None:
    token = _token()
    if not token:
        return None
    try:
        me = requests.get(f"{API_BASE}/me", params={"access_token": token}, timeout=15)
        me.raise_for_status()
        uid = me.json()["id"]
        r = requests.get(
            f"{API_BASE}/{uid}/threads_insights",
            params={"metric": "followers_count", "access_token": token},
            timeout=15,
        )
        if r.status_code != 200:
            return None
        for item in r.json().get("data", []):
            if item.get("name") == "followers_count":
                vals = item.get("values") or item.get("total_value", {}).get("value")
                if isinstance(vals, list) and vals:
                    return int(vals[0].get("value", 0))
                if isinstance(vals, int):
                    return vals
        return None
    except Exception:
        logger.exception("フォロワー取得失敗")
        return None


def _post_engagement(post_id: str) -> tuple[int | None, int | None]:
    token = _token()
    if not token or not post_id:
        return None, None
    try:
        r = requests.get(
            f"{API_BASE}/{post_id}",
            params={"fields": "like_count,replies_count", "access_token": token},
            timeout=10,
        )
        if r.status_code != 200:
            return None, None
        j = r.json()
        return j.get("like_count"), j.get("replies_count")
    except Exception:
        return None, None


def _get_today_posts_engagement() -> list[dict]:
    log = _safe_load_json(POST_LOG, [])
    today = date.today().isoformat()
    today_log = [e for e in log if (e.get("posted_at") or "").startswith(today)]
    results = []
    for e in today_log:
        likes, replies = _post_engagement(e.get("post_id", ""))
        results.append({
            "post_type": e.get("post_type") or "engage",
            "likes": likes,
            "replies": replies,
        })
    return results


def _top3_post_types(days: int = 7) -> list[tuple[str, float]]:
    log = _safe_load_json(POST_LOG, [])
    cutoff = datetime.now() - timedelta(days=days)
    sums: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for e in log:
        try:
            ts = datetime.fromisoformat(e["posted_at"])
        except Exception:
            continue
        if ts < cutoff:
            continue
        ptype = e.get("post_type") or "engage"
        likes, replies = _post_engagement(e.get("post_id", ""))
        likes = likes or 0
        replies = replies or 0
        sums[ptype] += likes + replies * 2
        counts[ptype] += 1
    ranked = []
    for t, total in sums.items():
        n = counts[t]
        ranked.append((t, total / n if n else 0.0))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked[:3]


def _engage_stats() -> tuple[int, int]:
    replied = _safe_load_json(REPLIED_USERS, {})
    today = date.today().isoformat()
    sent = sum(1 for v in replied.values() if isinstance(v, dict) and v.get("date") == today)
    conv = _safe_load_json(CONVERSATIONS, {})
    got = sum(1 for v in conv.values() if isinstance(v, dict) and v.get("date") == today)
    return sent, got


def _keyword_stats() -> dict | None:
    data = _safe_load_json(SEARCH_KW, None)
    if not data:
        return None
    kws = data.get("keywords", [])
    actives = [k for k in kws if float(k.get("score", 0)) > 0.05]
    actives.sort(key=lambda k: float(k.get("score", 0)), reverse=True)
    auto_added_today = [
        k["word"] for k in kws
        if k.get("category") == "auto" and (k.get("last_used") or "").startswith(date.today().isoformat())
    ]
    return {
        "active": len(actives),
        "total": len(kws),
        "top": [(k["word"], round(float(k["score"]), 2)) for k in actives[:2]],
        "auto_added": auto_added_today,
    }


def _distribution_diff() -> list[tuple[str, float, float]]:
    cur = _safe_load_json(DYN_DIST, {})
    prev = _safe_load_json(DYN_DIST_SNAPSHOT, {})
    if not cur:
        return []
    diffs = []
    for t, v in cur.items():
        old = prev.get(t, v)
        diffs.append((t, float(old), float(v)))
    diffs.sort(key=lambda x: abs(x[2] - x[1]), reverse=True)
    return diffs[:4]


def build_report() -> str:
    today_str = date.today().strftime("%-m/%-d")
    lines = [f"📊 affiliate-bot 日次レポート（{today_str}）", ""]

    cur_followers = _get_followers()
    prev_data = _safe_load_json(FOLLOWERS_SNAPSHOT, {})
    prev = prev_data.get("count")
    if cur_followers is not None:
        diff = (cur_followers - prev) if isinstance(prev, int) else None
        diff_str = f" (+{diff})" if diff is not None and diff >= 0 else (f" ({diff})" if diff is not None else "")
        lines.append(f"▶ フォロワー: {cur_followers}{diff_str}")
        _save_json(FOLLOWERS_SNAPSHOT, {"count": cur_followers, "date": date.today().isoformat()})

    posts = _get_today_posts_engagement()
    if posts:
        lines.append(f"▶ 今日の投稿: {len(posts)}本")
        for p in posts:
            label = POST_TYPE_LABEL.get(p["post_type"], p["post_type"])
            likes = p.get("likes")
            replies = p.get("replies")
            metrics = f"likes {likes} / replies {replies}" if likes is not None else "metrics取得失敗"
            lines.append(f"  - {label} → {metrics}")

    sent, got = _engage_stats()
    if sent or got:
        lines.append(f"▶ エンゲージリプ: {sent}件送信 / {got}件返信あり")

    top3 = _top3_post_types()
    if top3:
        lines.append("▶ 投稿型TOP3（過去7日）:")
        for i, (t, score) in enumerate(top3, 1):
            label = POST_TYPE_LABEL.get(t, t)
            lines.append(f"  {i}. {label} → avg engagement {score:.1f}")

    kw = _keyword_stats()
    if kw:
        lines.append("▶ keyword_manager:")
        lines.append(f"  - アクティブKW: {kw['active']}/{kw['total']}")
        if kw["top"]:
            top_str = " ".join(f"「{w}」(score {s})" for w, s in kw["top"])
            lines.append(f"  - 今日のTOP: {top_str}")
        if kw["auto_added"]:
            words = "、".join(f"「{w}」" for w in kw["auto_added"][:3])
            lines.append(f"  - 自動追加: +{len(kw['auto_added'])}（{words}）")

    diffs = _distribution_diff()
    if diffs:
        lines.append("▶ dynamic_distribution変動:")
        for t, old, new in diffs:
            if abs(new - old) < 0.005:
                continue
            arrow = "↑" if new > old else "↓"
            label = POST_TYPE_LABEL.get(t, t)
            lines.append(f"  - {label}: {old*100:.0f}% → {new*100:.0f}% {arrow}")
        cur_dist = _safe_load_json(DYN_DIST, {})
        if cur_dist:
            _save_json(DYN_DIST_SNAPSHOT, cur_dist)

    return "\n".join(lines)


def send_report() -> None:
    try:
        report = build_report()
    except Exception:
        logger.exception("レポート生成失敗")
        return
    try:
        from slack_notify import notify
        notify("daily_report", report)
        logger.info("日次レポート送信完了 (%d chars)", len(report))
    except Exception:
        logger.exception("レポート送信失敗")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    send_report()
