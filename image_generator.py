"""
image_generator.py
Amazon商品画像をDL → Pillowで1080×1080に整形 → Imgurにアップ → URL返却

使い方:
    from image_generator import generate_product_image
    url = generate_product_image("肌ラボ 極潤ヒアルロン液", "https://m.media-amazon.com/...")

環境変数:
    IMGUR_CLIENT_ID: Imgur Client ID（省略時はデフォルト値を使用）
"""
import io
import os

_DEVICE_KEYWORDS = [
    "美顔器", "フェイスライン", "イオン", "リファ", "ヤーマン", "パナソニック",
    "ems", "EMS", "rf", "RF", "超音波", "美容機器", "フォトプラス", "エフェクター",
]
_MAKEUP_KEYWORDS = [
    "ファンデ", "ファンデーション", "リップ", "アイシャドウ", "アイライナー",
    "マスカラ", "チーク", "コンシーラー", "ハイライト", "アイブロウ", "パウダー",
    "ベースメイク", "メイク", "ティント", "グロス",
]

_BG_COLORS = {
    "skincare": (255, 248, 245),  # 温かみのあるオフホワイト
    "makeup":   (255, 245, 248),  # 薄ピンク
    "device":   (245, 248, 255),  # 薄ブルー
    "default":  (250, 248, 245),  # ベージュ
}


def _detect_category(product_name):
    name = product_name.lower()
    for kw in _DEVICE_KEYWORDS:
        if kw.lower() in name:
            return "device"
    for kw in _MAKEUP_KEYWORDS:
        if kw.lower() in name:
            return "makeup"
    return "skincare"


def _upload_image(img_bytes):
    """Imgurに匿名アップロードしてURLを返す"""
    import base64
    import requests
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    client_id = os.environ.get("IMGUR_CLIENT_ID", "546c25a59c58ad7")
    res = requests.post(
        "https://api.imgur.com/3/image",
        headers={"Authorization": f"Client-ID {client_id}"},
        data={"image": b64, "type": "base64"},
        timeout=30,
    )
    data = res.json()
    if not data.get("success"):
        raise Exception(f"imgur upload failed: {data}")
    return data["data"]["link"]


def generate_product_image(product_name, image_url=None):
    """
    画像投稿はシャドウバンの原因となるため、常にNoneを返す。
    テキスト投稿のリーチを優先する。
    """
    print("[ImageGen] 画像投稿無効（リーチ優先） → None返却")
    return None
