"""バズ分析エージェント：実績ベンチマークパターンをベース"""
import json
from datetime import datetime, timedelta
from pathlib import Path

CACHE_PATH = Path(__file__).parent.parent / "data" / "buzz_patterns.json"
CACHE_TTL_HOURS = 6

# フックスコアリング重み（hook_optimizer.pyで使用）
# popo.biyou実績データ反映 2026/03/31
HOOK_SCORE_WEIGHTS = {
    "before_after":        +3,   # 変化を数字で示す
    "price_shock":         +2,   # コスパの驚きを前面に
    "first_person":        +2,   # 一人称（「私が」「先週」「届いた」）
    "has_number":          +1,   # 具体的な数字あり
    "no_link":             +1,   # リンク・URL含まない
    "influencer_mention":  +3,   # インフルエンサー名言及（popo.biyou 641いいね実績）
    "repeat_purchase":     +2,   # リピート購入言及（「〇回リピ」）
    "honest_confession":   +2,   # 「正直」系ワード
}

# 実績ベンチマークデータ（popo.biyou 直近7日 上位5件 2026/03/31計測）
BENCHMARK_PATTERNS = {
    "インフルエンサー言及型": [
        # 1位 641いいね
        "正直、これ一個で十分。全部これに詰まってるし、小田切ヒロさん推しが強すぎてびびる。",
        # 3位 46いいね
        "正直これ使ったら他に戻れない。小田切ヒロさんが使ってるって聞いて試したけど納得。",
        "紗栄子さんも小田切ヒロさんも絶賛って言われたら試すしかないじゃん。",
        "あの〇〇さんが愛用してるって知ってから毎月リピしてる。",
    ],
    "リピート断言型": [
        # 2位 197いいね
        "もう、10回以上リピしてる。KATEリプモン05、どんなメイクにもすっとなじむ。",
        "もう3本リピートしてる。これだけは絶対切らしたくない。",
        "気づいたら5本目。これがないと朝のルーティンが成立しない。",
    ],
    "価格破壊型": [
        # 4位 29いいね
        "KATEのこれ、普通に価格バグ。これひとつで、うるちゅる目元完成×ちゃんと盛れる。",
        "1000円台でこの効果は正気じゃない。デパコスと同じ成分で",
        "エステ級の毛穴ケアが3,000円台って何？",
    ],
    "権威型": [
        "美容クリニックの友達が『ロートの1000円台の美容液使うべき』って言ってて",
        "皮膚科医が実は〇〇より△△を推す理由が衝撃だった",
        "エステで働いてた子が辞めてから自腹で買いまくってる商品",
    ],
    "悩み直撃型": [
        # 5位 2いいね（伸びしろ確認中）
        "ニセ涙袋っぽい人、これ試して！一気に元から可愛い目になる。",
        "カラコン一日中絶対つけられない人なんだけど、コイツのおかげで1日中目がうるうるで助かってる",
        "乾燥でマスクが顔に貼り付く季節、ようやく解決策見つけた",
        "毛穴が気になって夏のファンデ諦めてた私が変わった",
    ],
    "驚き型": [
        "逆に怖いくらい効いた。翌朝の肌が別物すぎて自分で引いた",
        "1000円台でこの効果は正気じゃない。デパコスと同じ成分で",
        "使い始めて3日目の朝、鏡を二度見した",
    ],
    "コスパ訴求型": [
        "1回3万のレーザーより効いた気がする正直",
        "デパコスと成分ほぼ同じなのにこの値段差は何？",
        "コスパ最強すぎて友達に言いふらしてる",
    ],
}


def get_buzz_context() -> dict:
    """ライターエージェントに渡すバズコンテキストを返す"""
    if CACHE_PATH.exists():
        try:
            data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
            if datetime.now() - cached_at < timedelta(hours=CACHE_TTL_HOURS):
                return data
        except Exception:
            pass

    result = {
        "cached_at": datetime.now().isoformat(),
        "source": "static_benchmark",
        "patterns": BENCHMARK_PATTERNS,
        "hook_weights": HOOK_SCORE_WEIGHTS,
        "top_hooks": [
            {"pattern": "インフルエンサー言及型", "max_likes": 641, "example": "正直、これ一個で十分。小田切ヒロさん推しが強すぎてびびる。"},
            {"pattern": "リピート断言型", "max_likes": 197, "example": "もう10回以上リピしてる。どんなメイクにもすっとなじむ。"},
            {"pattern": "価格破壊型", "max_likes": 46, "example": "普通に価格バグ。うるちゅる目元完成×ちゃんと盛れる。"},
        ],
    }

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
