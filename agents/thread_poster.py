"""スレッド投稿エージェント：1投稿を3連リプライチェーンで展開、末尾にアフィリエイトリプ"""
import os
import time
import requests
from dotenv import load_dotenv
from utils.claude_cli import ask_json

load_dotenv()

BASE_URL = "https://graph.threads.net/v1.0"


def _get_token() -> str:
    return os.environ["THREADS_ACCESS_TOKEN"]


def _get_user_id() -> str:
    return os.environ["THREADS_USER_ID"]


def _create_container(text: str, reply_to_id: str = None) -> str:
    params = {
        "media_type": "TEXT",
        "text": text,
        "access_token": _get_token(),
    }
    if reply_to_id:
        params["reply_to_id"] = reply_to_id
    resp = requests.post(f"{BASE_URL}/{_get_user_id()}/threads", params=params)
    resp.raise_for_status()
    return resp.json()["id"]


def _publish(container_id: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/{_get_user_id()}/threads_publish",
        params={"creation_id": container_id, "access_token": _get_token()},
    )
    resp.raise_for_status()
    return resp.json()["id"]


def _generate_thread_texts(product_name: str, hook: str, season_context: str) -> list:
    """Claudeで3投稿分のテキストを生成する（各100文字以内）"""
    season_note = f"季節感: {season_context}\n" if season_context else ""
    prompt = f"""美容アカウント「りこ」として、{product_name}について3連投稿のスレッドを作成してください。

{season_note}1投稿目のフック: {hook}

構成:
- 1/3: 強いフック（数字・体験・before/after）＋続きを読ませる引き
- 2/3: 具体的な体験談 ＋「{product_name}使い始めて〜」のように商品名を自然に入れる
- 3/3: 結果・まとめ ＋「詳細はリプ欄👇」でCTA

ルール:
- 各投稿は100文字以内（厳守）
- 絵文字は各2個以内
- URLは含めない
- NGワード: 最安値、絶対、必ず

JSON形式で返してください:
{{"posts": ["投稿1テキスト", "投稿2テキスト", "投稿3テキスト"]}}"""

    result = ask_json(prompt)
    posts = result.get("posts", [])
    if len(posts) != 3:
        raise ValueError(f"3投稿生成できませんでした（{len(posts)}件）")
    return posts


def post_thread(product_name: str, hook: str, season_context: str = "", affiliate_url: str = "") -> dict:
    """3連リプライチェーンで投稿し、末尾にアフィリエイトURLをリプライする"""
    print(f"[ThreadPoster] スレッド生成中: {product_name}")
    texts = _generate_thread_texts(product_name, hook, season_context)

    post_ids = []
    prev_id = None

    for i, text in enumerate(texts, 1):
        print(f"[ThreadPoster] {i}/3 投稿中: {text[:30]}...")
        container_id = _create_container(text, reply_to_id=prev_id)
        time.sleep(3)
        post_id = _publish(container_id)
        post_ids.append(post_id)
        prev_id = post_id
        print(f"[ThreadPoster] {i}/3 完了: post_id={post_id}")
        if i < 3:
            time.sleep(2)

    # 1/3 の投稿にアフィリエイトURLをリプとして追加
    if affiliate_url and post_ids:
        affiliate_text = f"🛒 商品詳細はこちら👇\n{affiliate_url}"
        print(f"[ThreadPoster] アフィリエイトリプライ投稿中...")
        try:
            container_id = _create_container(affiliate_text, reply_to_id=post_ids[0])
            time.sleep(3)
            aff_id = _publish(container_id)
            post_ids.append(aff_id)
            print(f"[ThreadPoster] アフィリエイトリプライ完了: {aff_id}")
        except Exception as e:
            print(f"[ThreadPoster] アフィリエイトリプライ失敗（スキップ）: {e}")

    print(f"[ThreadPoster] スレッド投稿完了: {len(post_ids)}件")
    return {"post_ids": post_ids, "product_name": product_name}
