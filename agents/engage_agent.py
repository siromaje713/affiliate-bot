"""エンゲージエージェント：ベンチマークアカウントの最新投稿に共感リプライ
Threads APIにキーワード検索エンドポイントは存在しないため、
.envのBENCHMARK_ACCOUNT_IDSで指定したアカウントの最新投稿にリプライする。
"""
import json
import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv
from utils.claude_cli import ask

load_dotenv()

BASE_URL = "https://graph.threads.net/v1.0"
ENGAGED_IDS_PATH = Path("/tmp/engaged_post_ids.json")
SENT_REPLIES_PATH = Path("data/sent_replies.json")
MAX_REPLIES_PER_RUN = 5
MIN_LIKES_THRESHOLD = 30


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
        print(f"[EngageAgent] ユーザーID検索失敗 {username}: {e}")
    return None


def _get_benchmark_ids() -> list:
    """BENCHMARK_ACCOUNT_IDSから数値IDを取得する。ユーザー名は自動でID変換する"""
    raw = os.getenv("BENCHMARK_ACCOUNT_IDS", "")
    ids = []
    for entry in [e.strip() for e in raw.split(",") if e.strip()]:
        if entry.isdigit():
            ids.append(entry)
        else:
            uid = _lookup_user_id(entry)
            if uid:
                ids.append(uid)
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
    prompt = f"""美容アカウント「りこ」として、以下の投稿に短い共感リプを生成してください。

投稿: {post_text[:200]}

【厳守ルール】
- 20〜30文字（必須）
- 共感・体験談・質問返しのいずれかのトーン
- 宣伝・商品名・URL一切なし
- 絵文字1個まで
- 親しみやすいタメ口
- 例: 「わかる！私も同じだった〜どう変わった？」「それやってみたい！何分くらいかけてる？」

リプライ本文のみ返してください（説明・引用符不要）"""
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
            print(f"[EngageAgent] クローズリプ失敗 {post_id}: {e}")
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
        print(f"[EngageAgent] クローズリプ処理失敗: {e}")

    engaged_ids = _load_engaged_ids()
    sent_replies = _load_sent_replies()
    results = []

    for account_id in benchmark_ids:
        if len(results) >= MAX_REPLIES_PER_RUN:
            break
        try:
            posts = _get_recent_posts(account_id)
        except Exception as e:
            print(f"[EngageAgent] アカウント{account_id} 取得失敗: {e}")
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
                print(f"[EngageAgent] リプ失敗 {post_id}: {e}")

    print(f"[EngageAgent] 完了: 計{len(results)}件")
    return results
