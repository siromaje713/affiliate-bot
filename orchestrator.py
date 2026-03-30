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
from agents import researcher, writer, poster, analyst, buzz_analyzer, hook_optimizer, reply_poster
from agents import insights_analyzer, web_scraper, thread_poster, conversation_agent
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
        "name": "肌ラボ 極潤ヒアルロン液",
        "amazon": "https://www.amazon.co.jp/dp/B000FQUGXA?tag=rikocosmelab-22",
        "rakuten": "https://a.r10.to/h8N8Bv",
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
        "name": "VT CICA デイリースージングマスク",
        "amazon": "https://www.amazon.co.jp/dp/B083X5R6VR?tag=rikocosmelab-22",
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
    # ── 日焼け止め・UVケア ──────────────────────────
    "アネッサ": {
        "name": "アネッサ パーフェクトUV スキンケアミルク",
        "amazon": "https://www.amazon.co.jp/dp/B0CSSVF9GQ?tag=rikocosmelab-22",
        "rakuten": "https://a.r10.to/hkWt3Y",
    },
    "ANESSA": {
        "name": "アネッサ パーフェクトUV スキンケアミルク",
        "amazon": "https://www.amazon.co.jp/dp/B0CSSVF9GQ?tag=rikocosmelab-22",
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
        "name": "日焼け止め全般",
        "amazon": "https://www.amazon.co.jp/dp/B0CSSVF9GQ?tag=rikocosmelab-22",
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
        "name": "パナソニック 美顔器 イオンエフェクター",
        "amazon": "https://www.amazon.co.jp/dp/B0861FWQ8Q?tag=rikocosmelab-22",
        "rakuten": "",
    },
    # ── ヘアケア ────────────────────────────────────
    "ORBIS": {
        "name": "ORBIS エッセンスイン ヘアミルク",
        "amazon": "https://www.amazon.co.jp/dp/B06X17VVNQ?tag=rikocosmelab-22",
        "rakuten": "https://a.r10.to/h8N8vu",
    },
    "オルビス": {
        "name": "ORBIS エッセンスイン ヘアミルク",
        "amazon": "https://www.amazon.co.jp/dp/B06X17VVNQ?tag=rikocosmelab-22",
        "rakuten": "https://a.r10.to/h8N8vu",
    },
    "THE ANSWER": {
        "name": "THE ANSWER スーパーラメラシャンプー",
        "amazon": "https://www.amazon.co.jp/dp/B0DT4WN5D9?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "ラメラシャンプー": {
        "name": "THE ANSWER スーパーラメラシャンプー",
        "amazon": "https://www.amazon.co.jp/dp/B0DT4WN5D9?tag=rikocosmelab-22",
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
}

_DEFAULT_URL = "https://www.amazon.co.jp/dp/B0CSSVF9GQ?tag=rikocosmelab-22"  # フォールバック（アネッサAmazon）

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
        return fallback
    except Exception as e:
        elapsed = time.time() - t0
        print(f"[Timer] {label}: エラー({elapsed:.1f}秒) → {e}")
        return fallback
    finally:
        ex.shutdown(wait=False)

def run_pipeline(dry_run: bool = False):
    """バズ分析→フック最適化→ライティング→投稿→リプリンクの新パイプライン"""
    t_start = time.time()
    counter = read_counter()
    post_type = "buzz" if counter % 3 == 0 else "link"
    print(f"[Orchestrator] 投稿タイプ: {post_type}（カウンター: {counter}）")

    # trends_cacheを強制削除して毎回フレッシュな商品を生成させる
    trends_cache = Path("data/trends_cache.json")
    if trends_cache.exists():
        trends_cache.unlink()
        print("[Orchestrator] trends_cache.json を削除（強制リフレッシュ）")

    products = run_with_timeout("Researcher", researcher.run, timeout=60, fallback=[])
    if not products:
        print("[Orchestrator] 商品アイデアが取得できませんでした")
        return

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
    # 直近使用済み商品を除外してランダム選択（プログラム的フィルタ）
    last_used = researcher.load_last_used()
    filtered = [p for p in products if p["product_name"] not in last_used]
    if not filtered:
        filtered = products  # 全部使済みならリセット扱い
        print(f"[Orchestrator] 全商品が使用済みのためリセット")
    product = random.choice(filtered)
    print(f"\n[Orchestrator] 選択商品: 「{product['product_name']}」（{len(filtered)}/{len(products)}件から選択）")
    researcher.record_used(product["product_name"])

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
        if not dry_run:
            return

    best_post["text"] = strip_links(best_post["text"])
    print(f"[Orchestrator] 本文（リンクなし）:\n{best_post['text']}")

    _pname = best_post.get("product", {}).get("product_name", "美容商品")

    if not dry_run and random.random() < 0.3:
        print("[Orchestrator] スレッド投稿モード（30%抽選）")
        _aff_url = get_fresh_affiliate_url(_pname)
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

    post_result = poster.run(best_post, dry_run=dry_run)
    write_counter(counter + 1)

    post_id = post_result.get("post_id")
    _aff_url = get_fresh_affiliate_url(_pname)
    reply_text = f"🛒 商品詳細はこちら👇\n{_aff_url}\n#PR"

    # buzz型・link型どちらも毎回アフィリエイトリプライを付ける
    if dry_run:
        print(f"[Orchestrator][DRY RUN] リプライ予定:\n{reply_text}")
    else:
        _save_used_url(_aff_url)
        reply_result = reply_poster.run(post_id, dry_run=False, affiliate_url=_aff_url)
        print(f"[Orchestrator] リプライ投稿完了: {reply_result}")
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="affiliate-bot オーケストレーター")
    parser.add_argument("--mode", choices=["post", "analytics", "reply", "research", "insights"], default="post")
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
    except Exception as e:
        import traceback
        print(f"❌ [Orchestrator] エラー発生\n{type(e).__name__}: {str(e)[:200]}")
        if slack_notify:
            slack_notify("error", f"🚨 エラー\n{type(e).__name__}: {str(e)[:200]}")
        raise
