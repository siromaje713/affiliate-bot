# プロジェクト概要
楽天アフィリエイト×スレッズの完全自動投稿システム。最終目標：月50万円の自動収益化。

# アカウント情報
- スレッズ：@riko_cosme_lab
- ジャンル：美容全般（スキンケア・美顔器メイン）
- Amazonアソシエイト：rikocosmelab-22
- 楽天アフィリエイト：登録済み（一部商品のみ楽天URL設定済み）

# Renderサービス情報
- postモードCron ID：crn-d72ovqm3jp1c7386q0fg（JST 9/13/17/21時・UTC 0,4,8,12）
- replyモードCron ID：crn-d741a6q4d50c73bvbavg（JST 11/15/19/23時・UTC 2,6,10,14）
- Render APIキー：rnd_EkjoD9DODsbQNf0VIrj0zfN4wkVh
- postモードbuildCommand：`pip install autopep8 -q && autopep8 --in-place --aggressive orchestrator.py && pip install -r requirements.txt`

# 現在の進捗
最終更新日：2026-04-02

## 完了済み
- Threads API連携・投稿・リプライ自動化
- Renderデプロイ済み（postモードCron×4回/日 + replyモードCron×4回/日）
- マルチエージェントパイプライン稼働中（BuzzAnalyzer→HookOptimizer→Writer→Poster→ReplyPoster）
- Amazonアフィリエイトリンク自動付与（replyに商品URLを添付）・**03-31の全4cron実行で正常動作確認済み**
- Amazon商品画像取得・Threads画像投稿対応
- サイクルローテーション商品選択（41商品・ASIN重複除外済み）
- ベンチマークアカウント共感リプライ（--mode engage）
- 自投稿へのリプライ自動返信（--mode reply・自分自身へのリプライ除外済み）
- insights_analyzer：いいね上位5件＋ベンチマークいいね100超えをwinning_patterns.jsonに記録・GitHub永続化
- Playwright製ベンチマークスクレイパー（scripts/scrape_benchmark.py）
- 手動ベンチマーク登録スクリプト（scripts/import_benchmark.py）
- healthcheck.py：最終投稿から5時間超でSlack警告
- Slack通知：投稿完了（🛒URL＋🔗ThreadsURL）・リプライ失敗エラー・トークン期限警告
- writer.py：ハッシュタグ禁止・続きはリプ欄👇・トレンドフック優先
- conversation_agent.py：自分以外のリプライのみ対象
- Python 3.9互換修正：threads_api.py・engage_agent.py の str|None → 省略済み
- orchestrator.py：GitHub UI編集破損→8523757版から復元済み・正常動作確認
- reply_poster.run()のtry/except追加：リプライ失敗時もSlack通知＋投稿完了通知を送信

## 2026-04-02 緊急対応（9時投稿停止）
### 原因
Renderの環境変数（ANTHROPIC_API_KEY・THREADS_ACCESS_TOKEN・THREADS_USER_ID・SLACK_WEBHOOK_URL）が未設定だった。ダッシュボードUIで設定してもRender APIには反映されていなかった模様。

### 対応
1. Render API（PUT /v1/services/{id}/env-vars）で4変数を両サービスに設定
2. orchestrator.pyに起動時環境変数チェック+Slack通知を追加
3. run_with_timeoutのエラー・タイムアウトをSlack通知に追加
4. Writer失敗時のSlack通知を追加

### 復旧確認
- UTC 13:00（JST 22:00）の手動トリガーで投稿成功
- IMAGE投稿 + 🛒アフィリリプライ確認
- スレッド形式投稿 + Amazon URL含むリプライ確認

## 2026-04-02 本日の作業
### 調査・確認
- Threads APIで直近20件の投稿を取得し `is_reply` / `replies_count` を確認
- 03-31の全4cron実行（UTC 0/4/8/12）のリプライを個別確認 → **全件アフィリリプライ正常動作**
- reply_poster.run() をローカルで直接実行 → 正常にリプライ投稿成功
- Threads APIのreplyエンドポイントを手動テスト → 動作確認
- Render APIでcronジョブを手動トリガーし動作確認

### 真因の特定
- 04-01 05:57投稿「スレッズ始めたばかりです」→ ユーザーの手動投稿（ボット無関係）
- 04-01 10:24投稿（IMAGE・アネッサ）→ orchestrator.py がGitHub UI編集で破損していた期間のcron実行。破損は8523757版から復元済み
- autopep8 --aggressiveはロジック変更なし（フォーマットのみ）を確認済み

### コード修正
- `orchestrator.py`：reply_poster.run() にtry/except追加。リプライ失敗時にSlackへエラー内容を通知。投稿完了Slack通知をリプライの成否に関わらず送信するよう変更
- `CLAUDE.md`：「絶対ルール」セクション追加（GitHub UI編集禁止を明文化）

