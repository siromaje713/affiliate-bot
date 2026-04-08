"""オーケストレーター：全エージェントを統括する"""
import json
import os
import re
import sys
import time
import random
import argparse
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timedelta
from pathlib import Path
from agents import writer, poster, analyst, buzz_analyzer, hook_optimizer, reply_poster
from agents import insights_analyzer, web_scraper, thread_poster, conversation_agent
from utils import threads_api
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
try:
    from line_notify import notify as line_notify
except ImportError:
    line_notify = None
try:
    from slack_notify import notify as slack_notify
except ImportError:
    slack_notify = None

# アフィリエイトURL辞書（楽天 + Amazon、post_countで交互切り替え）
# Amazonリンク形式: https://www.amazon.co.jp/dp/[ASIN]?tag=rikocosmelab-22
PRODUCT_AFFILIATE_URLS = {
    # ── 洗顔・クレンジング ──────────────────────────
    "キュレル泡洗顔": {
        "name": "キュレル 潤浸保湿 泡洗顔料",
        "amazon": "https://www.amazon.co.jp/dp/B0096HZBGG?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "バルクオム": {
        "name": "BULK HOMME THE FACE WASH",
        "amazon": "https://www.amazon.co.jp/dp/B00O2P9ALO?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "ファンケル": {
        "name": "ファンケル マイルドクレンジングオイル",
        "amazon": "https://www.amazon.co.jp/dp/B0773Q4M66?tag=rikocosmelab-22",
        "rakuten": "",
    },
    # ── スキンケア ──────────────────────────────────
    "アテニア": {
        "name": "アテニア スキンクリア クレンズ オイル",
        "amazon": "https://www.amazon.co.jp/dp/B0CJXS8CB2?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "肌ラボ": {
        "name": "肌ラボ 極潤ヒアルロン液",
        "amazon": "https://www.amazon.co.jp/dp/B000FQUGXA?tag=rikocosmelab-22",
        "rakuten": "https://a.r10.to/h8N8Bv",
    },
    "ヒアルロン": {
        "name": "LaViness セラミド・ヒアルロン酸配合化粧水",
        "amazon": "https://www.amazon.co.jp/dp/B08LKDDRDF?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "ルルルン": {
        "name": "ルルルン フェイスマスク 32枚",
        "amazon": "https://www.amazon.co.jp/dp/B09JW6Q9XC?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "VT CICA": {
        "name": "VT CICA デイリースージングマスク",
        "amazon": "https://www.amazon.co.jp/dp/B083X5R6VR?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "CICA": {
        "name": "PLATINUM LABEL CICAローション ツボクサエキス配合",
        "amazon": "https://www.amazon.co.jp/dp/B0BZPG5HW8?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "雪肌精": {
        "name": "雪肌精 化粧水",
        "amazon": "https://www.amazon.co.jp/dp/B0010MGT70?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "キュレル": {
        "name": "キュレル 潤浸保湿 化粧水",
        "amazon": "https://www.amazon.co.jp/dp/B001JF7Z2Q?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "セタフィル": {
        "name": "セタフィル モイスチャライジングローション",
        "amazon": "https://www.amazon.co.jp/dp/B00VHRI9SA?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "ニベア": {
        "name": "ニベア クリーム",
        "amazon": "https://www.amazon.co.jp/dp/B000FQMT8K?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "メラノCC": {
        "name": "メラノCC 集中対策美容液",
        "amazon": "https://www.amazon.co.jp/dp/B08WMGW2S4?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "イニスフリー": {
        "name": "イニスフリー ノーセバム ミネラルパウダー",
        "amazon": "https://www.amazon.co.jp/dp/B0C851WQFJ?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "ナチュリエ": {
        "name": "ナチュリエ ハトムギ化粧水 スキンコンディショナー",
        "amazon": "https://www.amazon.co.jp/dp/B000FQP2YS?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "無印良品": {
        "name": "無印良品 敏感肌用化粧水 高保湿タイプ",
        "amazon": "https://www.amazon.co.jp/dp/B0CL3T2D3V?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "オバジ": {
        "name": "Obagi C25セラム Neo",
        "amazon": "https://www.amazon.co.jp/dp/B08TJGNB8R?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "ナールス": {
        "name": "ナールス ユニバ フェイスクリーム",
        "amazon": "https://www.amazon.co.jp/dp/B07PQQFR2B?tag=rikocosmelab-22",
        "rakuten": "",
    },
    # ── 日焼け止め・UVケア ──────────────────────────
    "アネッサ": {
        "name": "アネッサ パーフェクトUV スキンケアミルク",
        "amazon": "https://www.amazon.co.jp/dp/B0CSSVF9GQ?tag=rikocosmelab-22",
        "rakuten": "https://a.r10.to/hkWt3Y",
    },
    "ANESSA": {
        "name": "アネッサ パーフェクトUV スキンケアスプレー",
        "amazon": "https://www.amazon.co.jp/dp/B0CSST7HY7?tag=rikocosmelab-22",
        "rakuten": "https://a.r10.to/hkWt3Y",
    },
    "スキンアクア": {
        "name": "スキンアクア トーンアップUV",
        "amazon": "https://www.amazon.co.jp/dp/B079LNBJLP?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "ビオレ": {
        "name": "ビオレ おうちdeエステ 肌をなめらかにするミルクジェル",
        "amazon": "https://www.amazon.co.jp/dp/B0759HMBJK?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "日焼け止め": {
        "name": "ビオレUV アクアリッチ ウォータリーエッセンス",
        "amazon": "https://www.amazon.co.jp/dp/B07MFX87LV?tag=rikocosmelab-22",
        "rakuten": "https://a.r10.to/h5b4am",
    },
    # ── 美顔器・美容機器 ────────────────────────────
    "リファ": {
        "name": "リファ ハートコーム Aira",
        "amazon": "https://www.amazon.co.jp/dp/B0DBH7FHBW?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "ヤーマン": {
        "name": "ヤーマン フォトプラスEX",
        "amazon": "https://www.amazon.co.jp/dp/B06XW7CJ1X?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "パナソニック": {
        "name": "パナソニック 美顔器 イオンエフェクター",
        "amazon": "https://www.amazon.co.jp/dp/B0861FWQ8Q?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "イオンエフェクター": {
        "name": "パナソニック 美顔器 イオンエフェクター EH-ST78",
        "amazon": "https://www.amazon.co.jp/dp/B0861FZVBH?tag=rikocosmelab-22",
        "rakuten": "",
    },
    # ── ヘアケア ────────────────────────────────────
    "ORBIS": {
        "name": "ORBIS エッセンスイン ヘアミルク",
        "amazon": "https://www.amazon.co.jp/dp/B06X17VVNQ?tag=rikocosmelab-22",
        "rakuten": "https://a.r10.to/h8N8vu",
    },
    "オルビス": {
        "name": "ORBIS リンクルブライトUVプロテクター",
        "amazon": "https://www.amazon.co.jp/dp/B0BSMSKHHY?tag=rikocosmelab-22",
        "rakuten": "https://a.r10.to/h8N8vu",
    },
    "THE ANSWER": {
        "name": "THE ANSWER スーパーラメラシャンプー",
        "amazon": "https://www.amazon.co.jp/dp/B0DT4WN5D9?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "ラメラシャンプー": {
        "name": "THE ANSWER EXモイストトリートメント",
        "amazon": "https://www.amazon.co.jp/dp/B0DTGTG866?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "シュワルツコフ": {
        "name": "シュワルツコフ ユイルアローム ラブ シャンプー",
        "amazon": "https://www.amazon.co.jp/dp/B07SL52MDY?tag=rikocosmelab-22",
        "rakuten": "",
    },
    # ── メイク ──────────────────────────────────────
    "キャンメイク": {
        "name": "キャンメイク ジェルクリーミータッチライナー",
        "amazon": "https://www.amazon.co.jp/dp/B07B456KKP?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "マシュマロフィニッシュ": {
        "name": "CANMAKE マシュマロフィニッシュパウダー",
        "amazon": "https://www.amazon.co.jp/dp/B001GC6PEY?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "セザンヌ": {
        "name": "セザンヌ パールグロウハイライト",
        "amazon": "https://www.amazon.co.jp/dp/B07H97J6TP?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "CEZANNE": {
        "name": "CEZANNE ウォータリーティントリップ",
        "amazon": "https://www.amazon.co.jp/dp/B08TTJL78F?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "フェイスアイパレット": {
        "name": "CEZANNE フェイスアイパレット",
        "amazon": "https://www.amazon.co.jp/dp/B0BQKCT28X?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "CEZANNEベース": {
        "name": "CEZANNE UV ウルトラフィットベースEX",
        "amazon": "https://www.amazon.co.jp/dp/B08FHPNP32?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "excel": {
        "name": "excel スキニーリッチシャドウ SR01",
        "amazon": "https://www.amazon.co.jp/dp/B015FG6RXM?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "romand": {
        "name": "rom&nd ベターザンパレット",
        "amazon": "https://www.amazon.co.jp/dp/B0C9XLWKFG?tag=rikocosmelab-22",
        "rakuten": "",
    },
}

