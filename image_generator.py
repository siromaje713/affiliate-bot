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

# ── カテゴリ別プロンプト ──────────────────────────────────────────────
_PROMPTS = {
    "skincare": (
        "A luxury skincare product on a marble vanity counter, soft morning light through sheer curtains, "
        "fresh flowers in background, minimalist Japanese bathroom aesthetic, warm golden tones, "
        "product photography style, highly detailed, sharp focus, 8K"
    ),
    "makeup": (
        "Makeup products on a pink marble surface with gold accessories, soft natural shadows, "
        "beauty blogger flatlay style, overhead angle, pastel feminine aesthetic, "
        "highly detailed, sharp focus, 8K"
    ),
    "device": (
        "A beauty device on a soft white towel next to herbal tea, morning skincare routine, "
        "clean bright counter, warm lifestyle photography, highly detailed, sharp focus, 8K"
    ),
}
_PROMPTS["default"] = _PROMPTS["skincare"]


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
        prompt = _PROMPTS.get(category, _PROMPTS["default"])
        print(f"[ImageGen] カテゴリ={category} 商品={product_name[:30]}")
        print("[ImageGen] Flux text-to-image生成中...")

        result = fal_client.subscribe(
            "fal-ai/flux-pro/v1.1",
            arguments={
                "prompt": prompt,
                "image_size": {"width": 1080, "height": 1080},
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
