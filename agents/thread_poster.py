"""スレッド投稿エージェント：1投稿を5連リプライチェーンで展開する"""
import json
import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv
from utils.claude_cli import ask_json

load_dotenv()

BASE_URL = "https://graph.threads.net/v1.0"


def _get_token() -> str:
    return os.environ["THREADS_ACCESS_TOKEN"]


def _get_user_id() -> str:
    return os.environ["THREADS_USER_ID"]


def _create_container(text: str, reply_to_id: str = None) -> str:
    """投稿またはリプライコンテナを作成してIDを返す"""
    params = {
        "media_type": "TEXT",
        "text": text,
        "access_token": _get_token(),
    }
    if reply_to_id:
        params["reply_to_id"] = reply_to_id

    resp = requests.post(
        f"{BASE_URL}/{_get_user_id()}/threads",
        params=params,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def _publish(container_id: str) -> str:
    """コンテナを公開して投稿IDを返す"""
    resp = requests.post(
        f"{BASE_URL}/{_get_user_id()}/threads_publish",
        params={
            "creation_id": container_id,
            "access_token": _get_token(),
        },
    )
    resp.raise_for_status()
    return resp.json()["id"]


def _generate_thread_texts(product_name: str, hook: str, season_context: str) -> list[str]:
    """Claudeで5投稿分のテキストを生成する（各100文字以内）"""
    season_note = f"季節感: {season_context}\n" if season_context else ""
    prompt = f"""美容アカウント「りこ」として、{product_name}について5連投稿のスレッドを作成してください。

{season_note}1投稿目のフック: {hook}

ルール:
- 各投稿は100文字以内
- 1投稿目: 掴み（フック）
- 2投稿目: 問題提起・共感
- 3投稿目: 商品の特徴・解決策
- 4投稿目: 使用感・体験談風
- 5投稿目: まとめ・行動促進（「詳細はリプ欄」と入れる）
- 絵文字は各2個以内
- URLは含めない
- NGワード: 最安値、絶対、必ず

JSON形式で返してください:
{{"posts": ["投稿1テキスト", "投稿2テキスト", "投稿3テキスト", "投稿4テキスト", "投稿5テキスト"]}}"""

    result = ask_json(prompt)
    posts = result.get("posts", [])
    if len(posts) != 5:
        raise ValueError(f"5投稿生成できませんでした（{len(posts)}件）")
    return posts


def post_thread(product_name: str, hook: str, season_context: str = "") -> dict:
    """5連リプライチェーンで投稿する"""
    print(f"[ThreadPoster] スレッド生成中: {product_name}")
    texts = _generate_thread_texts(product_name, hook, season_context)

    post_ids = []
    prev_id = None

    for i, text in enumerate(texts, 1):
        print(f"[ThreadPoster] {i}/5 投稿中: {text[:30]}...")
        container_id = _create_container(text, reply_to_id=prev_id)
        time.sleep(3)
        post_id = _publish(container_id)
        post_ids.append(post_id)
        prev_id = post_id
        print(f"[ThreadPoster] {i}/5 完了: post_id={post_id}")
        if i < 5:
            time.sleep(2)

    print(f"[ThreadPoster] スレッド投稿完了: {len(post_ids)}件")
    return {"post_ids": post_ids, "product_name": product_name}