_DEFAULT_URL = "https://www.amazon.co.jp/dp/B0CSSVF9GQ?tag=rikocosmelab-22"  # フォールバック（アネッサAmazon）

# ユニーク商品リスト（重複ASIN除外・サイクルローテーション用）
_seen_asins: set = set()
UNIQUE_PRODUCTS: list = []
for _key, _info in PRODUCT_AFFILIATE_URLS.items():
    _amazon = _info.get("amazon", "")
    _asin = _amazon.split("/dp/")[1].split("?")[0] if "/dp/" in _amazon else ""
    if _asin and _asin not in _seen_asins:
        _seen_asins.add(_asin)
        UNIQUE_PRODUCTS.append({"product_name": _info["name"], "keyword": _key, "amazon": _amazon})
del _seen_asins, _key, _info, _amazon, _asin

CYCLE_COUNTER_PATH = Path("/tmp/cycle_counter.json")

def read_cycle_counter() -> int:
    """Renderエフェメラル対策: /tmpが消えた場合は時刻ベースにフォールバック"""
    if CYCLE_COUNTER_PATH.exists():
        try:
            data = json.loads(CYCLE_COUNTER_PATH.read_text(encoding="utf-8"))
            return data.get("index", 0)
        except Exception:
            pass
    # /tmpが消えた場合: UTC時刻の4時間ブロックでローテーション
    import time
    return (int(time.time()) // (3600 * 4)) % len(UNIQUE_PRODUCTS)

def write_cycle_counter(n: int):
    CYCLE_COUNTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    CYCLE_COUNTER_PATH.write_text(json.dumps({"index": n}, ensure_ascii=False), encoding="utf-8")


USED_URLS_PATH = Path("/tmp/used_reply_urls.json")
_USED_URL_TTL_HOURS = 24


def get_affiliate_url(product_name: str, post_count: int = 0) -> str:
    """商品名でキーワードマッチ。常にAmazon URLを返す。"""
    for keyword, info in PRODUCT_AFFILIATE_URLS.items():
        if keyword.lower() in product_name.lower():
            return info.get("amazon") or _DEFAULT_URL
    return _DEFAULT_URL


def _load_used_urls() -> dict:
    if not USED_URLS_PATH.exists():
        return {}
    try:
        return json.loads(USED_URLS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_used_url(url: str):
    used = _load_used_urls()
    cutoff = (datetime.now() - timedelta(hours=_USED_URL_TTL_HOURS)).isoformat()
    used = {u: t for u, t in used.items() if t > cutoff}
    used[url] = datetime.now().isoformat()
    USED_URLS_PATH.parent.mkdir(exist_ok=True)
    USED_URLS_PATH.write_text(json.dumps(used, ensure_ascii=False, indent=2), encoding="utf-8")


def get_fresh_affiliate_url(product_name: str) -> str:
    """24時間以内に使ったURLを除外してAmazon URLを返す。全使用済みならリセット。"""
    primary = get_affiliate_url(product_name)
    used = _load_used_urls()
    cutoff = (datetime.now() - timedelta(hours=_USED_URL_TTL_HOURS)).isoformat()
    recently_used = {u for u, t in used.items() if t > cutoff}

    if primary not in recently_used:
        return primary

    # 別のAmazon URLを探す（重複回避）
    for keyword, info in PRODUCT_AFFILIATE_URLS.items():
        url = info.get("amazon", "")
        if url and url not in recently_used:
            print(f"[Orchestrator] URL重複回避: 「{product_name}」→「{info['name']}」のURLを使用")
            return url

    # 全URL使用済みならリセット
    print("[Orchestrator] 全URL使用済みのためリセット（primaryを再利用）")
    return primary

AGENT_TIMEOUT = 30
COUNTER_PATH = Path("/tmp/post_counter.txt")

def read_counter() -> int:
    if COUNTER_PATH.exists():
        try:
            return int(COUNTER_PATH.read_text().strip())
        except Exception:
            return 0
    return 0

def write_counter(n: int):
    COUNTER_PATH.write_text(str(n))

def strip_links(text: str) -> str:
    """本文からURL・リンク誘導フレーズを完全除去する"""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'→?\s*\[楽天リンク\]', '', text)
    text = re.sub(r'[▼▶►]?\s*楽天[^\n]*', '', text)
    text = re.sub(r'(こちら|リンク|詳細|チェック|購入|check)[はをでから]?[→▶]?\s*', '', text)
    text = re.sub(r'\n{2,}', '\n', text)
    return text.strip()

def run_with_timeout(label: str, fn, *args, timeout: int = AGENT_TIMEOUT, fallback=None):
    """エージェントをタイムアウト付きで実行。詰まったらfallbackを返す"""
    t0 = time.time()
    ex = ThreadPoolExecutor(max_workers=1)
    try:
        future = ex.submit(fn, *args)
        result = future.result(timeout=timeout)
        elapsed = time.time() - t0
        print(f"[Timer] {label}: {elapsed:.1f}秒")
        return result
    except FuturesTimeoutError:
        print(f"[Timer] {label}: タイムアウト({timeout}秒) → スキップ")
        if slack_notify:
            slack_notify("error", f"⏱ {label}: タイムアウト({timeout}秒)")
        return fallback
    except Exception as e:
        elapsed = time.time() - t0
        print(f"[Timer] {label}: エラー({elapsed:.1f}秒) → {e}")
        if slack_notify:
            slack_notify("error", f"❌ {label}: エラー\n{type(e).__name__}: {str(e)[:200]}")
        return fallback
    finally:
        ex.shutdown(wait=False)

def generate_engagement_post() -> str:
    """エンゲージメント投稿を生成（writer.py engage型プロンプト使用・有益情報×煽り）"""
    # writer.run経由で黄金パターンプロンプトを呼ぶ
    dummy_product = {"product_name": "", "keyword": "", "amazon": ""}
    result = writer.run(dummy_product, post_type="engage")
    if not result:
        return ""
    text = strip_links(result["text"]).strip()
    text = text.strip('"').strip("'").strip("「").strip("」").strip()
    return text


def run_engagement_pipeline(dry_run: bool = False, counter: int = 0):
    """エンゲージメント投稿パイプライン（テキストのみ・リンクなし）"""
    t_start = time.time()
    eng_text = run_with_timeout(
        "EngagementWriter",
        generate_engagement_post,
        timeout=60, fallback=None,
    )
    if not eng_text:
        print("[Orchestrator] エンゲージメント投稿生成失敗")
        if slack_notify:
            slack_notify("error", "🚫 エンゲージメント投稿生成失敗")
        return
    print(f"[Orchestrator] エンゲージメント本文（{len(eng_text)}字）:\n{eng_text}")
    eng_post = {"text": eng_text}
    if dry_run:
        print(f"[Orchestrator][DRY RUN] エンゲージメント投稿:\n{eng_text}")
    else:
        try:
            post_result = poster.run(eng_post, dry_run=False)
            write_counter(counter + 1)
            post_id = post_result.get("post_id") if post_result else None
            if slack_notify:
                _link = f"\n🔗 https://www.threads.net/t/{post_id}" if post_id else ""
                slack_notify("success", f"💬 エンゲージメント投稿完了\n{eng_text}{_link}")
            print(f"[Orchestrator] エンゲージメント投稿完了: {post_id}")
        except Exception as e:
            print(f"[Orchestrator] エンゲージメント投稿失敗: {e}")
            if slack_notify:
                slack_notify("error", f"❌ エンゲージメント投稿失敗\n{type(e).__name__}: {str(e)[:200]}")
    print(f"\n[Orchestrator] 完了（合計 {time.time() - t_start:.0f}秒）")


def run_pipeline(dry_run: bool = False):
    """バズ分析→フック最適化→ライティング→投稿→リプリンクの新パイプライン"""
    t_start = time.time()

    # 起動時診断：環境変数チェック
    _env_status = {k: "OK" if os.environ.get(k) else "未設定" for k in [
        "ANTHROPIC_API_KEY", "THREADS_ACCESS_TOKEN", "THREADS_USER_ID", "SLACK_WEBHOOK_URL"
    ]}
    _env_msg = " / ".join(f"{k}:{v}" for k, v in _env_status.items())
    print(f"[Orchestrator] 環境変数: {_env_msg}")
    if slack_notify:
        slack_notify("success", f"🚀 postモード起動\n{_env_msg}")
    if _env_status["ANTHROPIC_API_KEY"] == "未設定":
        print("[Orchestrator] ANTHROPIC_API_KEY未設定 → 終了")
        if slack_notify:
            slack_notify("error", "❌ ANTHROPIC_API_KEY未設定。Renderダッシュボードで設定してください")
        return

    # bot判定回避: 起動時に最大1時間ランダムスリープ
    if not dry_run:
        _jitter = random.uniform(0, 3600)
        print(f"[Orchestrator] bot判定回避ジッター: {_jitter:.0f}秒スリープ")
        time.sleep(_jitter)

    counter = read_counter()
    # 投稿比率（10サイクル）:
    #   list型（保存リスト+アフィリプ）: 3回（counter%10 in 0,3,6）
    #   engage型（有益情報×煽り短文・リプなし）: 7回
    #   アフィ単体投稿: 0（停止中）アカウントパワー育成のため
    post_type = "list" if (counter % 10) in (0, 3, 6) else "engage"
    print(f"[Orchestrator] 投稿タイプ: {post_type}（カウンター: {counter}）")

    # engage型: writerでengage本文生成→poster投稿（reply_posterは呼ばない）
    if post_type == "engage":
        run_engagement_pipeline(dry_run=dry_run, counter=counter)
        return

    # ↓以下は list 型のみ（保存リスト+アフィリプ）

    buzz_cache = Path("data/buzz_patterns.json")
    buzz_patterns = {}
    if buzz_cache.exists():
        try:
            raw_patterns = json.loads(buzz_cache.read_text(encoding="utf-8")).get("patterns", {})
            # hook_optimizerはdict形式を期待するため、list形式を変換して渡す
            if isinstance(raw_patterns, list):
                buzz_patterns = {p.get("name", f"pattern_{i}"): [p.get("example", "")] for i, p in enumerate(raw_patterns) if isinstance(p, dict)}
            elif isinstance(raw_patterns, dict):
                buzz_patterns = raw_patterns
            print("[Orchestrator] BuzzAnalyzer: キャッシュ使用")
        except Exception:
            pass

    win_cache = Path("agents/cache/own_insights.json")
    win_patterns = []
    if win_cache.exists():
        try:
            win_patterns = json.loads(win_cache.read_text(encoding="utf-8")).get("win_patterns", [])
            print(f"[Orchestrator] InsightsAnalyzer: キャッシュ使用 ({len(win_patterns)}件)")
        except Exception:
            pass

    if not win_patterns:
        try:
            print("[Orchestrator] InsightsAnalyzer: リアルタイム取得中...")
            live = insights_analyzer.run()
            win_patterns = live if live else []
            if win_patterns:
                win_cache.parent.mkdir(parents=True, exist_ok=True)
                win_cache.write_text(
                    __import__("json").dumps({"win_patterns": win_patterns}, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                print(f"[Orchestrator] InsightsAnalyzer: {len(win_patterns)}件取得・キャッシュ保存")
        except Exception as e:
            print(f"[Orchestrator] InsightsAnalyzer: 取得失敗→スキップ ({e})")

    comp_cache = Path("agents/cache/competitor_buzz.json")
    competitor_posts = []
    if comp_cache.exists():
        try:
            posts_data = json.loads(comp_cache.read_text(encoding="utf-8")).get("posts", [])
            competitor_posts = [p["text"] if isinstance(p, dict) else p for p in posts_data if p]
            print("[Orchestrator] WebScraper: キャッシュ使用")
        except Exception:
            pass

    best_post = None
    # サイクル順で商品選択（Renderリセット対策・全商品を順番に1周）
    cycle_idx = read_cycle_counter()
    product = UNIQUE_PRODUCTS[cycle_idx % len(UNIQUE_PRODUCTS)]
    write_cycle_counter(cycle_idx + 1)
    # _pname と _aff_url はサイクル選択した product から直接取得（writerの結果に依存しない）
    _pname = product["product_name"]
    _aff_url = product["amazon"] or _DEFAULT_URL
    print(f"\n[Orchestrator] サイクル選択: 「{_pname}」（{cycle_idx % len(UNIQUE_PRODUCTS) + 1}/{len(UNIQUE_PRODUCTS)}）")
    print(f"[Orchestrator] アフィリエイトURL: {_aff_url}")

    hook_result = run_with_timeout(
        f"HookOptimizer({product['product_name']})",
        hook_optimizer.run,
        product, buzz_patterns,
        timeout=30, fallback=None
    )
    hook_text = hook_result["hook"] if hook_result else None
    result = run_with_timeout(
        f"Writer({product['product_name']})",
        lambda p=product, h=hook_text, w=win_patterns, c=competitor_posts, pt=post_type: writer.run(p, hook=h, win_patterns=w, competitor_posts=c, post_type=pt),
        timeout=60, fallback=None
    )
    if result:
        best_post = result

    if not best_post:
        print("[Orchestrator] 品質基準を満たす投稿が生成できませんでした")
        if slack_notify:
            slack_notify("error", f"🚫 Writer失敗: 投稿スキップ\n商品: {_pname}\nhook_text: {hook_text}")
        if not dry_run:
            return

    best_post["text"] = strip_links(best_post["text"])
    print(f"[Orchestrator] 本文（リンクなし）:\n{best_post['text']}")

    # list型: writerのaffiliate_keywordからアフィURLを取得（サイクル選択商品より優先）
    aff_keyword = best_post.get("affiliate_keyword", "")
    if aff_keyword:
        _new_url = get_fresh_affiliate_url(aff_keyword)
        if _new_url:
            _aff_url = _new_url
            _pname = aff_keyword
            print(f"[Orchestrator] list型: affiliate_keyword「{aff_keyword}」→ {_aff_url}")

    print("[Orchestrator] テキスト投稿モード（画像なし・リーチ優先）")

    if not dry_run and random.random() < 0.3:
        print("[Orchestrator] スレッド投稿モード（30%抽選）")
        _save_used_url(_aff_url)
        thread_result = thread_poster.post_thread(
            product_name=_pname,
            hook=best_post["text"].split("\n")[0][:40],
            affiliate_url=_aff_url,
        )
        write_counter(counter + 1)
        print(f"[Orchestrator] スレッド投稿完了: {thread_result}")
        if slack_notify:
            _hook = best_post["text"].split("\n")[0][:40]
            _thread_post_id = thread_result.get("post_ids", [None])[0] if thread_result else None
            _threads_link = f"\n🔗 https://www.threads.net/t/{_thread_post_id}" if _thread_post_id else ""
            slack_notify("success",
                f"✅ 投稿完了\n商品: {_pname}\n{_hook}...\n🛒 {_aff_url}{_threads_link}"
            )
        print(f"\n[Orchestrator] 完了（合計 {time.time() - t_start:.0f}秒）")
        return

    try:
        post_result = poster.run(best_post, dry_run=dry_run)
    except Exception as _post_err:
        _err_str = str(_post_err)
        if best_post.get("image_url") and ("500" in _err_str or "Server" in _err_str):
            print(f"[Orchestrator] 画像投稿500エラー → テキスト投稿にフォールバック: {_post_err}")
            if slack_notify:
                slack_notify("error", f"⚠️ 画像投稿500エラー→テキストフォールバック\n商品: {_pname}")
            _fallback = dict(best_post)
            _fallback.pop("image_url", None)
            post_result = poster.run(_fallback, dry_run=dry_run)
        else:
            raise
    write_counter(counter + 1)

    post_id = post_result.get("post_id")
    reply_text = f"🛒 商品詳細はこちら👇\n{_aff_url}\n#PR"

    # list型のみ毎回アフィリエイトリプライを付ける（engage型はreply_poster呼ばない）
    if dry_run:
        print(f"[Orchestrator][DRY RUN] リプライ予定:\n{reply_text}")
    else:
        _save_used_url(_aff_url)
        print(f"[Orchestrator] リプライ投稿開始: post_id={post_id}")
        try:
            reply_result = reply_poster.run(post_id, dry_run=False, affiliate_url=_aff_url)
            print(f"[Orchestrator] リプライ投稿完了: {reply_result}")
        except Exception as _reply_err:
            print(f"[Orchestrator] リプライ投稿失敗: {_reply_err}")
            if slack_notify:
                slack_notify("error", f"❌ リプライ失敗\npost_id={post_id}\n{_reply_err}")
        if slack_notify:
            _hook = best_post["text"].split("\n")[0][:40]
            _threads_link = f"\n🔗 https://www.threads.net/t/{post_id}" if post_id else ""
            slack_notify("success",
                f"✅ 投稿完了\n商品: {_pname}\n{_hook}...\n🛒 {_aff_url}{_threads_link}"
            )

    print(f"\n[Orchestrator] 完了（合計 {time.time() - t_start:.0f}秒）")

def run_analytics():
    """アナリストのみ実行"""
    report = analyst.run()
    print("\n=== 改善レポート ===")
    for imp in report.get("improvements", []):
        print(f" • {imp}")
    print(f"明日のテーマ: {report.get('tomorrow_theme', 'なし')}")


def run_research():
    """Threadsバイラル投稿を収集・分析してbuzz_patterns.jsonを更新"""
    from agents import buzz_researcher
    print("[Research] バズリサーチ開始...")
    context = buzz_researcher.get_buzz_context()
    patterns = context.get("patterns", [])
    print(f"[Research] {len(patterns)}件のパターンを取得・保存完了")
    print(f"[Research] 保存先: data/buzz_patterns.json")


def run_insights():
    """自分のThreads投稿の反応データを分析してown_insights.jsonを更新"""
    print("[Insights] インサイト分析開始...")
    results = insights_analyzer.run()
    count = len(results) if results else 0
    print(f"[Insights] {count}件の勝ちパターンを更新完了")
    print(f"[Insights] 保存先: agents/cache/own_insights.json")


def run_engage():
    """ベンチマークアカウントの最新投稿に共感リプライ（エンゲージメント強化）"""
    from agents import engage_agent
    print("[Engage] エンゲージ開始...")
    results = engage_agent.run()
    if slack_notify and results:
        for r in results:
            snippet = r["post_text"][:30]
            slack_notify("success", f"💬 エンゲージ完了\n{snippet}...\nリプ: {r['reply']}")
    print(f"[Engage] {len(results)}件完了")


def _check_token_expiry():
    """THREADS_TOKEN_EXPIRES_ATが7日以内ならSlack警告を送る"""
    expires_at = os.environ.get("THREADS_TOKEN_EXPIRES_AT", "")
    if not expires_at:
        return
    try:
        expiry = datetime.strptime(expires_at, "%Y-%m-%d")
        days_left = (expiry - datetime.now()).days
        if days_left <= 7 and slack_notify:
            slack_notify("error", f"⚠️ トークン期限7日以内（残り{days_left}日）\nTHREADS_ACCESS_TOKENを更新してください")
            print(f"[Orchestrator] ⚠️ トークン期限警告: 残り{days_left}日")
    except Exception:
        pass


if __name__ == "__main__":
    _check_token_expiry()
    parser = argparse.ArgumentParser(description="affiliate-bot オーケストレーター")
    parser.add_argument("--mode", choices=["post", "analytics", "reply", "research", "insights", "engage"], default="post")
    parser.add_argument("--dry-run", action="store_true", help="実際には投稿しない")
    args = parser.parse_args()
    try:
        if args.mode == "post":
            run_pipeline(dry_run=args.dry_run)
        elif args.mode == "analytics":
            run_analytics()
        elif args.mode == "reply":
            conversation_agent.run_conversation()
        elif args.mode == "research":
            run_research()
        elif args.mode == "insights":
            run_insights()
        elif args.mode == "engage":
            run_engage()
    except Exception as e:
        import traceback
        print(f"❌ [Orchestrator] エラー発生\n{type(e).__name__}: {str(e)[:200]}")
        if slack_notify:
            slack_notify("error", f"🚨 エラー\n{type(e).__name__}: {str(e)[:200]}")
        raise
