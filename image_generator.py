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


def generate_product_image(product_name, image_url):
    """
    Amazon商品画像を1080×1080に整形してImgurにアップロードし、URLを返す。

    Args:
        product_name: 商品名（カテゴリ判定・ログ用）
        image_url:    Amazon商品画像のURL

    Returns:
        Imgur上の画像URL (str)。失敗時は None を返す。
    """
    try:
        import requests
        from PIL import Image, ImageDraw
    except ImportError as e:
        print(f"[ImageGen] ライブラリ未インストール: {e}")
        return None

    try:
        # Step1: Amazon画像をDL
        print(f"[ImageGen] 商品画像DL中: {product_name[:30]}")
        resp = requests.get(
            image_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            },
            timeout=15,
        )
        resp.raise_for_status()
        src = Image.open(io.BytesIO(resp.content)).convert("RGBA")

        # Step2: 1080×1080 カテゴリ別パステル背景にリサイズ（アスペクト比を保ってパディング）
        SIZE = 1080
        category = _detect_category(product_name)
        bg_rgb = _BG_COLORS.get(category, _BG_COLORS["default"])
        print(f"[ImageGen] カテゴリ={category} 背景色={bg_rgb}")
        src.thumbnail((SIZE, SIZE), Image.LANCZOS)
        canvas = Image.new("RGBA", (SIZE, SIZE), bg_rgb + (255,))
        offset_x = (SIZE - src.width) // 2
        offset_y = (SIZE - src.height) // 2
        canvas.paste(src, (offset_x, offset_y), src)

        # Step3: 下部に薄いグラデーション帯（高さ120px、透明→半透明黒）
        GRAD_H = 120
        grad = Image.new("RGBA", (SIZE, GRAD_H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(grad)
        for y in range(GRAD_H):
            alpha = int(80 * y / GRAD_H)
            draw.line([(0, y), (SIZE, y)], fill=(0, 0, 0, alpha))
        canvas.paste(grad, (0, SIZE - GRAD_H), grad)

        # Step4: JPEGに変換してバッファへ
        out = canvas.convert("RGB")
        buf = io.BytesIO()
        out.save(buf, format="JPEG", quality=92)
        print("[ImageGen] 画像整形完了（1080×1080）")

        # Step5: Imgurにアップロード
        uploaded_url = _upload_image(buf.getvalue())
        print(f"[ImageGen] Imgurアップロード完了: {uploaded_url}")
        return uploaded_url

    except Exception as e:
        print(f"[ImageGen] エラー: {type(e).__name__}: {e}")
        return None
