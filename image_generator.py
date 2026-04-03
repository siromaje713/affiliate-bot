"""
image_generator.py
Flux text-to-image で「商品が置いてあるおしゃれな日常シーン」を直接生成する。

使い方:
    from image_generator import generate_product_image
    url = generate_product_image("肌ラボ 極潤ヒアルロン液")

環境変数:
    FAL_KEY: Fal AI APIキー（https://fal.ai/dashboard/keys で取得）
"""
import os

# ── カテゴリ判定キーワード ───────────────────────────────────────────
_DEVICE_KEYWORDS = [
    "美顔器", "フェイスライン", "イオン", "リファ", "ヤーマン", "パナソニック",
    "ems", "EMS", "rf", "RF", "超音波", "美容機器", "フォトプラス", "エフェクター",
]
_MAKEUP_KEYWORDS = [
    "ファンデ", "ファンデーション", "リップ", "アイシャドウ", "アイライナー",
    "マスカラ", "チーク", "コンシーラー", "ハイライト", "アイブロウ", "パウダー",
    "ベースメイク", "メイク", "ティント", "グロス",
]

# ── カテゴリ別プロンプトテンプレート（{product_name} を商品名で展開） ──
_PROMPT_TEMPLATES = {
    "skincare": (
        "Full frame, {product_name} skincare product casually held in a woman's hand, "
        "modern Japanese apartment interior, white marble countertop, morning light from window, "
        "minimal lifestyle, Canon 5D portrait lens bokeh background, "
        "editorial magazine quality, 8K sharp"
    ),
    "makeup": (
        "Full frame, {product_name} makeup product lying on a white bed sheet, "
        "modern clean Japanese apartment, soft morning sunlight, feminine lifestyle, "
        "woman's hand reaching for it, shallow depth of field bokeh, "
        "editorial beauty magazine quality, 8K sharp"
    ),
    "device": (
        "Full frame, {product_name} beauty device on a wooden bathroom shelf, "
        "modern Japanese apartment bathroom, soft warm lighting, "
        "towel and skincare bottles around, lifestyle photography, "
        "shallow depth of field, editorial quality, 8K sharp"
    ),
}
_PROMPT_TEMPLATES["default"] = _PROMPT_TEMPLATES["skincare"]


def _detect_category(product_name):
    """商品名のキーワードからカテゴリを判定する"""
    name = product_name.lower()
    for kw in _DEVICE_KEYWORDS:
        if kw.lower() in name:
            return "device"
    for kw in _MAKEUP_KEYWORDS:
        if kw.lower() in name:
            return "makeup"
    return "skincare"


def generate_product_image(product_name, image_url=None):
    """
    fal-ai/flux-pro/v1.1 でカテゴリ別の雰囲気画像を生成して返す。
    image_url は後方互換のため残すが使用しない。

    Args:
        product_name: 商品名（カテゴリ自動判定に使用）
        image_url:    未使用（後方互換）

    Returns:
        生成画像URL (str)。失敗時は None を返す（投稿はテキストにフォールバック）
    """
    fal_key = os.environ.get("FAL_KEY", "")
    if not fal_key:
        print("[ImageGen] FAL_KEY未設定 → スキップ")
        return None

    try:
        import fal_client
    except ImportError:
        print("[ImageGen] fal-client未インストール: pip install fal-client")
        return None

    try:
        os.environ["FAL_KEY"] = fal_key

        category = _detect_category(product_name)
        template = _PROMPT_TEMPLATES.get(category, _PROMPT_TEMPLATES["default"])
        prompt = template.format(product_name=product_name)
        print(f"[ImageGen] カテゴリ={category} 商品={product_name[:30]}")
        print("[ImageGen] Flux text-to-image生成中...")

        result = fal_client.subscribe(
            "fal-ai/flux-pro/v1.1",
            arguments={
                "prompt": prompt,
                "image_size": "square_hd",
                "num_inference_steps": 28,
                "guidance_scale": 3.5,
                "num_images": 1,
                "enable_safety_checker": True,
                "output_format": "jpeg",
            },
        )

        images = result.get("images") or []
        url = images[0].get("url") if images else result.get("url") or ""
        if not url:
            raise RuntimeError(f"flux-pro/v1.1: 画像URLが取得できません。response={result}")

        print(f"[ImageGen] 生成完了: {url[:60]}...")
        return url

    except Exception as e:
        print(f"[ImageGen] エラー: {type(e).__name__}: {e}")
        return None
