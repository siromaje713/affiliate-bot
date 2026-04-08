# affiliate-bot 現状（毎回更新）
最終更新：2026-04-08

## 投稿設計（2026-04-08更新）
- list型（保存リスト+アフィリプ）: 30%（10サイクル中3回・counter%10 in 0,3,6）
- engage型（有益情報×煽り）: 70%（残り7回・reply_poster呼ばない）
- アフィ単体投稿: 停止中（アカウントパワー育成優先）

## 次にやること
- 投稿パフォーマンス確認（Slack通知で）
- アカウントパワーが付いたらアフィ再開を検討

## 稼働状況
- postモード cron: crn-d72ovqm3jp1c7386q0fg（JST 9/13/17/21時）
- replyモード cron: crn-d741a6q4d50c73bvbavg（JST 11/15/19/23時）

## 完了済み
- Threads API連携・投稿・リプライ自動化
- image_generator.py: Noneのみ返す（画像投稿完全停止・シャドウバン対策）
- orchestrator.py: エンゲージメント70%/アフィリ30%・起動時ランダムsleep(0-3600秒)
- writer.py: engage post_type追加
- apply_research.yml: YAMLエラー修正済み
- 作業ディレクトリ ~/affiliate-bot に一本化（~/Documents/affiliate-bot 削除済み）
- Claude Codeログイン切れ対処: claude /login で再認証

## 既知の問題
- sync_render_env.yml: Failure（未修正）

## 次にやること
1. sync_render_env.yml 修正

---

# Coworkリサーチ自動学習パイプライン（2日1回）

## Cowork起動時の固定プロンプト
```
docs/research_latest.json を読み込んで現状把握。
BENCHMARK_ACCOUNT_IDSのアカウントを全件巡回して
直近48時間のいいね100+投稿を収集。
フックの冒頭パターン・感情トリガー・商品カテゴリをJSONで出力して
docs/research_YYYYMMDD.jsonとしてGitHubにpushして。
```

## GitHub Actions
- apply_research.yml: docs/research_*.json push → winning_patterns.json更新 → Slack通知
- slack_reminder.yml: 月水金日 UTC 23:00にリマインダー

---

# ベンチマークアカウント（5件）
| アカウント | いいね100+ | 特徴 |
|-----------|-----------|------|
| popo.biyou | 244・648 | Amazon系・垢抜け |
| km.room | あり | 1.2万人・楽天ROOM |
| momo_cosme_b | 396・1487 | 30代美容 |
| kajierimakeup | 238 | 2.6万人・メイクのプロ |
| ior_coco | 349・976 | 育児×美容 |

---

# 環境変数（Render env groupに設定済み）
- ANTHROPIC_API_KEY
- THREADS_ACCESS_TOKEN（60日期限・月次自動更新あり）
- THREADS_USER_ID: 26498495833117828
- SLACK_WEBHOOK_URL
- GH_PAT
- BENCHMARK_ACCOUNT_IDS: popo.biyou,km.room,momo_cosme_b,kajierimakeup,ior_coco
- PYTHONUNBUFFERED / TZ
- THREADS_TOKEN_EXPIRES_AT: 2026-05-30

---

# ツール運用ルール
- Cowork：ベンチマーク巡回・docs/research_YYYYMMDD.json push
- Claude AI（このチャット）：戦略・CLAUDE.md更新（GitHubのrawから読み込み）
- Claude Code：~/affiliate-bot/ で起動・コード実装・Git管理

---

# プロジェクト概要
美容特化Threads自動投稿×Amazonアフィリエイト。最終目標：月50万円。
- スレッズ：@riko_cosme_lab
- Amazonアソシエイト：rikocosmelab-22（メイン）/ 楽天（サブ）
- Meta Developerアプリ：affiliate-bot（ID: 707899495683413）
- Render APIキー：rnd_EkjoD9DODsbQNf0VIrj0zfN4wkVh
- postモードCron ID：crn-d72ovqm3jp1c7386q0fg（UTC 0,4,8,12）
- replyモードCron ID：crn-d741a6q4d50c73bvbavg（UTC 2,6,10,14）
- buildCommand: pip install autopep8 -q && autopep8 --in-place --aggressive orchestrator.py && pip install -r requirements.txt

---

# 絶対ルール
- 既存ファイル編集はClaude Code経由のみ（GitHub UI禁止）
- git push --force禁止・rm -rf禁止
- APIキー・トークンをログに出力しない
- Python 3.10+構文禁止（Renderが3.9）
- 変更後は python3 -c "import orchestrator" で構文チェック

# Claudeへの必須指示
- 起動時は必ずCLAUDE.mdを読んで現状把握
- リスク・落とし穴は先に指摘する
- 美容Threads専用。占い・fortune-bot・catman-videoは別リポジトリ

# Claude Codeログイン切れ対処法
- claude /login を実行 → ブラウザでコード確認 → ターミナルに貼り付け
