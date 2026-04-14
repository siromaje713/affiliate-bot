#!/usr/bin/env python3
"""セッション終了時にCLAUDE.mdを自動更新するスクリプト"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# プロジェクトルートをパスに追加
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from utils.claude_cli import ask, MODEL_OPUS

def load_current_claude_md() -> str:
    path = PROJECT_ROOT / "CLAUDE.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""

def load_session_context() -> str:
    """stdinからhookのJSONコンテキストを読む"""
    try:
        data = json.loads(sys.stdin.read())
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        return "{}"

def update_claude_md():
    current_md = load_current_claude_md()
    session_ctx = load_session_context()
    today = datetime.now().strftime("%Y-%m-%d")

    prompt = f"""あなたはaffiliate-botプロジェクトのCLAUDE.mdを更新するアシスタントです。
今日の日付: {today}

【現在のCLAUDE.md】
{current_md}

【セッション終了コンテキスト】
{session_ctx}

上記をもとに、CLAUDE.mdを以下の構成で更新してください。
既存の「プロジェクト概要」「アカウント情報」「Claudeへの必須指示」などの固定セクションは保持し、
「現在の進捗」「次にやること」のみ今日の作業内容に合わせて更新してください。

更新ルール：
- 「現在の進捗 > 完了済み」に今日完了した作業を追加
- 「現在の進捗 > 既知の問題・バグ」セクションを追加または更新（問題があれば）
- 「次にやること」を最新の状態に更新
- 重要なファイル・設定値（ポート番号、パス、IDなど）があれば「重要な設定値」セクションに記載
- 日付を {today} に更新

CLAUDE.mdの内容のみを出力してください（説明文不要）。"""

    try:
        new_md = ask(prompt, model=MODEL_OPUS)
        # コードブロックで囲まれていたら除去
        if new_md.startswith("```"):
            lines = new_md.split("\n")
            new_md = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        out_path = PROJECT_ROOT / "CLAUDE.md"
        out_path.write_text(new_md, encoding="utf-8")
        print(f"[UpdateCLAUDE] CLAUDE.md を更新しました ({today})")
    except Exception as e:
        print(f"[UpdateCLAUDE] エラー: {e}", file=sys.stderr)

if __name__ == "__main__":
    update_claude_md()
