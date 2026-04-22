"""Writer list型/engage型のLLM生応答ダンプ（修正せず診断のみ）

monkey-patch で utils.claude_cli.ask_medium を包み、raw応答を /tmp/writer_raw_dump.txt に追記保存する。
writer.generate_patterns を post_type=list / post_type=engage で1回ずつ呼び、
それぞれの raw 応答と json.loads 試行結果を報告する。
"""
import os
import sys
import json
import re
import random

_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS)
sys.path.insert(0, _ROOT)

# ANTHROPIC_API_KEY を /tmp/anthropic_key.txt からロード（Render env groupから取得済み）
_key_path = "/tmp/anthropic_key.txt"
if os.path.exists(_key_path) and os.path.getsize(_key_path) > 0:
    os.environ["ANTHROPIC_API_KEY"] = open(_key_path).read().strip()

DUMP_PATH = "/tmp/writer_raw_dump.txt"
if os.path.exists(DUMP_PATH):
    os.remove(DUMP_PATH)

from utils import claude_cli
_orig_ask_medium = claude_cli.ask_medium

_captured = []

def _wrap_ask_medium(prompt, model=None, retries=None):
    kwargs = {}
    if model is not None:
        kwargs["model"] = model
    if retries is not None:
        kwargs["retries"] = retries
    raw = _orig_ask_medium(prompt, **kwargs)
    _captured.append({"prompt": prompt, "raw": raw})
    return raw

claude_cli.ask_medium = _wrap_ask_medium
# writer.py は `from utils.claude_cli import ask, ask_json, ask_short` している。
# ask_json は claude_cli モジュール内部で ask_medium を参照するので上のパッチで効く。

from agents import writer

DUMMY_PRODUCT = {
    "product_name": "キュレル 潤浸保湿 泡洗顔料",
    "seasonal_hook": "春の花粉で敏感になった肌に",
    "urgency": "今の時期の敏感肌ケア",
    "hook_angle": "セラミド補給で夕方までしっとり",
    "target_pain": "乾燥・敏感で何を使っても合わない人",
}


def _try_parse(raw: str):
    """ask_json が使っているのと同じ抽出＋パースを再現"""
    match = re.search(r"(\[.*\]|\{.*\})", raw, re.DOTALL)
    if not match:
        return None, "JSONが見つからない"
    extracted = match.group()
    try:
        obj = json.loads(extracted)
        return obj, None
    except Exception as e:
        # 失敗箇所付近のスニペットを付与
        msg = str(e)
        m2 = re.search(r"char (\d+)", msg)
        snippet = ""
        if m2:
            pos = int(m2.group(1))
            start = max(0, pos - 80)
            end = min(len(extracted), pos + 80)
            snippet = f"\n[先頭からのbyte位置 {pos}]\n...{extracted[start:pos]}<<<HERE>>>{extracted[pos:end]}..."
        return None, f"{msg}{snippet}"


def dump_one(label: str, post_type: str, random_seed: int = None):
    if random_seed is not None:
        random.seed(random_seed)
    _captured.clear()
    print(f"\n===== {label} (post_type={post_type}, seed={random_seed}) =====")
    try:
        result = writer.generate_patterns(DUMMY_PRODUCT, post_type=post_type)
    except Exception as e:
        print(f"[ERROR] generate_patterns例外: {e}")
        result = None

    if not _captured:
        print("[ERROR] ask_medium 呼び出しが捕捉されなかった")
        return

    cap = _captured[-1]
    raw = cap["raw"]
    prompt = cap["prompt"]

    # ファイルに追記
    with open(DUMP_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n\n====================== {label} ======================\n")
        f.write(f"[post_type] {post_type}\n")
        f.write(f"[raw length] {len(raw)} chars\n")
        f.write(f"[raw ends with] ...{raw[-80:]!r}\n")
        f.write(f"[prompt length] {len(prompt)} chars\n")
        f.write("---------- RAW RESPONSE START ----------\n")
        f.write(raw)
        f.write("\n---------- RAW RESPONSE END ----------\n")

    parsed, err = _try_parse(raw)
    print(f"[raw length] {len(raw)} chars")
    print(f"[raw最終80文字] {raw[-80:]!r}")
    if err is None:
        print(f"[parse] OK")
        if isinstance(parsed, list):
            print(f"  list len={len(parsed)}")
            for i, item in enumerate(parsed[:3]):
                s = str(item)[:80]
                print(f"  [{i}] {s}")
        elif isinstance(parsed, dict):
            posts = parsed.get("posts", [])
            print(f"  dict.posts len={len(posts)}")
            for i, item in enumerate(posts[:3]):
                s = str(item)[:80]
                print(f"  [{i}] {s}")
    else:
        print(f"[parse FAILED] {err}")
    print(f"[generate_patterns return] {type(result).__name__} len={len(result) if result is not None else 0}")


def main():
    # list型: 両サブタイプを確実に踏む（seed=1 → ane / seed=0 → save）
    dump_one("LIST_SUBTYPE_ANE (random.seed=1 → 0.1344)", "list", random_seed=1)
    dump_one("LIST_SUBTYPE_SAVE (random.seed=0 → 0.8444)", "list", random_seed=0)
    # engage型: 1件
    dump_one("ENGAGE", "engage", random_seed=0)

    print(f"\nraw dump saved to: {DUMP_PATH}")


if __name__ == "__main__":
    main()
