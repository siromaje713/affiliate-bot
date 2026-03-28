"""スレッド投稿エージェント：1投稿を2連リプライチェーンで展開（2/2にアフィリエイトURL直接埋め込み）"""
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
    """Claudeで2投稿分のテキストを生成する（各100文字以内・URLなし）"""
    season_note = f"季節感: {season_context}\n" if season_context else ""
    prompt = f"""美容アカウント「りこ」として、{product_name}について2連投稿のスレッドを作成してください。

{season_note}1投稿目のフック: {hook}

【実績ベンチマークから学んだバズ構成】
- 1/2: 悩み直撃フック（商品名より先に悩みを言う）＋「{product_name}」を自然に1回だけ言及＋「続きで詳しく→」でCTA
  例: 「カラコン一日中つけられない人なんだけど、{product_name}のおかげで変わった。続きで詳しく→」
- 2/2: 具体的な体験談＋数字や変化で結果を示す＋「みんなは試した？」等の質問で締める
  例: 「使い始めて3日で目元のうるおいが全然違う。乾燥が気になる季節に本当に助かってる。みんなは？😊」

ルール:
- 各投稿は100文字以内（厳守）
- 絵文字は各2個以内
- URLは含めない（URLは後で別途追加する）
- NGワード: 最安値、絶対、必ず
- 2/2は質問で締めること（「みんなは？」「試した人いる？」「どう思う？」等）

JSON形式で返してください:
{{"posts": ["投稿1テキスト", "投稿2テキスト"]}}"""

    result = ask_json(prompt)
    posts = result.get("posts", [])
    if len(posts) != 2:
        raise ValueError(f"2投稿生成できませんでした（{len(posts)}件）")
    return posts


def post_thread(product_name: str, hook: str, season_context: str = "", affiliate_url: str = "") -> dict:
    """2連リプライチェーンで投稿（2/2の末尾にアフィリエイトURLを直接埋め込む）"""
    print(f"[ThreadPoster] スレッド生成中: {product_name}")
    texts = _generate_thread_texts(product_name, hook, season_context)

    # 2/2の末尾にURLを直接埋め込む
    if affiliate_url:
        texts[1] = texts[1].rstrip() + f"\n{affiliate_url}\n#PR"
        print(f"[ThreadPoster] アフィリエイトURL埋め込み済み（2/2）")

    post_ids = []
    prev_id = None

    for i, text in enumerate(texts, 1):
        print(f"[ThreadPoster] {i}/2 投稿中: {text[:30]}...")
        container_id = _create_container(text, reply_to_id=prev_id)
        time.sleep(3)
        post_id = _publish(container_id)
        post_ids.append(post_id)
        prev_id = post_id
        print(f"[ThreadPoster] {i}/2 完了: post_id={post_id}")
        if i < 2:
            time.sleep(2)

    print(f"[ThreadPoster] スレッド投稿完了: {len(post_ids)}件")
    return {"post_ids": post_ids, "product_name": product_name}
