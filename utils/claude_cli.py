"""Anthropic API直接呼び出しラッパー"""
import json
import os
import re
import anthropic
from dotenv import load_dotenv

load_dotenv()

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def ask(prompt: str) -> str:
    """プロンプトを送り、テキストで返す"""
    response = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def ask_json(prompt: str) -> any:
    """JSONを返すプロンプトを送り、パース済みオブジェクトで返す"""
    raw = ask(prompt)
    match = re.search(r"(\[.*\]|\{.*\})", raw, re.DOTALL)
    if not match:
        raise ValueError(f"JSONが見つからない: {raw[:200]}")
    return json.loads(match.group())
