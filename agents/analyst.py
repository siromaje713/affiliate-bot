"""アナリストエージェント：投稿メトリクス収集・改善サイクル"""
import json
from pathlib import Path
from datetime import datetime, timedelta
from utils import threads_api
from utils.claude_cli import ask_json, MODEL_OPUS

LOG_PATH = Path(__file__).parent.parent / "data" / "post_log.json"
REPORT_PATH = Path(__file__).parent.parent / "data" / "analytics_report.json"


def load_log() -> list:
    if not LOG_PATH.exists():
        return []
    return json.loads(LOG_PATH.read_text(encoding="utf-8"))


def fetch_metrics_for_recent_posts(hours: int = 24) -> list[dict]:
    """直近N時間の投稿のメトリクスを取得する"""
    log = load_log()
    cutoff = datetime.now() - timedelta(hours=hours)
    results = []
    for entry in log:
        posted_at = datetime.fromisoformat(entry["posted_at"])
        if posted_at < cutoff:
            continue
        try:
            insights = threads_api.get_post_insights(entry["post_id"])
            metrics = {item["name"]: item["values"][0]["value"] for item in insights.get("data", [])}
            results.append({**entry, "metrics": metrics})
        except Exception as e:
            print(f"[Analyst] メトリクス取得失敗 {entry['post_id']}: {e}")
    return results


def generate_improvement_report(posts_with_metrics: list[dict]) -> dict:
    """メトリクスをもとに改善案を生成する"""
    if not posts_with_metrics:
        return {"summary": "データなし", "improvements": [], "tomorrow_theme": "スキンケア基本"}

    sorted_posts = sorted(
        posts_with_metrics,
        key=lambda x: x.get("metrics", {}).get("likes", 0),
        reverse=True,
    )
    summary_text = "\n".join([
        f"- [{p['posted_at'][:10]}] いいね:{p.get('metrics',{}).get('likes',0)} 「{p['text'][:40]}...」"
        for p in sorted_posts[:3]
    ])

    prompt = f"""美容アフィリエイトアカウント(@riko_cosme_lab)の直近投稿トップ3です。

{summary_text}

共通パターンを分析して明日の投稿改善案を3つ出してください。
JSONのみで返してください（説明不要）：
{{"top_patterns": ["パターン1", "パターン2"], "improvements": ["改善案1", "改善案2", "改善案3"], "tomorrow_theme": "明日のテーマ"}}"""

    try:
        return ask_json(prompt, model=MODEL_OPUS)
    except Exception as e:
        print(f"[Analyst] レポート生成エラー: {e}")
        return {"summary": "解析失敗", "improvements": [], "tomorrow_theme": ""}


def run(hours: int = 24) -> dict:
    """アナリスト実行。レポートを返してdata/analytics_report.jsonに保存。"""
    print(f"[Analyst] 直近{hours}時間の投稿メトリクスを収集中...")
    posts = fetch_metrics_for_recent_posts(hours)
    print(f"[Analyst] {len(posts)}件のデータを取得")

    print("[Analyst] 改善レポート生成中...")
    report = generate_improvement_report(posts)
    report["generated_at"] = datetime.now().isoformat()
    report["posts_analyzed"] = len(posts)

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Analyst] レポート保存: {REPORT_PATH}")
    return report
