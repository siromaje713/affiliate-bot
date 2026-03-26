"""バズ分析エージェント：10万インプ超え美容系投稿パターンをキャッシュ"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from utils.claude_cli import ask_json

CACHE_PATH = Path(__file__).parent.parent / "data" / "buzz_patterns.json"
CACHE_TTL_HOURS = 24

# フックスコアリング重み（hook_optimizer.pyで使用）
HOOK_SCORE_WEIGHTS = {
    "before_after": +3,   # 変化を数字で示す
    "price_shock":  +2,   # コスパの驚きを前面に
    "first_person": +2,   # 一人称（「私が」「先週」「届いた」）
    "has_number":   +1,   # 具体的な数字あり
    "no_link":      +1,   # リンク・URL含まない
}


def _is_cache_valid() -> bool:
    if not CACHE_PATH.exists():
        return False
    data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
    return datetime.now() - cached_at < timedelta(hours=CACHE_TTL_HOURS)


def _load_cache() -> dict:
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def _save_cache(patterns: dict):
    CACHE_PATH.parent.mkdir(exist_ok=True)
    data = {"cached_at": datetime.now().isoformat(), "patterns": patterns}
    CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def analyze() -> dict:
    """10万インプ超えパターンを分析してJSONで返す"""
    prompt = """Threadsで10万インプレッション以上を獲得している美容系投稿の特徴を分析し、
@riko_cosme_lab（20〜40代女性・スキンケア・美顔器）向けのフックパターンを作成してください。

以下6タイプを各3例ずつ、JSONのみで返してください（説明不要）：
{
  "before_after型": [
    "3日で毛穴が消えた",
    "1週間でリフトアップした話",
    "2ヶ月で別人みたいになった顎のライン"
  ],
  "価格破壊型": [
    "9,900円が2,300円って何事",
    "エステ代1回分で一生使えるやつ見つけた",
    "デパコスと同じ成分でこの値段は正気か"
  ],
  "共感・悩み型": [
    "毛穴が気になって夏のファンデ諦めてた",
    "40代で美顔器デビューするか悩んでた",
    "乾燥がひどくてマスクが貼り付いてた"
  ],
  "実体験型": [
    "先週届いたんだけど正直ビビった",
    "半信半疑で使ってみたら朝の肌が別物",
    "口コミ見て試したら全員正しかった"
  ],
  "驚き型": [
    "美顔器、朝より夜に使うと効果が変わるって知ってた？",
    "汗で落ちる日焼け止め、実は選び方が9割だった",
    "保湿が足りないんじゃなくて順番が間違ってた"
  ],
  "数字型": [
    "1日60秒で頬がリフトした話",
    "月300円で化粧水の浸透が変わった",
    "週3回・5分で4週間後に友人に気づかれた"
  ]
}"""
    try:
        patterns = ask_json(prompt)
        _save_cache(patterns)
        return patterns
    except Exception as e:
        print(f"[BuzzAnalyzer] 分析エラー: {e}")
        return {}


def run() -> dict:
    """バズパターンを返す（キャッシュ有効なら再利用）"""
    if _is_cache_valid():
        print("[BuzzAnalyzer] キャッシュ使用")
        return _load_cache()["patterns"]
    print("[BuzzAnalyzer] 10万インプ超えパターンを分析中...")
    patterns = analyze()
    print(f"[BuzzAnalyzer] {sum(len(v) for v in patterns.values())}件のパターンを取得")
    return patterns
