"""エンゲージエージェント：ベンチマークアカウントの最新投稿に共感リプライ
Threads APIにキーワード検索エンドポイントは存在しないため、
.envのBENCHMARK_ACCOUNT_IDSで指定したアカウントの最新投稿にリプライする。
"""
import base64
import json
import os
import time
from datetime import datetime, timedelta, timezone
import requests
from pathlib import Path
from dotenv import load_dotenv
from utils.claude_cli import ask

load_dotenv()

BASE_URL = "https://graph.threads.net/v1.0"
ENGAGED_IDS_PATH = Path("/tmp/engaged_post_ids.json")
SENT_REPLIES_PATH = Path("data/sent_replies.json")
DYNAMIC_BENCHMARKS_PATH = Path("data/dynamic_benchmarks.json")
MAX_REPLIES_PER_RUN = 5
MIN_LIKES_THRESHOLD = 30
DISCOVERY_LIMIT_PER_RUN = 5
REVALIDATION_LIMIT_PER_RUN = 5
REVALIDATION_STALE_DAYS = 14
GITHUB_REPO = os.getenv("GITHUB_REPO", "siromaje713/affiliate-bot")
DYNAMIC_BENCHMARKS_GH_PATH = "data/dynamic_benchmarks.json"
# リプ対象から除外するusername（小文字で比較）
ENGAGE_EXCLUDE = {"popo.biyou", "riko_cosme_lab"}


def _get_token() -> str:
    return os.environ["THREADS_ACCESS_TOKEN"]


def _get_user_id() -> str:
    return os.environ["THREADS_USER_ID"]


def _lookup_user_id(username: str):
    """Threads検索APIでユーザー名から数値IDを取得する"""
    try:
        resp = requests.get(
            f"{BASE_URL}/search",
            params={
                "q": username,
                "type": "USER",
                "fields": "id,username",
                "access_token": _get_token(),
            },
        )
        resp.raise_for_status()
        for u in resp.json().get("data", []):
            if u.get("username", "").lower() == username.lower():
                print(f"[EngageAgent] {username} → ID: {u['id']}")
                return u["id"]
    except Exception as e:
        print(f"[EngageAgent] ユーザーID検索失敗 {username}: {type(e).__name__}")
    return None


def _get_benchmark_ids() -> list:
    """dynamic_benchmarks.jsonから数値IDを取得する。空ならenvのBENCHMARK_ACCOUNT_IDSでseedする"""
    data = _load_dynamic_benchmarks()
    accounts = data.get("accounts", [])

    # 初回起動: envからpermanent=Trueでseed
    if not accounts:
        raw = os.getenv("BENCHMARK_ACCOUNT_IDS", "")
        today = datetime.now().strftime("%Y-%m-%d")
        for entry in [e.strip() for e in raw.split(",") if e.strip()]:
            accounts.append({
                "username": entry,
                "added_at": today,
                "permanent": True,
                "top_likes": 0,
                "last_checked": today,
            })
        if accounts:
            data["accounts"] = accounts
            _save_dynamic_benchmarks(data)
            print(f"[EngageAgent] dynamic_benchmarks.json初期化: {len(accounts)}件")

    ids = []
    for a in accounts:
        uname = a.get("username", "")
        if not uname:
            continue
        if uname.lower() in ENGAGE_EXCLUDE:
            print(f"[EngageAgent] 除外: {uname}")
            continue
        # 優先: user_idフィールド（手動設定済み数値ID）
        uid = str(a.get("user_id", "") or "").strip()
        if uid.isdigit():
            ids.append(uid)
            continue
        if uname.isdigit():
            ids.append(uname)
            continue
        # 検索API(/search)は400エラーのため使わない。未設定はスキップ
        print(f"[EngageAgent] user_id未設定: {uname} → dynamic_benchmarks.jsonに数値IDを手動設定してください")
    return ids


def _load_engaged_ids() -> set:
    if ENGAGED_IDS_PATH.exists():
        try:
            return set(json.loads(ENGAGED_IDS_PATH.read_text(encoding="utf-8")).get("ids", []))
        except Exception:
            pass
    return set()