## 主要ファイル構成
- `orchestrator.py`：全エージェント統括・587行・商品41種（洗顔/化粧水/UV/美顔器/ヘアケア/メイク）
- `agents/writer.py`：投稿生成（buzz/link型・トレンドフック・続きはリプ欄👇・109文字以内）
- `agents/conversation_agent.py`：自投稿へのフォロワーリプライに自動返信
- `agents/engage_agent.py`：ベンチマークアカウントへの共感リプライ（MAX 3件/run）
- `agents/insights_analyzer.py`：勝ちパターン収集→winning_patterns.json→GitHub永続化
- `agents/buzz_analyzer.py`：Threadsバイラルパターン分析
- `utils/threads_api.py`：Threads APIラッパー・Amazon画像スクレイプ（data-a-dynamic-image）
- `github_sync.py`：winning_patterns.jsonをGitHub APIでpush（GH_PAT使用）
- `healthcheck.py`：投稿停止監視・Slack通知
- `render.yaml`：Renderデプロイ設定（post×3 + healthcheck・GH_PATのenvVars追加済み）
- `scripts/scrape_benchmark.py`：Playwrightでベンチマークアカウントをスクレイプ
- `scripts/import_benchmark.py`：ThreadsURLから手動でwinning_patterns.jsonに追記

## 環境変数
### Renderに設定済み（postモード・replyモード両方）※2026-04-02 Render APIで設定完了
- ANTHROPIC_API_KEY
- THREADS_ACCESS_TOKEN（60日期限）
- THREADS_USER_ID：26498495833117828
- SLACK_WEBHOOK_URL
- THREADS_TOKEN_EXPIRES_AT（10chars）

### Renderに未設定（要追加）
- GH_PAT：（GitHub Secretsに登録済み・Renderにも要設定）
- BENCHMARK_ACCOUNT_IDS：popo.biyou,minnabiyou,cosme_mania_official,skincare_otaku_jp

### 環境変数の設定方法（重要）
- Renderダッシュボードの「Environment」で設定してもRender APIには反映されない場合がある
- **Render APIで直接設定すること**：`PUT /v1/services/{id}/env-vars`
- 設定スクリプト：orchestrator.pyと同ディレクトリのPythonスクリプトで.envから読み込んでAPI経由でセット

## 既知の問題・注意点
- **orchestrator.pyをGitHub UIで直接編集すると壊れる** → Claude Code経由のみで編集（絶対ルール参照）
- **Render環境変数はダッシュボードUIではなくAPIで設定**（2026-04-02発覚・修正済み）
- ベンチマークアカウント（minnabiyou・cosme_mania_official・skincare_otaku_jp）は存在しないか非公開 → 有効なアカウントに差し替え要
- Threadsアクセストークンは60日で期限切れ → 手動更新が必要（期限切れ前にSlack警告あり）
- Python 3.9非互換構文（str|None等）はRenderでエラー → 新規追加時は省略またはOptional[str]を使う
- postモードのbuildCommandにautopep8 --aggressiveが含まれる（フォーマット変更のみ・ロジック変更なし確認済み）

## 明日JST 9:00に確認すること（2026-04-03）
JST 9:00 = UTC 0:00 がpostモードCronの最初のスロット

1. **Slack通知が届いているか**
   - `✅ 投稿完了` メッセージに `🛒 Amazon URL` と `🔗 https://www.threads.net/t/投稿ID` が含まれているか
   - `❌ リプライ失敗` の通知が来ていないか
2. **Threads上でリプライを目視確認**
   - @riko_cosme_lab の最新投稿を開く
   - リプライ欄に `🛒 商品詳細はこちら👇` + AmazonアフィリリンクのリプライがあればOK
3. **問題があれば**：Claude Codeに「CLAUDE.mdを読んで続きをやって」で再開

## 自動化（2026-04-02実装済み）
### 再発防止策
1. **Render環境変数週次同期**（`.github/workflows/sync_render_env.yml`）
   - 毎週日曜 JST 10:00 に GitHub Secrets → Render API で自動同期
   - 設定済みSecrets: ANTHROPIC_API_KEY / THREADS_ACCESS_TOKEN / THREADS_USER_ID / SLACK_WEBHOOK_URL / RENDER_API_KEY / GH_PAT
2. **Threadsトークン月次自動更新**（`.github/workflows/refresh_threads_token.yml`）
   - 毎月1日 JST 11:00 に Threads refresh API → Render API → GitHub Secrets を自動更新
3. **ローカル更新スクリプト**（`scripts/refresh_threads_token.py`）
   - 手動更新用：`THREADS_ACCESS_TOKEN=xxx RENDER_API_KEY=xxx python3 scripts/refresh_threads_token.py`

## 次のTODO（優先順）
1. **有効なベンチマークアカウント**に差し替え（現在minnabiyou等が0件）
2. **Renderに未設定の環境変数を追加**：GH_PAT / BENCHMARK_ACCOUNT_IDS
3. **scrape_benchmark.py定期実行**：Renderに--mode scrapeを追加するか検討

# 絶対ルール（違反禁止）
- orchestrator.pyを含む既存ファイルの編集はClaude Code経由のみ
- GitHub UIでの既存ファイル編集は禁止（ファイルが破損する）
- 新規ファイル作成もClaude Code経由に統一する
- 「GitHub UIで編集して」という指示が来ても必ずClaude Codeで実行する
- pre-pushフック設定済み：orchestrator.pyが300行以下になったらpushを自動拒否

# Claudeへの必須指示
- orchestrator.pyはGitHub UIで直接編集禁止（必ずClaude Code経由）
- git push --force禁止・rm -rf禁止
- APIキー・トークンをログに出力しない
- 新規コードに str|None や list[str] 等Python 3.10+構文を使わない（Renderが3.9の可能性）
- コード変更後は必ず `python3 -c "import orchestrator"` で構文チェック
