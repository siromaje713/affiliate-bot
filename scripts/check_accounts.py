"""
ベンチマークアカウントの有効性チェック + 新候補の確認

使い方:
  # 現在設定済みアカウントをチェック
  python3 scripts/check_accounts.py

  # 候補アカウントをチェック
  python3 scripts/check_accounts.py --accounts @cosme_jp,_._.cosme._._,b_room_official

  # チェック後にRender + GitHub Secretsを一括更新
  python3 scripts/check_accounts.py --accounts valid1,valid2 --update
"""
import argparse
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()


def check_accounts(accounts: list) -> dict:
    """Playwrightで各アカウントページの存在を確認"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("pip install playwright && playwright install chromium")
        sys.exit(1)

    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ja-JP",
        )
        page = context.new_page()
        for account in accounts:
            account = account.lstrip("@").strip()
            url = f"https://www.threads.com/@{account}"
            print(f"[Check] {url} ...", end=" ", flush=True)
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=20000)
                time.sleep(2)
                # 投稿数を確認
                posts = page.evaluate("""
                    () => document.querySelectorAll('time[datetime]').length
                """)
                status_code = resp.status if resp else 0
                if status_code == 404 or posts == 0:
                    # ページテキストで404確認
                    body = page.inner_text("body")[:200]
                    if "404" in body or "見つかりません" in body or "not found" in body.lower():
                        results[account] = {"status": "❌ 404/存在しない", "posts": 0}
                    elif posts == 0:
                        results[account] = {"status": "⚠️ 投稿0件（非公開か新規）", "posts": 0}
                    else:
                        results[account] = {"status": "✅ 有効", "posts": posts}
                else:
                    results[account] = {"status": "✅ 有効", "posts": posts}
            except Exception as e:
                results[account] = {"status": f"❌ エラー: {e}", "posts": 0}
            print(results[account]["status"])
        browser.close()
    return results


def update_render_and_secrets(valid_accounts: list):
    """有効なアカウントをRenderとGitHub Secretsに反映"""
    import json
    import urllib.request
    import base64

    account_str = ",".join(valid_accounts)
    render_api_key = os.environ.get("RENDER_API_KEY", "")
    gh_pat = os.environ.get("GH_PAT", "")
    if not render_api_key:
        print("[Error] RENDER_API_KEY が未設定です")
        return
    if not gh_pat:
        print("[Error] GH_PAT が未設定です")
    services = ["crn-d72ovqm3jp1c7386q0fg", "crn-d741a6q4d50c73bvbavg"]

    # Render更新
    for svc in services:
        ex_req = urllib.request.Request(
            f"https://api.render.com/v1/services/{svc}/env-vars",
            headers={"Authorization": f"Bearer {render_api_key}", "Accept": "application/json"}
        )
        with urllib.request.urlopen(ex_req, timeout=15) as r:
            existing = json.loads(r.read())
        env_map = {item["envVar"]["key"]: item["envVar"]["value"] for item in existing}
        env_map["BENCHMARK_ACCOUNT_IDS"] = account_str
        payload = json.dumps([{"key": k, "value": v} for k, v in env_map.items()]).encode()
        put_req = urllib.request.Request(
            f"https://api.render.com/v1/services/{svc}/env-vars",
            data=payload,
            method="PUT",
            headers={"Authorization": f"Bearer {render_api_key}", "Content-Type": "application/json", "Accept": "application/json"}
        )
        with urllib.request.urlopen(put_req, timeout=15) as r:
            r.read()
        print(f"[Render] {svc}: BENCHMARK_ACCOUNT_IDS={account_str}")

    # GitHub Secrets更新
    try:
        from nacl.public import PublicKey, SealedBox
        key_req = urllib.request.Request(
            "https://api.github.com/repos/siromaje713/affiliate-bot/actions/secrets/public-key",
            headers={"Authorization": f"Bearer {gh_pat}", "Accept": "application/vnd.github+json"}
        )
        with urllib.request.urlopen(key_req, timeout=15) as r:
            key_data = json.loads(r.read())
        key_id = key_data["key_id"]
        pub_key = base64.b64decode(key_data["key"])
        box = SealedBox(PublicKey(pub_key))
        encrypted = base64.b64encode(box.encrypt(account_str.encode())).decode()
        secret_req = urllib.request.Request(
            "https://api.github.com/repos/siromaje713/affiliate-bot/actions/secrets/BENCHMARK_ACCOUNT_IDS",
            data=json.dumps({"encrypted_value": encrypted, "key_id": key_id}).encode(),
            method="PUT",
            headers={"Authorization": f"Bearer {gh_pat}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(secret_req, timeout=15) as r:
            r.read()
        print(f"[GitHub Secrets] BENCHMARK_ACCOUNT_IDS={account_str}")
    except Exception as e:
        print(f"[GitHub Secrets] 更新失敗: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--accounts", default="", help="チェックするアカウント（カンマ区切り）")
    parser.add_argument("--update", action="store_true", help="有効アカウントをRender+Secretsに反映")
    args = parser.parse_args()

    if args.accounts:
        accounts = [a.strip().lstrip("@") for a in args.accounts.split(",") if a.strip()]
    else:
        raw = os.getenv("BENCHMARK_ACCOUNT_IDS", "")
        accounts = [a.strip() for a in raw.split(",") if a.strip()]

    if not accounts:
        print("アカウントを指定してください: --accounts @account1,@account2")
        sys.exit(1)

    print(f"\n{len(accounts)}件のアカウントをチェック中...\n")
    results = check_accounts(accounts)

    valid = [a for a, r in results.items() if "✅" in r["status"]]
    invalid = [a for a, r in results.items() if "✅" not in r["status"]]

    print(f"\n{'='*40}")
    print(f"✅ 有効: {len(valid)}件 → {', '.join(valid) if valid else 'なし'}")
    print(f"❌ 無効: {len(invalid)}件 → {', '.join(invalid) if invalid else 'なし'}")

    if args.update and valid:
        print(f"\nRender + GitHub Secrets を更新中...")
        update_render_and_secrets(valid)
        print("✅ 更新完了")
    elif args.update and not valid:
        print("\n有効なアカウントが0件のため更新をスキップ")

    if invalid:
        print(f"\n💡 有効なアカウントを探すには:")
        print("  threads.com で「スキンケア」「美容」などを検索")
        print("  フォロワー1万人以上・投稿頻度高・美容ジャンルのアカウントを選ぶ")
        print(f"  確認後: python3 scripts/check_accounts.py --accounts @new1,@new2 --update")


if __name__ == "__main__":
    main()
