# プロジェクト概要
楽天アフィリエイト×スレッズの完全自動投稿システム。最終目標：月50万円の自動収益化。

# アカウント情報
- スレッズ：@riko_cosme_lab
- ジャンル：美容全般（スキンケア・美顔器メイン）
- Amazonアソシエイト：rikocosmelab-22
- 楽天アフィリエイト：登録済み（一部商品のみ楽天URL設定済み）

# 現在の進捗
最終更新日：2026-04-01

## 完了済み
- Threads API連携・投稿・リプライ自動化
- Renderデプロイ済み（postモードCron×3本 + replyモードCron）
- マルチエージェントパイプライン稼働中（BuzzAnalyzer→HookOptimizer→Writer→Poster→ReplyPoster）
- Amazonアフィリエイトリンク自動付与（replyに商品URLを添付）
- Amazon商品画像取得・Threads画像投稿対応
- サイクルローテーション商品選択（41商品・ASIN重複除外済み）
- ベンチマークアカウント共感リプライ（--mode engage）
- 自投稿へのリプライ自動返信（--mode reply・自分自身へのリプライ除外済み）
- insights_analyzer：自分の投稿いいね上位5件＋ベンチマークいいね100超えをwinning_patterns.jsonに記録
- winning_patterns.jsonをGitHubに永続化（github_sync.py経由・Renderリセット対策）
- Playwright製ベンチマークスクレイパー（scripts/scrape_benchmark.py）
- 手動ベンチマーク登録スクリプト（scripts/import_benchmark.py）
- healthcheck.py：最終投稿から5時間超でSlack警告
- GH_PAT GitHub Secretsに登録済み
- Slack通知：投稿完了・エラー・トークン期限警告

## 主要ファイル構成
- `orchestrator.py`：全エージェント統括・587行・商品41種
- `agents/writer.py`：投稿生成（buzz/link型・トレンドフック・続きはリプ欄👇）
- `agents/conversation_agent.py`：自投稿リプライ返信
- `agents/engage_agent.py`：ベンチマーク共感リプライ
- `agents/insights_analyzer.py`：勝ちパターン収集・GitHub永続化
- `utils/threads_api.py`：Threads APIラッパー・Amazon画像取得
- `github_sync.py`：winning_patterns.jsonをGitHubにpush
- `healthcheck.py`：投稿停止監視
- `render.yaml`：Renderデプロイ設定（postモード×3 + healthcheck）

## 環境変数（Renderに要設定）
- ANTHROPIC_API_KEY
- THREADS_ACCESS_TOKEN（60日期限・THREADS_TOKEN_EXPIRES_ATで期限監視）
- THREADS_USER_ID：26498495833117828
- SLACK_WEBHOOK_URL
- BENCHMARK_ACCOUNT_IDS：popo.biyou,minnabiyou,cosme_mania_official,skincare_otaku_jp
- GH_PAT（GitHub永続化用）
- THREADS_TOKEN_EXPIRES_AT：YYYY-MM-DD形式

## 既知の問題・注意点
- GitHub UIでorchestrator.pyを直接編集するとファイルが壊れる（Claude Code経由で編集すること）
- PATのworkflowスコープ不足のため.github/workflows/のpushが制限される
- ベンチマークアカウント（minnabiyou等）は存在しないか非公開のため0件
- Threadsアクセストークンは60日で期限切れ（要手動更新）
- Python 3.9非互換の型ヒント（str|None, list[str]等）はRenderでエラーになる → Optional[str]またはアノテーション省略で対応

## 次にやること
- RenderダッシュボードでreplyモードのenvにBENCHMARK_ACCOUNT_IDS・GH_PAT追加
- THREADS_TOKEN_EXPIRES_ATをRenderに設定
- 有効なベンチマークアカウントに差し替え

# Claudeへの必須指示
- ユーザーが知らなそうなリスク・落とし穴・コスト・制限は聞かれる前に先に指摘する
- orchestrator.pyはGitHub UIで直接編集しない（壊れる）
- git push --force禁止
- rm -rf禁止
- APIキー・トークンをログに出力しない