def _save_engaged_id(post_id: str):
    ids = _load_engaged_ids()
    ids.add(post_id)
    ENGAGED_IDS_PATH.write_text(
        json.dumps({"ids": list(ids)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _get_recent_posts(account_id: str) -> list:
    resp = requests.get(
        f"{BASE_URL}/{account_id}/threads",
        params={
            "fields": "id,text,timestamp,like_count,replies_count",
            "limit": 10,
            "access_token": _get_token(),
        },
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def _load_dynamic_benchmarks() -> dict:
    """dynamic_benchmarks.jsonを読み込む。GitHub contents APIから取得し、失敗時はローカル→デフォルト"""
    default = {"accounts": [], "max_pool_size": 50, "min_likes_threshold": 100}
    gh_pat = os.getenv("GH_PAT")
    if gh_pat:
        try:
            r = requests.get(
                f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DYNAMIC_BENCHMARKS_GH_PATH}",
                headers={"Authorization": f"token {gh_pat}", "Accept": "application/vnd.github+json"},
                timeout=10,
            )
            if r.status_code == 200:
                payload = r.json()
                content = base64.b64decode(payload["content"]).decode("utf-8")
                data = json.loads(content)
                data["_sha"] = payload["sha"]
                return data
            else:
                print(f"[EngageAgent] GitHub load非200: {r.status_code}")
        except Exception as e:
            print(f"[EngageAgent] GitHub load例外: {type(e).__name__}")
    if DYNAMIC_BENCHMARKS_PATH.exists():
        try:
            return json.loads(DYNAMIC_BENCHMARKS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def _save_dynamic_benchmarks(data: dict):
    """ローカル保存 + GitHub contents APIでpush"""
    sha = data.pop("_sha", None)
    DYNAMIC_BENCHMARKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(data, ensure_ascii=False, indent=2)
    DYNAMIC_BENCHMARKS_PATH.write_text(body, encoding="utf-8")

    gh_pat = os.getenv("GH_PAT")
    if not gh_pat:
        print("[EngageAgent] GH_PAT未設定 → ローカル保存のみ")
        return
    try:
        content_b64 = base64.b64encode(body.encode("utf-8")).decode("utf-8")
        payload = {
            "message": "chore: update dynamic_benchmarks.json",
            "content": content_b64,
            "branch": "main",
        }
        if sha:
            payload["sha"] = sha
        r = requests.put(
            f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DYNAMIC_BENCHMARKS_GH_PATH}",
            headers={"Authorization": f"token {gh_pat}", "Accept": "application/vnd.github+json"},
            json=payload,
            timeout=15,
        )
        if r.status_code in (200, 201):
            print("[EngageAgent] dynamic_benchmarks.json → GitHub push成功")
        else:
            print(f"[EngageAgent] GitHub push失敗: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"[EngageAgent] GitHub push例外: {type(e).__name__}")


def _fetch_user_top_likes(account_id: str) -> int:
    """直近10件の最高like_countを返す"""
    try:
        posts = _get_recent_posts(account_id)
        if not posts:
            return 0
        return max(int(p.get("like_count", 0) or 0) for p in posts)
    except Exception as e:
        print(f"[EngageAgent] top_likes取得失敗 {account_id}: {type(e).__name__}")
        return 0


def _fetch_user_14day_top_likes(account_id: str) -> int:
    """直近14日の最大like_count"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    try:
        posts = _get_recent_posts(account_id)
        top = 0
        for p in posts:
            ts = p.get("timestamp", "")
            try:
                post_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if post_dt >= cutoff:
                    top = max(top, int(p.get("like_count", 0) or 0))
            except Exception:
                continue
        return top
    except Exception:
        return 0


def _fetch_user_30day_likes_sum(account_id: str) -> int:
    """直近30日のlike_count合計"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    try:
        posts = _get_recent_posts(account_id)
        total = 0
        for p in posts:
            ts = p.get("timestamp", "")
            try:
                post_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if post_dt >= cutoff:
                    total += int(p.get("like_count", 0) or 0)
            except Exception:
                continue
        return total
    except Exception:
        return 0


def _get_post_repliers(post_id: str) -> list:
    """投稿へのリプから、自分以外のユーザー情報を収集"""
    try:
        resp = requests.get(
            f"{BASE_URL}/{post_id}/replies",
            params={"fields": "id,from", "access_token": _get_token()},
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        my_id = _get_user_id()
        repliers = []
        seen = set()
        for r in resp.json().get("data", []):
            frm = r.get("from", {}) or {}
            rid = str(frm.get("id", ""))
            uname = frm.get("username", "")
            if not rid or not uname:
                continue
            if rid == my_id or uname in seen:
                continue
            seen.add(uname)
            repliers.append({"id": rid, "username": uname})
        return repliers
    except Exception as e:
        print(f"[EngageAgent] replies取得失敗 {post_id}: {type(e).__name__}")
        return []


def _discover_new_benchmarks(engaged_post_ids: list):
    """リプした投稿のリプ者から新規ベンチマーク候補を発見＋既存の再検証"""
    data = _load_dynamic_benchmarks()
    accounts = data.get("accounts", [])
    min_likes = int(data.get("min_likes_threshold", 100))
    max_pool = int(data.get("max_pool_size", 50))
    today = datetime.now().strftime("%Y-%m-%d")
    drop_messages = []

    # --- 再検証: last_checkedが14日以上前のアカウント ---
    stale_cutoff = datetime.now() - timedelta(days=REVALIDATION_STALE_DAYS)
    revalidated = 0
    kept_accounts = []
    for a in accounts:
        if revalidated >= REVALIDATION_LIMIT_PER_RUN:
            kept_accounts.append(a)
            continue
        last_checked_str = a.get("last_checked", "")
        try:
            last_dt = datetime.strptime(last_checked_str, "%Y-%m-%d") if last_checked_str else None
        except Exception:
            last_dt = None
        if not last_dt or last_dt >= stale_cutoff:
            kept_accounts.append(a)
            continue

        uname = a.get("username", "")
        uid = _lookup_user_id(uname)
        time.sleep(1)
        if not uid:
            kept_accounts.append(a)
            continue
        top14 = _fetch_user_14day_top_likes(uid)
        time.sleep(1)
        revalidated += 1
        a["last_checked"] = today
        a["top_likes"] = max(int(a.get("top_likes", 0) or 0), top14)
        if top14 < min_likes:
            if a.get("permanent"):
                print(f"[EngageAgent] revalidate (permanent keep): {uname} 14d_top={top14}")
                kept_accounts.append(a)
            else:
                drop_messages.append(f"{uname} を削除しました。理由: {REVALIDATION_STALE_DAYS}日間いいね{min_likes}+なし")
                print(f"[EngageAgent] revalidate drop: {uname} 14d_top={top14}")
        else:
            print(f"[EngageAgent] revalidate pass: {uname} 14d_top={top14}")
            kept_accounts.append(a)
    accounts = kept_accounts
    if revalidated:
        print(f"[EngageAgent] revalidate完了: {revalidated}件検証")

    # --- 新規発見: リプした投稿のリプ者から ---
    known = {a.get("username", "").lower() for a in accounts}
    candidates = []
    seen_cand = set()
    for post_id in engaged_post_ids:
        for r in _get_post_repliers(post_id):
            uname_lc = r["username"].lower()
            if uname_lc in ENGAGE_EXCLUDE:
                continue
            if uname_lc in known or uname_lc in seen_cand:
                continue
            seen_cand.add(uname_lc)
            candidates.append(r)
        time.sleep(1)

    added = 0
    checked = 0
    for cand in candidates:
        if checked >= DISCOVERY_LIMIT_PER_RUN:
            break
        checked += 1
        top_likes = _fetch_user_top_likes(cand["id"])
        time.sleep(1)
        if top_likes < min_likes:
            print(f"[EngageAgent] discover skip: {cand['username']} top_likes={top_likes}")
            continue
        accounts.append({
            "username": cand["username"],
            "added_at": today,
            "permanent": False,
            "top_likes": top_likes,
            "last_checked": today,
        })
        added += 1
        print(f"[EngageAgent] discover add: {cand['username']} top_likes={top_likes}")

    # --- 上限超過時は非permanent分を直近30日いいね合計が低い順にドロップ ---
    if len(accounts) > max_pool:
        perm = [a for a in accounts if a.get("permanent")]
        non_perm = [a for a in accounts if not a.get("permanent")]
        for a in non_perm:
            uid = _lookup_user_id(a.get("username", ""))
            a["_drop_score"] = _fetch_user_30day_likes_sum(uid) if uid else 0
            time.sleep(1)
        non_perm.sort(key=lambda x: x.get("_drop_score", 0), reverse=True)
        keep_count = max(0, max_pool - len(perm))
        dropped = non_perm[keep_count:]
        kept = non_perm[:keep_count]
        for a in kept:
            a.pop("_drop_score", None)
        for a in dropped:
            uname = a.get("username", "")
            score = a.get("_drop_score", 0)
            print(f"[EngageAgent] pool drop: {uname} 30d_likes={score}")
            drop_messages.append(f"{uname} を削除しました。理由: pool上限超過（30日いいね合計 {score}）")
        accounts = perm + kept
        print(f"[EngageAgent] pool trimmed → {len(accounts)}件")

    data["accounts"] = accounts
    _save_dynamic_benchmarks(data)
    print(f"[EngageAgent] discover完了: 新規{added}件追加 / pool合計{len(accounts)}件")

    # --- Slack通知: ドロップしたアカウント ---
    if drop_messages:
        try:
            from slack_notify import notify as slack_notify
            for msg in drop_messages:
                slack_notify("info", f"🗑 {msg}")
        except Exception as e:
            print(f"[EngageAgent] slack notify失敗: {type(e).__name__}")


def _load_sent_replies() -> dict:
    """sent_replies.json: {post_id: {reply_id, replied_back: bool}}"""
    if SENT_REPLIES_PATH.exists():
        try:
            return json.loads(SENT_REPLIES_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_sent_replies(data: dict):
    SENT_REPLIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    SENT_REPLIES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _generate_empathy_reply(post_text: str) -> str:
    prompt = f"""美容アカウント「りこ」として、以下の投稿に対して関係を作るリプライを1つ生成して。

【3パターンからどれか1つ選んで生成】
A. 言い換え型：相手の投稿の本質を一言で言い換える（例：「それって結局○○ってことよね」）
B. 共感+一撃型：自分の経験を絡めて共感+鋭い一言（例：「わかる、私も○○だった。で気づいたのが○○」）
C. 問い型：相手が思わず返信したくなる問いで終わる（例：「それって○○の時もそう感じた？」）

【口調ルール】
- 相手の投稿が敬語・丁寧語 → こちらも敬語で合わせる
- 相手の投稿がタメ口・カジュアル → こちらもタメ口で合わせる
- 絵文字1個

【絶対ルール】
- 20〜35字
- 宣伝・自分のアカウントへの誘導禁止
- 「素晴らしい」「すごい」だけで終わる一言禁止
- 相手の投稿内容を具体的に拾うこと

投稿：{post_text[:300]}

リプライ文のみ返して。"""
    text = ask(prompt).strip().strip('"').strip("'").strip("「").strip("」")
    return text


def _generate_close_reply(my_reply: str, their_reply: str) -> str:
    prompt = f"""自分のリプ「{my_reply}」に相手から「{their_reply[:150]}」と返信が来た。
柔らかいクローズリプを生成してください。

【厳守ルール】
- 15〜25文字
- 感謝・共感で会話を自然に締める
- 質問はしない
- 絵文字1個まで
- 例: 「教えてくれてありがとう！参考にする🙌」

リプライ本文のみ返してください（説明・引用符不要）"""
    return ask(prompt).strip().strip('"').strip("'").strip("「").strip("」")


def _post_reply(post_id: str, text: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/{_get_user_id()}/threads",
        params={
            "media_type": "TEXT",
            "text": text,
            "reply_to_id": post_id,
            "access_token": _get_token(),
        },
    )
    resp.raise_for_status()
    container_id = resp.json()["id"]
    time.sleep(3)
    resp = requests.post(
        f"{BASE_URL}/{_get_user_id()}/threads_publish",
        params={"creation_id": container_id, "access_token": _get_token()},
    )
    resp.raise_for_status()
    return resp.json()["id"]


def _check_and_send_close_replies():
    """sent_replies.jsonを見て、こちらのリプに相手から返信が来ていたらクローズリプを返す"""
    sent = _load_sent_replies()
    closed_count = 0
    for post_id, info in list(sent.items()):
        if not isinstance(info, dict):
            continue
        if info.get("closed"):
            continue
        my_reply_id = info.get("reply_id")
        if not my_reply_id:
            continue
        try:
            # 自分のリプライへの返信を取得
            resp = requests.get(
                f"{BASE_URL}/{my_reply_id}/replies",
                params={"fields": "id,text,from", "access_token": _get_token()},
                timeout=10,
            )
            if resp.status_code != 200:
                continue
            replies = resp.json().get("data", [])
            my_user_id = _get_user_id()
            their_replies = [r for r in replies if str(r.get("from", {}).get("id", "")) != my_user_id]
            if not their_replies:
                continue
            their_text = their_replies[0].get("text", "")
            if not their_text:
                continue
            close_text = _generate_close_reply(info.get("my_reply", ""), their_text)
            _post_reply(my_reply_id, close_text)
            info["closed"] = True
            info["close_reply"] = close_text
            sent[post_id] = info
            closed_count += 1
            print(f"[EngageAgent] クローズリプ送信: {post_id} → {close_text}")
            time.sleep(2)
        except Exception as e:
            print(f"[EngageAgent] クローズリプ失敗 {post_id}: {type(e).__name__}")
    if closed_count:
        _save_sent_replies(sent)
    print(f"[EngageAgent] クローズリプ {closed_count}件送信")


def run() -> list:
    """ベンチマークアカウントのいいね30+投稿に最大5件リプ→クローズリプ自動返信"""
    benchmark_ids = _get_benchmark_ids()
    if not benchmark_ids:
        print("[EngageAgent] BENCHMARK_ACCOUNT_IDSが未設定 → スキップ")
        return []

    # まず既存のリプに返信が来てたらクローズリプを返す
    try:
        _check_and_send_close_replies()
    except Exception as e:
        print(f"[EngageAgent] クローズリプ処理失敗: {type(e).__name__}")

    engaged_ids = _load_engaged_ids()
    sent_replies = _load_sent_replies()
    engaged_ids.update(sent_replies.keys())
    results = []

    for account_id in benchmark_ids:
        if len(results) >= MAX_REPLIES_PER_RUN:
            break
        try:
            posts = _get_recent_posts(account_id)
        except Exception as e:
            print(f"[EngageAgent] アカウント{account_id} 取得失敗: {type(e).__name__}")
            continue

        # いいね数でソート→上位を狙う
        posts.sort(key=lambda x: x.get("like_count", 0), reverse=True)

        for post in posts:
            if len(results) >= MAX_REPLIES_PER_RUN:
                break
            post_id = post["id"]
            post_text = post.get("text", "")
            like_count = post.get("like_count", 0)
            if not post_text or post_id in engaged_ids:
                continue
            if like_count < MIN_LIKES_THRESHOLD:
                continue

            try:
                reply_text = _generate_empathy_reply(post_text)
                reply_id = _post_reply(post_id, reply_text)
                _save_engaged_id(post_id)
                sent_replies[post_id] = {
                    "reply_id": reply_id,
                    "my_reply": reply_text,
                    "closed": False,
                    "post_text": post_text[:100],
                }
                _save_sent_replies(sent_replies)
                results.append({"post_id": post_id, "post_text": post_text, "reply": reply_text, "likes": like_count})
                print(f"[EngageAgent] リプ完了: ❤️{like_count} {post_id} → {reply_text[:30]}")
                time.sleep(2)
            except Exception as e:
                print(f"[EngageAgent] リプ失敗 {post_id}: {type(e).__name__}")

    print(f"[EngageAgent] 完了: 計{len(results)}件")

    # 新規ベンチマーク発見（リプした投稿のリプ者から）
    try:
        engaged_post_ids = [r["post_id"] for r in results if r.get("post_id")]
        _discover_new_benchmarks(engaged_post_ids)
    except Exception as e:
        print(f"[EngageAgent] discover処理失敗: {type(e).__name__}")

    return results
