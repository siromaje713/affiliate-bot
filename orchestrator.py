"""オーケストレーター：全エージェントを統括する"""
import json
import os
import re
import sys
import time
import random
import argparse
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from agents import researcher, writer, poster, analyst, buzz_analyzer, hook_optimizer, reply_poster
from agents import insights_analyzer, web_scraper, thread_poster, conversation_agent
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
try:
    from line_notify import notify as line_notify
except ImportError:
    line_notify = None

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
        "amazon": "https://www.amazon.co.jp/dp/B001GPIQKE?tag=rikocosmelab-22",
        "rakuten": "https://a.r10.to/h8N8Bv",
    },
    "ヒアルロン": {
        "name": "肌ラボ 極潤ヒアルロン液",
        "amazon": "https://www.amazon.co.jp/dp/B001GPIQKE?tag=rikocosmelab-22",
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
        "amazon": "https://www.amazon.co.jp/dp/B003EPYUJE?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "キュレル": {
        "name": "キュレル 潤浸保湿 化粧水",
        "amazon": "https://www.amazon.co.jp/dp/B003DFOAP8?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "セタフィル": {
        "name": "セタフィル モイスチャライジングローション",
        "amazon": "https://www.amazon.co.jp/dp/B0009ET2UI?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "ニベア": {
        "name": "ニベア クリーム",
        "amazon": "https://www.amazon.co.jp/dp/B003ZRGDPG?tag=rikocosmelab-22",
        "rakuten": "",
    },
    # ── 日焼け止め・UVケア ──────────────────────────
    "アネッサ": {
        "name": "アネッサ パーフェクトUV スキンケアミルク",
        "amazon": "https://www.amazon.co.jp/dp/B0CWM6GZTM?tag=rikocosmelab-22",
        "rakuten": "https://a.r10.to/hkWt3Y",
    },
    "ANESSA": {
        "name": "アネッサ パーフェクトUV スキンケアミルク",
        "amazon": "https://www.amazon.co.jp/dp/B0CWM6GZTM?tag=rikocosmelab-22",
        "rakuten": "https://a.r10.to/hkWt3Y",
    },
    "スキンアクア": {
        "name": "スキンアクア トーンアップUV",
        "amazon": "https://www.amazon.co.jp/dp/B07BPLJFLK?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "ビオレ": {
        "name": "ビオレ UV アクア リッチ ウォータリーエッセンス",
        "amazon": "https://www.amazon.co.jp/dp/B00PQNUIWY?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "日焼け止め": {
        "name": "日焼け止め全般",
        "amazon": "https://www.amazon.co.jp/dp/B0CWM6GZTM?tag=rikocosmelab-22",
        "rakuten": "https://a.r10.to/h5b4am",
    },
    "ダルバ": {
        "name": "ダルバ 日焼け止め",
        "amazon": "",
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
        "amazon": "https://www.amazon.co.jp/dp/B08KGVHTS3?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "パナソニック": {
        "name": "パナソニック 美顔器 イオンエフェクター",
        "amazon": "https://www.amazon.co.jp/dp/B09TVHF7LY?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "イオンエフェクター": {
        "name": "パナソニック 美顔器 イオンエフェクター",
        "amazon": "https://www.amazon.co.jp/dp/B09TVHF7LY?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "RF美顔器": {
        "name": "RF美顔器",
        "amazon": "",
        "rakuten": "https://a.r10.to/h5yZS4",
    },
    "美顔器": {
        "name": "美顔器全般",
        "amazon": "",
        "rakuten": "https://a.r10.to/h5yZS4",
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
        "name": "シュワルツコフ グロッシーシャイン",
        "amazon": "https://www.amazon.co.jp/dp/B07MQ6FWZL?tag=rikocosmelab-22",
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
        "amazon": "https://www.amazon.co.jp/dp/B082YF3RGM?tag=rikocosmelab-22",
        "rakuten": "",
    },
    "CEZANNE": {
        "name": "CEZANNE ウォータリーティントリップ",
        "amazon": "https://www.amazon.co.jp/dp/B092KCNLPB?tag=rikocosmelab-22",
        "rakuten": "",
    },
    # ── その他（既存） ───────────────────────────────
    "MISSHA": {
        "name": "MISSHA アンプル",
        "amazon": "",
        "rakuten": "https://a.r10.to/hktN94",
    },
    "ミシャ": {
        "name": "ミシャ アンプル",
        "amazon": "",
        "rakuten": "https://a.r10.to/hktN94",
    },
    "アンプル": {
        "name": "ミシャ アンプル",
        "amazon": "",
        "rakuten": "https://a.r10.to/hktN94",
    },
}

