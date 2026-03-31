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
MAX_REPLIES_PER_RUN = 3


def _get_token() -> str:
    return os.environ["THREADS_ACCESS_TOKEN"]


def _get_user_id() -> str:
    return os.environ["THREADS_USER_ID"]


def _get_benchmark_ids() -> list:
    ids = os.getenv("BENCHMARK_ACCOUNT_IDS", "")
    return [i.strip() for i in ids.split(",") if i.strip()]


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
            "fields": "id,text,timestamp",
            "limit": 5,
            "access_token": _get_token(),
        },
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def _generate_empathy_reply(post_text: str) -> str:
    prompt = f"""美容アカウント「りこ」として、以下の投稿に共感リプライを生成してください。

投稿: {post_text[:200]}

ルール:
- 50文字以内
- 宣伝・商品紹介は絶対にNG
- 自然な共感・応援・励まし
- 絵文字1〜2個
- 親しみやすい口調

リプライテキストのみ返してください（説明不要）"""
    return ask(prompt)


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


def run() -> list:
    """ベンチマークアカウントの最新投稿に最大3件共感リプライを送る"""
    benchmark_ids = _get_benchmark_ids()
    if not benchmark_ids:
        print("[EngageAgent] BENCHMARK_ACCOUNT_IDSが未設定 → スキップ")
        return []

    engaged_ids = _load_engaged_ids()
    results = []

    for account_id in benchmark_ids:
        if len(results) >= MAX_REPLIES_PER_RUN:
            break
        try:
            posts = _get_recent_posts(account_id)
        except Exception as e:
            print(f"[EngageAgent] アカウント{account_id} 取得失敗: {e}")
            continue

        for post in posts:
            if len(results) >= MAX_REPLIES_PER_RUN:
                break
            post_id = post["id"]
            post_text = post.get("text", "")
            if not post_text or post_id in engaged_ids:
                continue

            try:
                reply_text = _generate_empathy_reply(post_text)
                _post_reply(post_id, reply_text)
                _save_engaged_id(post_id)
                results.append({"post_id": post_id, "post_text": post_text, "reply": reply_text})
                print(f"[EngageAgent] リプライ完了: {post_id} → {reply_text[:30]}...")
                time.sleep(2)
            except Exception as e:
                print(f"[EngageAgent] リプライ失敗 {post_id}: {e}")

    print(f"[EngageAgent] 完了: 計{len(results)}件")
    return results
