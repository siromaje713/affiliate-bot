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


def ask_json(prompt: str, model: str = MODEL_SONNET) -> any:
    """JSONを返すプロンプトを送り、パース済みオブジェクトで返す"""
    raw = ask(prompt, model=model)
    match = re.search(r"(\[.*\]|\{.*\})", raw, re.DOTALL)
    if not match:
        raise ValueError(f"JSONが見つからない: {raw[:200]}")
    return json.loads(match.group())
