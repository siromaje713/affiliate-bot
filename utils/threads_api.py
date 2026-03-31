"""Threads API ラッパー"""
import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://graph.threads.net/v1.0"


def get_token() -> str:
    token = os.getenv("THREADS_ACCESS_TOKEN")
    if not token:
        raise ValueError("THREADS_ACCESS_TOKEN が .env に未設定")
    return token


def get_user_id() -> str:
    user_id = os.getenv("THREADS_USER_ID")
    if not user_id:
        raise ValueError("THREADS_USER_ID が .env に未設定")
    return user_id


def get_amazon_image_url(asin: str) -> str | None:
    """Amazon商品ページのdata-a-dynamic-imageからメイン画像URLを取得する"""
    try:
        resp = requests.get(
            f"https://www.amazon.co.jp/dp/{asin}",
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            timeout=10,
        )
        match = re.search(
            r'data-a-dynamic-image="\{&quot;(https://m\.media-amazon\.com/images/I/[^&]+)&quot;',
            resp.text,
        )
        if match:
            return match.group(1)
    except Exception as e:
        print(f"[ThreadsAPI] Amazon画像取得失敗 {asin}: {e}")
    return None


def create_post_container(text: str, image_url: str = None) -> str:
    """投稿コンテナを作成してIDを返す。image_urlがあれば画像投稿になる"""
    user_id = get_user_id()
    token = get_token()
    params = {
        "media_type": "IMAGE" if image_url else "TEXT",
        "text": text,
        "access_token": token,
    }
    if image_url:
        params["image_url"] = image_url
    resp = requests.post(
        f"{BASE_URL}/{user_id}/threads",
        params=params,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def publish_post(container_id: str) -> str:
    """コンテナを公開して投稿IDを返す"""
    user_id = get_user_id()
    token = get_token()
    resp = requests.post(
        f"{BASE_URL}/{user_id}/threads_publish",
        params={
            "creation_id": container_id,
            "access_token": token,
        },
    )
    resp.raise_for_status()
    return resp.json()["id"]


def get_post_insights(post_id: str) -> dict:
    """投稿メトリクスを取得する"""
    token = get_token()
    resp = requests.get(
        f"{BASE_URL}/{post_id}/insights",
        params={
            "metric": "likes,replies,reposts,views",
            "access_token": token,
        },
    )
    resp.raise_for_status()
    return resp.json()


def get_replies(post_id: str) -> list:
    """リプライ一覧を取得する"""
    token = get_token()
    resp = requests.get(
        f"{BASE_URL}/{post_id}/replies",
        params={"access_token": token},
    )
    resp.raise_for_status()
    return resp.json().get("data", [])
