"""
scripts/cowork_research.py
Threadsベンチマークアカウントを巡回して直近48時間のいいね100+投稿を収集し
docs/research_YYYYMMDD.json を生成してGitHubにpushする。

実行:
    python3 scripts/cowork_research.py

環境変数:
    BENCHMARK_ACCOUNT_IDS : カンマ区切りアカウント名（デフォルト設定済み）
    ANTHROPIC_API_KEY     : Claude API（フック分析用）
    GH_PAT                : GitHub Personal Access Token
    GITHUB_REPO           : owner/repo 形式（例: siromaje713/affiliate-bot）
"""
import base64
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

BENCHMARK_ACCOUNTS = os.environ.get(
    "BENCHMARK_ACCOUNT_IDS",
    "popo.biyou,km.room,momo_cosme_b,kajierimakeup,ior_coco",
).split(",")

JST = timezone(timedelta(hours=9))


# ── Playwright でThreadsページから投稿を収集 ────────────────────────────


def _scrape_account(page, account):
    """1アカウントの投稿一覧を取得する。失敗時は空リスト。"""
    posts = []
    try:
        url = f"https://www.threads.net/@{account.strip()}"
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # 投稿が描画されるまで待機
        time.sleep(4)

        # 投稿テキストを抽出（Threadsのarticle要素）
        articles = page.query_selector_all("article")
        for art in articles[:20]:
            text_el = art.query_selector("span, p")
            text = text_el.inner_text().strip() if text_el else ""
            if len(text) < 10:
                continue

            # いいね数（aria-labelまたはspan内の数字）
            likes = 0
            like_el = art.query_selector("[aria-label*='like'], [aria-label*='いいね']")
            if like_el:
                label = like_el.get_attribute("aria-label") or ""
                m = re.search(r"(\d[\d,]*)", label)
                if m:
                    likes = int(m.group(1).replace(",", ""))
            # aria-labelになければspan内の数字を探す
            if likes == 0:
                spans = art.query_selector_all("span")
                for sp in spans:
                    t = sp.inner_text().strip()
                    if re.match(r"^\d+$", t) and int(t) > 0:
                        likes = int(t)
                        break

            posts.append({"text": text[:300], "likes": likes})

    except Exception as e:
        print(f"[Research] {account} スクレイプ失敗: {e}", file=sys.stderr)

    return posts


def scrape_all_accounts():
    """全アカウントを巡回して投稿リストを返す"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[Research] playwright未インストール: pip install playwright && playwright install chromium")
        return []

    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="ja-JP",
        )
        page = ctx.new_page()

        for account in BENCHMARK_ACCOUNTS:
            account = account.strip()
            print(f"[Research] {account} 収集中...")
            posts = _scrape_account(page, account)
            high_likes = [p for p in posts if p["likes"] >= 100]
            print(f"[Research] {account}: {len(posts)}件取得 / いいね100+: {len(high_likes)}件")
            results.append({"account": account, "posts": posts, "high_likes": high_likes})
            time.sleep(2)

        browser.close()

    return results


# ── Claude API でフック分析 ──────────────────────────────────────────────


def analyze_with_claude(account_results):
    """収集した投稿をClaude Haikuで分析してフック・感情トリガーを抽出する"""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("[Research] ANTHROPIC_API_KEY未設定 → 分析スキップ")
        return [], []

    # いいね100+投稿のテキストをまとめる
    high_like_texts = []
    for ar in account_results:
        for p in ar.get("high_likes", []):
            hook = p["text"].split("\n")[0][:60]
            high_like_texts.append(f"[{ar['account']}] いいね{p['likes']}: {hook}")

    if not high_like_texts:
        # 100+がなければ全投稿から上位を使う
        all_posts = []
        for ar in account_results:
            for p in ar.get("posts", []):
                all_posts.append((p["likes"], ar["account"], p["text"]))
        all_posts.sort(reverse=True)
        high_like_texts = [
            f"[{acc}] いいね{lk}: {txt.split(chr(10))[0][:60]}"
            for lk, acc, txt in all_posts[:15]
        ]

    if not high_like_texts:
        return [], []

    try:
        import urllib.request
        prompt = f"""美容系Threads投稿の分析をしてください。

投稿サンプル:
{chr(10).join(high_like_texts[:20])}

以下をJSON形式で返してください（コードブロック不要）:
{{
  "top_hooks": ["フックパターン（冒頭の言い回し）を5個"],
  "emotion_triggers": ["感情を動かすワードを5個"]
}}"""

        body = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 500,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        text = result["content"][0]["text"].strip()
        parsed = json.loads(text)
        return parsed.get("top_hooks", []), parsed.get("emotion_triggers", [])
    except Exception as e:
        print(f"[Research] Claude分析エラー: {e}", file=sys.stderr)
        return [], []


# ── GitHub Contents API でpush ───────────────────────────────────────────


def push_to_github(filename, content_str):
    """GitHub Contents APIでファイルをpushする"""
    import urllib.request
    import urllib.error

    gh_pat = os.environ.get("GH_PAT", "")
    repo = os.environ.get("GITHUB_REPO", "siromaje713/affiliate-bot")
    if not gh_pat:
        print("[Research] GH_PAT未設定 → GitHubへのpushをスキップ")
        return False

    path = f"docs/{filename}"
    api_url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"token {gh_pat}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }

    # 既存ファイルのSHAを取得（更新時に必要）
    sha = None
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req) as r:
            sha = json.loads(r.read()).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"[Research] SHA取得エラー: {e}")

    encoded = base64.b64encode(content_str.encode("utf-8")).decode("ascii")
    body = {"message": f"auto: {filename} 更新", "content": encoded}
    if sha:
        body["sha"] = sha

    try:
        req = urllib.request.Request(
            api_url,
            data=json.dumps(body).encode(),
            headers=headers,
            method="PUT",
        )
        with urllib.request.urlopen(req) as r:
            print(f"[Research] GitHub push完了: {path} (HTTP {r.status})")
            return True
    except Exception as e:
        print(f"[Research] GitHub pushエラー: {e}", file=sys.stderr)
        return False


# ── メイン ──────────────────────────────────────────────────────────────


def main():
    today = datetime.now(JST).strftime("%Y%m%d")
    print(f"[Research] 開始: {today} / アカウント: {BENCHMARK_ACCOUNTS}")

    # 収集
    account_results = scrape_all_accounts()

    # いいね100+投稿を整形
    accounts_out = []
    for ar in account_results:
        high = ar.get("high_likes", [])
        accounts_out.append({
            "account": ar["account"],
            "posts": [
                {"text": p["text"], "likes": p["likes"], "hook": p["text"].split("\n")[0][:60]}
                for p in high
            ],
        })

    # Claude分析
    top_hooks, emotion_triggers = analyze_with_claude(account_results)

    # JSON生成
    output = {
        "date": datetime.now(JST).strftime("%Y-%m-%d"),
        "accounts": accounts_out,
        "top_hooks": top_hooks,
        "emotion_triggers": emotion_triggers,
    }
    content_str = json.dumps(output, ensure_ascii=False, indent=2)
    filename = f"research_{today}.json"

    # ローカル保存
    os.makedirs("docs", exist_ok=True)
    local_path = os.path.join("docs", filename)
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(content_str)
    print(f"[Research] ローカル保存: {local_path}")

    # GitHubにpush
    push_to_github(filename, content_str)
    print("[Research] 完了")


if __name__ == "__main__":
    main()
