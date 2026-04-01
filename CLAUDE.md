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

## 完了済み（本日含む）
- Threads API連携・投稿・リプライ自動化
- Renderデプロイ済み（postモードCron×4回/日 + replyモードCron×4回/日）
- マルチエージェントパイプライン稼働中（BuzzAnalyzer→HookOptimizer→Writer→Poster→ReplyPoster）
- Amazonアフィリエイトリンク自動付与（replyに商品URLを添付）
- Amazon商品画像取得・Threads画像投稿対応
- サイクルローテーション商品選択（41商品・ASIN重複除外済み）
- ベンチマークアカウント共感リプライ（--mode engage、手動or別cron）
- 自投稿へのリプライ自動返信（--mode reply・自分自身へのリプライ除外済み）
- insights_analyzer：自分の投稿いいね上位5件＋ベンチマークいいね100超えをwinning_patterns.jsonに記録（直近30投稿・post_dateフィールドあり）
- winning_patterns.jsonをGitHubに永続化（github_sync.py経由・Renderリセット対策）
- Playwright製ベンチマークスクレイパー（scripts/scrape_benchmark.py）→ popo.biyouで17件収集確認済み
- 手動ベンチマーク登録スクリプト（scripts/import_benchmark.py）
- healthcheck.py：最終投稿から5時間超でSlack警告（render.yamlに毎時cronあり）
- GH_PAT：GitHub Secretsに登録済み（workflowスコープ付き・値はRenderにも要設定）
- Slack通知：投稿完了（🛒URL＋🔗ThreadsURL）・エラー・トークン期限警告
- writer.py：厳守ルール（ハッシュタグ禁止・続きはリプ欄👇・トレンドフック優先）
- conversation_agent.py：自分以外のリプライのみ対象（/meで自username取得しフィルタ）
- Python 3.9互換修正：threads_api.py・engage_agent.py の str|None → 省略済み
- orchestrator.py：GitHub UI編集で壊れた際に8523757版から復元済み・587行・正常動作確認
- BENCHMARK_ACCOUNT_IDS：popo.biyou,minnabiyou,cosme_mania_official,skincare_otaku_jp（ローカル.env・.env.example）

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
### Renderに設定済み（postモード・replyモード両方）
- ANTHROPIC_API_KEY
- THREADS_ACCESS_TOKEN（60日期限）
- THREADS_USER_ID：26498495833117828
- SLACK_WEBHOOK_URL

### Renderに未設定（要追加）
- GH_PAT：（GitHub Secretsに登録済み・値はRenderダッシュボードで設定）
- BENCHMARK_ACCOUNT_IDS：popo.biyou,minnabiyou,cosme_mania_official,skincare_otaku_jp
- THREADS_TOKEN_EXPIRES_AT：トークン発行日+60日（YYYY-MM-DD）

## 既知の問題・注意点
- **orchestrator.pyをGitHub UIで直接編集すると壊れる** → Claude Code経由のみで編集
- PATのworkflowスコープ付きPATは取得済みだが.github/workflows/のpushは未テスト
- ベンチマークアカウント（minnabiyou・cosme_mania_official・skincare_otaku_jp）は存在しないか非公開 → 有効なアカウントに差し替え要
- Threadsアクセストークンは60日で期限切れ → 手動更新が必要
- Python 3.9非互換構文（str|None等）はRenderでエラー → 新規追加時は省略またはOptional[str]を使う
- postモードのbuildCommandにautopep8 --aggressiveが含まれる（Renderサーバー上でのみ動作・フォーマット変更のみ）
- replyモードcronの直近2回はsucceeded・postモードcronの最新デプロイはlive（2026-04-01確認）
- **アフィリエイトリプライ動作確認済み（2026-04-02）**：03-31の全4cron実行（UTC 0/4/8/12）すべてでアフィリリプライが正常に付いていることを確認。04-01の2件無リプライは①手動投稿（ボットではない）②orchestrator.py破損期のcron実行が原因。現在は修復済み。さらにtry/except+Slackエラー通知を追加して障害の可視性を向上。

## 次のTODO（優先順）
1. **次回cron実行確認**：次回postモードCron実行後（JST 9:00）のSlack通知でリプライが正常に付くか確認
2. **Renderダッシュボード**でreplyモード・postモード両方に以下の環境変数を追加：
   - GH_PAT
   - BENCHMARK_ACCOUNT_IDS
   - THREADS_TOKEN_EXPIRES_AT
3. **有効なベンチマークアカウント**に差し替え（現在minnabiyou等が0件）
4. **scrape_benchmark.py定期実行**：Renderに--mode scrapeを追加するか検討
5. **.github/workflows/weekly_research.yml**のcron変更（3日ごと）をGitHub UIまたはworkflowスコープPATでpush

# Claudeへの必須指示
- orchestrator.pyはGitHub UIで直接編集禁止（必ずClaude Code経由）
- git push --force禁止・rm -rf禁止
- APIキー・トークンをログに出力しない
- 新規コードに str|None や list[str] 等Python 3.10+構文を使わない（Renderが3.9の可能性）
- コード変更後は必ず `python3 -c "import orchestrator"` で構文チェック
