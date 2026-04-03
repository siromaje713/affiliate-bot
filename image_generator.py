"""
image_generator.py
パターンA: Amazon商品画像 → birefnet背景除去 → Flux背景合成 → 画像URL返却

使い方:
    from image_generator import generate_product_image
    url = generate_product_image("肌ラボ 極潤ヒアルロン液", "https://m.media-amazon.com/...")

環境変数:
    FAL_KEY: Fal AI APIキー（https://fal.ai/dashboard/keys で取得）
"""
import os
import re

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

# ── カテゴリ別プロンプト（06_画像戦略_プロンプト集.md より） ──────────
_PROMPTS = {
    "skincare": (
        "A luxury skincare product placed on a white marble bathroom countertop, "
        "surrounded by fresh white flowers and soft green leaves, "
        "morning sunlight streaming in from the side creating gentle shadows, "
        "clean minimalist composition, soft pastel tones, "
        "professional product photography, high-end beauty brand aesthetic, "
        "8k resolution, shallow depth of field"
    ),
    "device": (
        "A premium beauty device placed on a neatly folded white towel, "
        "beside a warm herbal tea cup and small pebbles, "
        "clean white bathroom shelf background, "
        "soft diffused lighting, spa-like serene atmosphere, "
        "professional product photography, minimalist Japanese aesthetic, "
        "8k resolution"
    ),
    "makeup": (
        "A cosmetic product arranged on a pink marble flat lay, "
        "surrounded by gold accessories, dried rose petals, and a small mirror, "
        "overhead shot with soft warm lighting, "
        "luxury beauty editorial style, feminine and elegant composition, "
        "professional product photography, 8k resolution"
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


def _run_fal(endpoint, arguments):
    """fal_client.run のラッパー。FAL_KEY を環境変数から注入する"""
    fal_key = os.environ.get("FAL_KEY", "")
    if not fal_key:
        raise RuntimeError("FAL_KEY が環境変数に設定されていません")

    try:
        import fal_client  # pip install fal-client
    except ImportError:
        raise RuntimeError("fal-client が未インストールです: pip install fal-client")

    os.environ["FAL_KEY"] = fal_key  # fal_client は環境変数を参照する
    return fal_client.run(endpoint, arguments=arguments)


def remove_background(image_url):
    """
    Step1: fal-ai/birefnet で背景除去
    Returns: 背景除去後の画像URL (PNG)
    """
    result = _run_fal(
        "fal-ai/birefnet",
        {
            "image_url": image_url,
            "model": "General Use (Light)",
            "output_format": "png",
        },
    )
    # レスポンス構造: {"image": {"url": "..."}}
    out = result.get("image") or {}
    url = out.get("url") or result.get("url") or ""
    if not url:
        raise RuntimeError(f"birefnet: 画像URLが取得できません。response={result}")
    return url


def composite_background(bg_removed_url, prompt):
    """
    Step2: fal-ai/flux/dev/image-to-image で背景合成
    Returns: 合成後の画像URL (JPEG)
    """
    result = _run_fal(
        "fal-ai/flux/dev/image-to-image",
        {
            "image_url": bg_removed_url,
            "prompt": prompt,
            "image_size": "square_hd",
            "num_inference_steps": 28,
            "guidance_scale": 3.5,
            "strength": 0.65,
            "num_images": 1,
            "enable_safety_checker": True,
            "output_format": "jpeg",
        },
    )
    # レスポンス構造: {"images": [{"url": "..."}]}
    images = result.get("images") or []
    url = images[0].get("url") if images else result.get("url") or ""
    if not url:
        raise RuntimeError(f"flux image-to-image: 画像URLが取得できません。response={result}")
    return url


def generate_product_image(product_name, image_url):
    """
    Amazon商品画像を美しい背景に合成して返す（パターンA）

    Args:
        product_name: 商品名（カテゴリ自動判定に使用）
        image_url:    Amazon商品画像のURL

    Returns:
        合成後の画像URL (str)。失敗時は None を返す（投稿はテキストにフォールバック）
    """
    try:
        category = _detect_category(product_name)
        prompt = _PROMPTS.get(category, _PROMPTS["default"])
        print(f"[ImageGen] カテゴリ={category} 商品={product_name[:30]}")

        print("[ImageGen] Step1: birefnet 背景除去中...")
        bg_removed_url = remove_background(image_url)
        print(f"[ImageGen] Step1完了: {bg_removed_url[:60]}...")

        print("[ImageGen] Step2: Flux 背景合成中...")
        final_url = composite_background(bg_removed_url, prompt)
        print(f"[ImageGen] Step2完了: {final_url[:60]}...")

        return final_url

    except RuntimeError as e:
        print(f"[ImageGen] エラー（設定不備）: {e}")
        return None
    except Exception as e:
        print(f"[ImageGen] エラー: {type(e).__name__}: {e}")
        return None
