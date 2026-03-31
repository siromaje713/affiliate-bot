"""ベンチマークアカウントのThreadsページをPlaywrightでスクレイプして
直近N日のバズ投稿をwinning_patterns.jsonに保存する

使い方:
  python3 scripts/scrape_benchmark.py [--accounts a,b,c] [--days 7] [--limit 50]
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WINNING_PATTERNS_PATH = Path(__file__).parent.parent / "agents" / "cache" / "winning_patterns.json"

_EXTRACT_JS = """
() => {
    const posts = [];
    const times = document.querySelectorAll('time[datetime]');
    times.forEach(t => {
        let container = t;
        for (let i = 0; i < 15; i++) {
            container = container.parentElement;
            if (!container) break;
            const textSpans = container.querySelectorAll('span[dir=auto]');
            if (textSpans.length >= 1) {
                let bestText = '';
                textSpans.forEach(s => {
                    if (s.innerText && s.innerText.length > bestText.length) bestText = s.innerText;
                });
                let likes = '0';
                const allSvgs = container.querySelectorAll('svg');
                allSvgs.forEach(svg => {
                    const label = svg.getAttribute('aria-label') || '';
                    if (label.includes('いいね')) {
                        const btn = svg.closest('div') || svg.parentElement;
                        if (btn) {
                            btn.querySelectorAll('span').forEach(s => {
                                const txt = (s.innerText || '').trim();
                                if (txt && /^[0-9][0-9,\\.]*[KkMm万千]?$/.test(txt)) {
                                    likes = txt;
                                }
                            });
                        }
                    }
                });
                if (bestText.length > 10) {
                    posts.push({text: bestText.substring(0, 300), likes, datetime: t.getAttribute('datetime')});
                    break;
                }
            }
        }
    });
    return posts;
}
"""


def _get_accounts() -> list:
    raw = os.getenv("BENCHMARK_ACCOUNT_IDS", "")
    return [e.strip() for e in raw.split(",") if e.strip()]


def _load_patterns() -> list:
    if WINNING_PATTERNS_PATH.exists():
        try:
            return json.loads(WINNING_PATTERNS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_patterns(patterns: list):
    WINNING_PATTERNS_PATH.parent.mkdir(parents=True, exist_ok=True)
    WINNING_PATTERNS_PATH.write_text(
        json.dumps(patterns, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _parse_like_count(text: str) -> int:
    text = text.strip().replace(",", "").replace(" ", "")
    if not text or text == "0":
        return 0
    try:
        m = re.match(r"([\d.]+)([KkMm万千]?)", text)
        if not m:
            return 0
        num = float(m.group(1))
        suffix = m.group(2).lower()
        if suffix == "k":
            num *= 1000
        elif suffix == "m":
            num *= 1_000_000
        elif suffix == "万":
            num *= 10000
        elif suffix == "千":
            num *= 1000
        return int(num)
    except Exception:
        return 0


def scrape_account(page, account: str, days: int, scroll_limit: int) -> list:
    url = f"https://www.threads.com/@{account}"
    print(f"[Scraper] {account}: {url} を開いています...")

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        print(f"[Scraper] {account}: ページ読み込み失敗 → {e}")
        return []

    time.sleep(4)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    results = []
    seen_texts = set()
    scroll_count = 0
    stall_count = 0
    last_count = 0
    hit_old_post = False

    while scroll_count < scroll_limit and not hit_old_post:
        posts_data = page.evaluate(_EXTRACT_JS)

        for item in posts_data:
            text = item.get("text", "").strip()
            ts = item.get("datetime", "")
            if not text or text in seen_texts:
                continue

            # 期間フィルタ
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if dt < cutoff:
                        hit_old_post = True
                        continue
                except Exception:
                    pass

            like_count = _parse_like_count(item.get("likes", "0"))
            seen_texts.add(text)
            results.append({
                "source": "scrape",
                "account": account,
                "like_count": like_count,
                "hook_text": text[:50],
                "full_text": text,
                "post_date": ts,
            })

        print(f"[Scraper] {account}: スクロール{scroll_count+1}回目 / 累計{len(results)}件")

        if len(results) == last_count:
            stall_count += 1
            if stall_count >= 3:
                print(f"[Scraper] {account}: 新規投稿なし3回連続 → 終了")
                break
        else:
            stall_count = 0
        last_count = len(results)

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2.5)
        scroll_count += 1

    print(f"[Scraper] {account}: 完了 {len(results)}件取得")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--accounts", default="", help="カンマ区切りアカウント名")
    parser.add_argument("--days", type=int, default=7, help="直近N日（デフォルト7）")
    parser.add_argument("--limit", type=int, default=50, help="最大スクロール回数（デフォルト50）")
    parser.add_argument("--min-likes", type=int, default=0, help="いいね最低数フィルタ")
    args = parser.parse_args()

    accounts = [a.strip() for a in args.accounts.split(",") if a.strip()] if args.accounts else _get_accounts()
    if not accounts:
        print("アカウントが指定されていません（--accounts または BENCHMARK_ACCOUNT_IDS）")
        sys.exit(1)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("pip install playwright && playwright install chromium")
        sys.exit(1)

    all_new = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 390, "height": 844},
            locale="ja-JP",
        )
        page = context.new_page()

        for account in accounts:
            posts = scrape_account(page, account, args.days, args.limit)
            all_new.extend(posts)

        browser.close()

    # いいね数でソート
    all_new.sort(key=lambda x: x["like_count"], reverse=True)

    if args.min_likes > 0:
        all_new = [p for p in all_new if p["like_count"] >= args.min_likes]

    # 既存データと重複除去してマージ
    existing = _load_patterns()
    existing_texts = {p.get("full_text", "") for p in existing}
    new_only = [p for p in all_new if p["full_text"] not in existing_texts]
    merged = existing + new_only

    _save_patterns(merged)

    print(f"\n[Scraper] 完了: 新規{len(new_only)}件追加 / 合計{len(merged)}件")
    if all_new:
        print("\n上位5件:")
        for i, item in enumerate(all_new[:5], 1):
            print(f"  {i}. ❤️{item['like_count']} @{item['account']} 「{item['hook_text']}」")


if __name__ == "__main__":
    main()