_DEFAULT_URL = "https://a.r10.to/hkWt3Y"  # フォールバック（アネッサ楽天）


def get_affiliate_url(product_name: str, post_count: int = 0) -> str:
    """商品名でキーワードマッチ。post_countで楽天/Amazonを交互に返す。"""
    matched = None
    for keyword, info in PRODUCT_AFFILIATE_URLS.items():
        if keyword.lower() in product_name.lower():
            matched = info
            break

    if matched is None:
        return _DEFAULT_URL

    # post_countが奇数→Amazon優先、偶数→楽天優先（未設定なら逆を使う）
    if post_count % 2 == 1:
        return matched.get("amazon") or matched.get("rakuten") or _DEFAULT_URL
    else:
        return matched.get("rakuten") or matched.get("amazon") or _DEFAULT_URL

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
    for product in products[:1]:
        print(f"\n[Orchestrator] 「{product['product_name']}」処理中...")
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
            if best_post is None or result["score"] > best_post["score"]:
                best_post = result

    if not best_post:
        print("[Orchestrator] 品質基準を満たす投稿が生成できませんでした")
        if not dry_run:
            return

    best_post["text"] = strip_links(best_post["text"])
    print(f"[Orchestrator] 本文（リンクなし）:\n{best_post['text']}")

    if not dry_run and random.random() < 0.3:
        print("[Orchestrator] スレッド投稿モード（30%抽選）")
        thread_result = thread_poster.post_thread(
            product_name=best_post.get("product_name", "美容商品"),
            hook=best_post["text"].split("\n")[0][:40],
        )
        write_counter(counter + 1)
        print(f"[Orchestrator] スレッド投稿完了: {thread_result}")
        print(f"\n[Orchestrator] 完了（合計 {time.time() - t_start:.0f}秒）")
        return

    post_result = poster.run(best_post, dry_run=dry_run)
    write_counter(counter + 1)

    post_id = post_result.get("post_id")
    reply_text = f"🛒 商品詳細はこちら👇\n{get_affiliate_url(best_post.get('product_name', ''), post_count=counter)}"

    if post_type == "buzz":
        if dry_run:
            print("[Orchestrator][DRY RUN] buzz型のためリプライはスキップ")
        else:
            print("[Orchestrator] buzz型のためリプライはスキップ")
    elif dry_run:
        print(f"[Orchestrator][DRY RUN] リプライ予定:\n{reply_text}")
    else:
        reply_result = reply_poster.run(post_id, dry_run=False, product_name=best_post.get("product_name", ""))
        print(f"[Orchestrator] リプライ投稿完了: {reply_result}")

    print(f"\n[Orchestrator] 完了（合計 {time.time() - t_start:.0f}秒）")

def run_analytics():
    """アナリストのみ実行"""
    report = analyst.run()
    print("\n=== 改善レポート ===")
    for imp in report.get("improvements", []):
        print(f" • {imp}")
    print(f"明日のテーマ: {report.get('tomorrow_theme', 'なし')}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="affiliate-bot オーケストレーター")
    parser.add_argument("--mode", choices=["post", "analytics", "reply"], default="post")
    parser.add_argument("--dry-run", action="store_true", help="実際には投稿しない")
    args = parser.parse_args()
    try:
        if args.mode == "post":
            run_pipeline(dry_run=args.dry_run)
        elif args.mode == "analytics":
            run_analytics()
        elif args.mode == "reply":
            conversation_agent.run_conversation()
    except Exception as e:
        import traceback
        print(f"❌ [Orchestrator] エラー発生\n{type(e).__name__}: {str(e)[:200]}")
        raise
