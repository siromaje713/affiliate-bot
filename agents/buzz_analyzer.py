"""バズ分析エージェント：実績ベンチマークパターンをベース"""
import json
from datetime import datetime, timedelta
from pathlib import Path

CACHE_PATH = Path(__file__).parent.parent / "data" / "buzz_patterns.json"
CACHE_TTL_HOURS = 6

# フックスコアリング重み（hook_optimizer.pyで使用）
HOOK_SCORE_WEIGHTS = {
    "before_after": +3,   # 変化を数字で示す
    "price_shock":  +2,   # コスパの驚きを前面に
    "first_person": +2,   # 一人称（「私が」「先週」「届いた」）
    "has_number":   +1,   # 具体的な数字あり
    "no_link":      +1,   # リンク・URL含まない
}

# 実績ベンチマークデータ（siro_beauty7 2.2万フォロワー・riri____.beauty等から収集）
BENCHMARK_PATTERNS = {
    "権威型": [
        "美容クリニックの友達が『ロートの1000円台の美容液使うべき』って言ってて",
        "皮膚科医が実は〇〇より△△を推す理由が衝撃だった",
        "エステで働いてた子が辞めてから自腹で買いまくってる商品",
    ],
    "悩み直撃型": [
        "カラコン一日中絶対つけられない人なんだけど、コイツのおかげで1日中目がうるうるで助かってる",
        "乾燥でマスクが顔に貼り付く季節、ようやく解決策見つけた",
        "毛穴が気になって夏のファンデ諦めてた私が変わった",
    ],
    "驚き型": [
        "これ、名品中の名品。紗栄子さんも小田切ヒロさんも絶賛って間違いない",
        "逆に怖いくらい効いた。翌朝の肌が別物すぎて自分で引いた",
        "1000円台でこの効果は正気じゃない。デパコスと同じ成分で",
    ],
    "コスパ訴求型": [
        "1回3万のレーザーより1000円台の美容液の方が効いたって本当だった",
        "エステ代1回分で3年分のケアができるやつ見つけた",
        "デパコスと同じ成分でこの値段は何かの間違いかと思った",
    ],
    "リスト型": [
        "肌悩み解決策TOP5【保存推奨】①赤ら顔→亜鉛 ②毛穴→酵素 ③乾燥→セラミド",
        "春の肌トラブル別おすすめ対策リスト【保存版】",
        "27歳が厳選した美容アイテムBEST3",
    ],
    "before_after型": [
        "3日で毛穴が消えた話、信じてもらえないかもしれないけど",
        "1週間でリフトアップ、これ気のせいじゃなかった",
        "2ヶ月で別人みたいになった顎のライン",
    ],
}


def _is_cache_valid() -> bool:
    if not CACHE_PATH.exists():
        return False
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(data.get("cached_at", data.get("updated_at", "2000-01-01")))
        return datetime.now() - cached_at < timedelta(hours=CACHE_TTL_HOURS)
    except Exception:
        return False


def _load_cache() -> dict:
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def _save_cache(patterns: dict):
    CACHE_PATH.parent.mkdir(exist_ok=True)
    data = {"cached_at": datetime.now().isoformat(), "patterns": patterns}
    CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run() -> dict:
    """バズパターンを返す（キャッシュ有効なら再利用、なければ実績パターンを保存して返す）"""
    if _is_cache_valid():
        print("[BuzzAnalyzer] キャッシュ使用")
        return _load_cache()["patterns"]
    print("[BuzzAnalyzer] 実績ベンチマークパターンをロード中...")
    _save_cache(BENCHMARK_PATTERNS)
    total = sum(len(v) for v in BENCHMARK_PATTERNS.values())
    print(f"[BuzzAnalyzer] {total}件のパターンをセット")
    return BENCHMARK_PATTERNS
