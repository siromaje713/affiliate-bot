"""Anthropic API直接呼び出しラッパー（タイムアウト・リトライ対応版）"""
import json
import os
import re
import time
import anthropic
from dotenv import load_dotenv

load_dotenv()

_client = None
TIMEOUT = 90       # APIタイムアウト秒数
MAX_RETRIES = 3    # 最大リトライ回数

MODEL_OPUS = "claude-opus-4-6"
MODEL_SONNET = "claude-sonnet-4-6"


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"],
            timeout=TIMEOUT,
        )
    return _client


def ask(prompt: str, retries: int = MAX_RETRIES, model: str = MODEL_SONNET) -> str:
    """プロンプトを送り、テキストで返す。タイムアウト・リトライ対応"""
    last_err = None
    for attempt in range(retries):
        try:
            response = _get_client().messages.create(
                model=model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except anthropic.APITimeoutError as e:
            last_err = e
            wait = 10 * (attempt + 1)
            print(f"[ClaudeCLI] タイムアウト (attempt {attempt+1}/{retries})、{wait}秒後リトライ...")
            time.sleep(wait)
        except anthropic.RateLimitError as e:
            last_err = e
            wait = 30 * (attempt + 1)
            print(f"[ClaudeCLI] レートリミット (attempt {attempt+1}/{retries})、{wait}秒後リトライ...")
            time.sleep(wait)
        except anthropic.APIConnectionError as e:
            last_err = e
            wait = 15 * (attempt + 1)
            print(f"[ClaudeCLI] 接続エラー (attempt {attempt+1}/{retries})、{wait}秒後リトライ...")
            time.sleep(wait)
        except Exception as e:
            print(f"[ClaudeCLI] 予期せぬエラー: {e}")
            raise
    raise RuntimeError(f"[ClaudeCLI] {retries}回リトライ失敗: {last_err}")


def ask_short(prompt: str, model: str = MODEL_SONNET, retries: int = MAX_RETRIES) -> str:
    """短文用ask。max_tokens=256でリプライ生成等に使う。"""
    last_err = None
    for attempt in range(retries):
        try:
            response = _get_client().messages.create(
                model=model,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except anthropic.APITimeoutError as e:
            last_err = e
            time.sleep(5 * (attempt + 1))
        except anthropic.RateLimitError as e:
            last_err = e
            time.sleep(15 * (attempt + 1))
        except anthropic.APIConnectionError as e:
            last_err = e
            time.sleep(10 * (attempt + 1))
        except Exception as e:
            print(f"[ClaudeCLI] ask_short予期せぬエラー: {e}")
            raise
    raise RuntimeError(f"[ClaudeCLI] ask_short {retries}回リトライ失敗: {last_err}")


def ask_medium(prompt: str, model: str = MODEL_SONNET, retries: int = MAX_RETRIES) -> str:
    """中間サイズ用ask。max_tokens=512。投稿生成等に使う。"""
    last_err = None
    for attempt in range(retries):
        try:
            response = _get_client().messages.create(
                model=model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except anthropic.APITimeoutError as e:
            last_err = e
            time.sleep(8 * (attempt + 1))
        except anthropic.RateLimitError as e:
            last_err = e
            time.sleep(20 * (attempt + 1))
        except anthropic.APIConnectionError as e:
            last_err = e
            time.sleep(10 * (attempt + 1))
        except Exception as e:
            print(f"[ClaudeCLI] ask_medium予期せぬエラー: {e}")
            raise
    raise RuntimeError(f"[ClaudeCLI] ask_medium {retries}回リトライ失敗: {last_err}")


def ask_json(prompt: str, model: str = MODEL_SONNET) -> any:
    """JSONを返すプロンプトを送り、パース済みオブジェクトで返す"""
    raw = ask_medium(prompt, model=model)
    match = re.search(r"(\[.*\]|\{.*\})", raw, re.DOTALL)
    if not match:
        raise ValueError(f"JSONが見つからない: {raw[:200]}")
    return json.loads(match.group())


def ask_plain(
    prompt: str,
    prefill: str = "",
    max_tokens: int = 256,
    model: str = MODEL_SONNET,
    retries: int = MAX_RETRIES,
) -> str:
    """プレーンテキスト返却ask。前置き・説明を抑えたいときに使う。

    - prefill を渡すと assistant メッセージとして末尾に追加され、Claude は続きから生成する。
      前置き混入の抑制に有効（例: prefill="「"）。
    - max_tokens は呼び出し側で指定可能（デフォルト256）。
    - 返却は prefill + 生成文字列 の strip() 済みプレーンテキスト。
    """
    messages = [{"role": "user", "content": prompt}]
    if prefill:
        messages.append({"role": "assistant", "content": prefill})
    last_err = None
    for attempt in range(retries):
        try:
            response = _get_client().messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
            )
            text = response.content[0].text
            return (prefill + text).strip()
        except anthropic.APITimeoutError as e:
            last_err = e
            time.sleep(5 * (attempt + 1))
        except anthropic.RateLimitError as e:
            last_err = e
            time.sleep(15 * (attempt + 1))
        except anthropic.APIConnectionError as e:
            last_err = e
            time.sleep(10 * (attempt + 1))
        except Exception as e:
            print(f"[ClaudeCLI] ask_plain予期せぬエラー: {e}")
            raise
    raise RuntimeError(f"[ClaudeCLI] ask_plain {retries}回リトライ失敗: {last_err}")
