#!/usr/bin/env python3
"""
aggregate_dashboard.py
======================
hoshi-musubi 占いbot ダッシュボード用のデータ集約スクリプト。
GitHub Actions cron (15分おき) から呼ばれる想定。

各種APIから値を引いて dashboard/data.json に書き出す。
失敗した項目は前回値を保持する (best-effort)。

必須環境変数:
- THREADS_ACCESS_TOKEN   : Threads Graph API トークン
- THREADS_USER_ID        : Threads ユーザーID
- GITHUB_TOKEN           : workflow実行履歴・commit取得用 (Actions が自動付与)
- GITHUB_REPOSITORY      : "siromaje713/hoshi-musubi" (Actions が自動付与)

任意環境変数:
- ANTHROPIC_ADMIN_KEY    : 残高取得 (なければスキップ)
- RENDER_API_KEY         : Render稼働状態 (なければスキップ)
- RENDER_SERVICE_ID      : srv-d7brc0dm5p6s73f4eobg
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

JST = timezone(timedelta(hours=9))
NOW = datetime.now(JST)

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = REPO_ROOT / "dashboard" / "data.json"
TASKS_PATH = REPO_ROOT / "dashboard" / "tasks.json"
MISSIONS_PATH = REPO_ROOT / "dashboard" / "missions.json"


# ──────────────────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────────────────
def log(msg: str) -> None:
    print(f"[{NOW.strftime('%H:%M:%S')}] {msg}", flush=True)


def safe(fn, default=None, label="?"):
    """fn() を呼んで例外なら default を返す。"""
    try:
        return fn()
    except Exception as e:
        log(f"⚠ {label} failed: {e}")
        return default


def load_prev_data() -> dict:
    if DATA_PATH.exists():
        try:
            return json.loads(DATA_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def load_tasks() -> list[dict]:
    if TASKS_PATH.exists():
        try:
            return json.loads(TASKS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def load_missions() -> list[dict]:
    if MISSIONS_PATH.exists():
        try:
            return json.loads(MISSIONS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


# ──────────────────────────────────────────────────────────
# Threads API
# ──────────────────────────────────────────────────────────
def fetch_threads_data() -> dict:
    token = os.getenv("THREADS_ACCESS_TOKEN")
    user_id_env = os.getenv("THREADS_USER_ID")
    if not (token and user_id_env):
        log("⚠ Threads creds missing, skip")
        return {}

    # /me から実 user_id を取得 (buzz_researcher.py と同じ方式 — secret の THREADS_USER_ID
    # は post 用途と一致しないケースがあるため信用しない)
    r = requests.get(
        "https://graph.threads.net/v1.0/me",
        params={
            "fields": "id,username",
            "access_token": token,
        },
        timeout=15,
    )
    r.raise_for_status()
    me = r.json()
    user_id = me.get("id") or user_id_env
    base = f"https://graph.threads.net/v1.0/{user_id}"

    # followers_countはuser_insightsで取る (sinceが必須)
    from datetime import datetime as _dt
    since_ts = int((NOW - timedelta(days=2)).timestamp())
    until_ts = int(NOW.timestamp())

    followers = 0
    try:
        r_fc = requests.get(
            f"{base}/threads_insights",
            params={
                "metric": "followers_count",
                "since": since_ts,
                "until": until_ts,
                "access_token": token,
            },
            timeout=15,
        )
        if r_fc.status_code == 200:
            js = r_fc.json()
            for m in js.get("data", []):
                if m.get("name") == "followers_count":
                    # followers_count は total_value で来る
                    tv = m.get("total_value", {})
                    if tv:
                        followers = tv.get("value", 0)
                    else:
                        # values配列で来る場合
                        vals = m.get("values", [])
                        if vals:
                            followers = vals[-1].get("value", 0)
    except Exception as e:
        log(f"⚠ followers_count fetch failed: {e}")

    # 直近の投稿 (limit 100) — fields は buzz_researcher と揃えて permalink を外す
    r2 = requests.get(
        f"{base}/threads",
        params={
            "fields": "id,timestamp",
            "limit": 100,
            "access_token": token,
        },
        timeout=15,
    )
    r2.raise_for_status()
    posts = r2.json().get("data", [])

    cutoff_24h = NOW - timedelta(hours=24)
    posts_24h = 0
    for p in posts:
        ts = p.get("timestamp", "")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(JST)
            if dt >= cutoff_24h:
                posts_24h += 1
        except Exception:
            pass

    return {
        "followers": followers,
        "posts_24h": posts_24h,
        "posts_total_sampled": len(posts),
    }


# ──────────────────────────────────────────────────────────
# GitHub API (workflow runs, commits)
# ──────────────────────────────────────────────────────────
def fetch_github_data() -> dict:
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY", "siromaje713/hoshi-musubi")
    if not token:
        log("⚠ GITHUB_TOKEN missing, skip")
        return {}

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # 直近workflow runs (20件)
    r = requests.get(
        f"https://api.github.com/repos/{repo}/actions/runs",
        headers=headers,
        params={"per_page": 20},
        timeout=15,
    )
    r.raise_for_status()
    runs = r.json().get("workflow_runs", [])

    recent_workflows = []
    success = 0
    total = 0
    for run in runs[:10]:
        status = run.get("conclusion") or run.get("status") or "unknown"
        recent_workflows.append({
            "name": run.get("name", "?"),
            "status": status,
            "at": run.get("updated_at", ""),
            "url": run.get("html_url", ""),
        })
        if run.get("conclusion") in ("success", "failure"):
            total += 1
            if run["conclusion"] == "success":
                success += 1
    cron_success_rate = round(success / total * 100, 1) if total else 100.0

    # 直近7日のcommit数
    since = (NOW - timedelta(days=7)).isoformat()
    r2 = requests.get(
        f"https://api.github.com/repos/{repo}/commits",
        headers=headers,
        params={"since": since, "per_page": 100},
        timeout=15,
    )
    r2.raise_for_status()
    commits_7d = len(r2.json())

    return {
        "recent_workflows": recent_workflows,
        "cron_success_rate": cron_success_rate,
        "commits_7d": commits_7d,
    }


# ──────────────────────────────────────────────────────────
# Anthropic 残高 (Admin API)
# ──────────────────────────────────────────────────────────
def fetch_anthropic_balance() -> float | None:
    key = os.getenv("ANTHROPIC_ADMIN_KEY")
    if not key:
        return None
    # 公式の残高エンドポイントは Admin API 経由。
    # 仕様変動があるので best-effort。失敗時は None を返して前回値維持。
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    try:
        r = requests.get(
            "https://api.anthropic.com/v1/organizations/usage_report/messages",
            headers=headers,
            timeout=10,
        )
        if r.status_code == 200:
            # 残高そのものは公式APIで出ない場合があるため、
            # ここでは "取得可" のシグナルとして 0 以上の値を仮置きする。
            # 正確な残高は ANTHROPIC_BALANCE_USD 環境変数で手動上書きも可。
            override = os.getenv("ANTHROPIC_BALANCE_USD")
            if override:
                return float(override)
            return None
    except Exception:
        pass

    # 環境変数で手動指定された値があれば優先
    override = os.getenv("ANTHROPIC_BALANCE_USD")
    if override:
        try:
            return float(override)
        except ValueError:
            return None
    return None


# ──────────────────────────────────────────────────────────
# Render 稼働状態
# ──────────────────────────────────────────────────────────
def fetch_render_status() -> str | None:
    key = os.getenv("RENDER_API_KEY")
    svc = os.getenv("RENDER_SERVICE_ID")
    if not (key and svc):
        return None
    try:
        r = requests.get(
            f"https://api.render.com/v1/services/{svc}",
            headers={"Authorization": f"Bearer {key}"},
            timeout=10,
        )
        if r.status_code == 200:
            js = r.json()
            return js.get("suspended", "not_suspended")
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────────────────
# Mission / Task 評価
# ──────────────────────────────────────────────────────────
def get_nested(d: dict, dotted_key: str) -> Any:
    cur = d
    for k in dotted_key.split("."):
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    return cur


def evaluate_missions(missions: list[dict], data: dict) -> list[dict]:
    results = []
    for m in missions:
        target = m.get("target", 0)
        current_key = m.get("current_key", "")
        current = get_nested(data, current_key) if current_key else 0
        if current is None:
            current = 0
        progress = min(100, round(current / target * 100, 1)) if target else 0
        results.append({
            **m,
            "current": current,
            "progress": progress,
            "completed": current >= target,
        })
    return results


# ──────────────────────────────────────────────────────────
# Level / XP 算出
# ──────────────────────────────────────────────────────────
def compute_level(followers: int, posts_total: int, engage_count: int) -> dict:
    """
    レベル算出ロジック (仮):
    XP = followers + posts_total * 5 + engage_count * 2
    Lv n に必要な XP = n * 750 (累積)
    """
    xp_total = followers + posts_total * 5 + engage_count * 2
    level = 1
    xp_for_next = 750
    accum = 0
    while accum + xp_for_next <= xp_total:
        accum += xp_for_next
        level += 1
        xp_for_next = level * 750
    return {
        "level": level,
        "xp": xp_total - accum,
        "xp_next": xp_for_next,
    }


# ──────────────────────────────────────────────────────────
# Main aggregation
# ──────────────────────────────────────────────────────────
def main() -> int:
    log("=== aggregate_dashboard.py start ===")
    prev = load_prev_data()
    tasks = load_tasks()
    missions = load_missions()

    threads = safe(fetch_threads_data, {}, "Threads") or {}
    gh = safe(fetch_github_data, {}, "GitHub") or {}
    anth_balance = safe(fetch_anthropic_balance, None, "Anthropic")
    render_status = safe(fetch_render_status, None, "Render")

    # 前回値フォールバック
    followers = threads.get("followers") or prev.get("kpi", {}).get("followers", 0)
    posts_24h = threads.get("posts_24h", 0)
    posts_total_sampled = threads.get("posts_total_sampled", 0)
    # posts_total は累積。Threads APIで全件取れない場合に備えて 前回値+今回新規 で近似
    prev_posts_total = prev.get("kpi", {}).get("posts_total", 0)
    posts_total = max(prev_posts_total, posts_total_sampled)

    commits_7d = gh.get("commits_7d", 0)
    cron_success_rate = gh.get("cron_success_rate", 100.0)
    recent_workflows = gh.get("recent_workflows", [])

    # placeholder で取れないものは前回値 or 仮値
    engage_count_7d = prev.get("departments", {}).get("sales", {}).get("value", 0)
    buzz_candidates = prev.get("departments", {}).get("strategy", {}).get("value", 0)
    avg_ctr = prev.get("departments", {}).get("analytics", {}).get("value", 0.0)
    line_friends = prev.get("departments", {}).get("hr", {}).get("value", 0)

    # KPI / Level
    lvl = compute_level(followers, posts_total, engage_count_7d)

    # アラート組み立て
    alerts = []
    if anth_balance is not None and anth_balance < 10:
        alerts.append({"level": "warning", "dept": "general",
                       "msg": f"API残高 ${anth_balance:.2f} — 補充検討"})
    failed_recent = [w for w in recent_workflows[:5] if w["status"] == "failure"]
    if failed_recent:
        alerts.append({"level": "error", "dept": "dev",
                       "msg": f"直近workflow失敗 {len(failed_recent)}件"})
    if posts_24h == 0:
        alerts.append({"level": "error", "dept": "pr",
                       "msg": "過去24h投稿なし — cron停止疑い"})

    # 履歴(7日) - 前回履歴に今日分を追記する設計
    hist = prev.get("history_7d", {"posts": [], "engage": [], "followers": []})
    today_key = NOW.strftime("%Y-%m-%d")
    last_key = prev.get("history_last_date", "")
    if last_key != today_key:
        # 日付が変わったので push
        hist["posts"] = (hist.get("posts", []) + [posts_24h])[-7:]
        hist["engage"] = (hist.get("engage", []) + [engage_count_7d])[-7:]
        hist["followers"] = (hist.get("followers", []) + [followers])[-7:]

    # データ組み立て
    data = {
        "updated_at": NOW.isoformat(),
        "kpi": {
            "level": lvl["level"],
            "xp": lvl["xp"],
            "xp_next": lvl["xp_next"],
            "happiness": min(100, int(cron_success_rate)),  # cron健康度を幸福度とする
            "tasks_done": sum(1 for t in tasks if t.get("done")),
            "tasks_total": len(tasks),
            "posts_total": posts_total,
            "followers": followers,
            "profit_per_sec": 248,  # placeholder (Stripe接続後に実値)
            "profit_cumulative": prev.get("kpi", {}).get("profit_cumulative", 0) + 248,
        },
        "departments": {
            "sales":     {"level": 9, "progress": 72, "metric": "engage_count_7d", "value": engage_count_7d},
            "strategy":  {"level": 7, "progress": 58, "metric": "buzz_candidates", "value": buzz_candidates},
            "analytics": {"level": 8, "progress": 60, "metric": "avg_ctr",         "value": avg_ctr},
            "dev":       {"level": 8, "progress": min(100, commits_7d * 4), "metric": "commits_7d", "value": commits_7d},
            "hr":        {"level": 7, "progress": 55, "metric": "line_friends",    "value": line_friends},
            "general":   {"level": 7, "progress": int(cron_success_rate * 0.7), "metric": "cron_success_rate", "value": cron_success_rate},
            "pr":        {"level": 6, "progress": min(100, posts_24h * 25), "metric": "posts_24h", "value": posts_24h},
        },
        "alerts": alerts,
        "next_post": estimate_next_post(),
        "infra": {
            "anthropic_balance_usd": anth_balance,
            "render_status": render_status,
            "recent_workflows": recent_workflows[:5],
        },
        "timeline": build_timeline(recent_workflows, posts_24h),
        "history_7d": hist,
        "history_last_date": today_key,
        "tasks": tasks,
        "missions": [],  # 下で埋める
    }

    # ミッション評価 (data 全体に対して)
    data["missions"] = evaluate_missions(missions, data)

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log(f"✓ wrote {DATA_PATH} (followers={followers}, posts_24h={posts_24h}, alerts={len(alerts)})")
    return 0


def estimate_next_post() -> dict:
    """JST 09/12/15/19 のうち次に来る時刻を返す"""
    schedule = [9, 12, 15, 19]
    now = NOW
    for h in schedule:
        candidate = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if candidate > now:
            return {
                "scheduled_at": candidate.isoformat(),
                "type": {9: "morning", 12: "noon", 15: "afternoon", 19: "evening"}[h],
            }
    # 全部過ぎてたら翌日09:00
    tomorrow = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    return {"scheduled_at": tomorrow.isoformat(), "type": "morning"}


def build_timeline(recent_workflows: list[dict], posts_24h: int) -> list[dict]:
    timeline = []
    for w in recent_workflows[:8]:
        icon = "✅" if w["status"] == "success" else "❌" if w["status"] == "failure" else "⏳"
        at = w.get("at", "")
        try:
            t = datetime.fromisoformat(at.replace("Z", "+00:00")).astimezone(JST).strftime("%H:%M")
        except Exception:
            t = "??:??"
        timeline.append({"at": t, "icon": icon, "text": f"{w['name']}"})
    return timeline


if __name__ == "__main__":
    sys.exit(main())
