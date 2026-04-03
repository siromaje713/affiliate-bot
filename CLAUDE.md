# affiliate-bot 現状（毎回更新）
最終更新：2026-04-04

## 稼働状況
- postモード cron: crn-d72ovqm3jp1c7386q0fg（JST 9/13/17/21時）
- replyモード cron: crn-d741a6q4d50c73bvbavg（JST 11/15/19/23時）
- healthcheck cron: 作成中

## 完了済み
- Threads API連携・投稿・リプライ自動化
- ANTHROPIC_API_KEY未設定による投稿停止 → 復旧済み
- Render環境変数週次同期（sync_render_env.yml）
- Threadsトークン月次自動更新（refresh_threads_token.yml）
- apply_research.yml・slack_reminder.yml 追加済み
- ベンチマークアカウント5件確定

## 既知の問題
- GitHub UIでの既存ファイル編集禁止（orchestrator.pyが破損する）→ 必ずClaude Code経由

## 次にやること（優先順）
1. ベンチマークアカウントを追加（基準を満たすものを随時追加）
2. healthcheck cronをRenderに追加

---

# Coworkリサーチ自動学習パイプライン（2日1回）

## 運用フロー（ユーザー操作）
```
【2日に1回】
① Coworkを起動
② 下記「固定プロンプト」を実行
③ docs/research_YYYYMMDD.json がGitHubにpushされる
④ あとは全自動（GitHub Actions → winning_patterns.json更新 → 次の投稿に反映）
```

## Cowork起動時の固定プロンプト
```
docs/research_latest.json を読み込んで現状把握。
BENCHMARK_ACCOUNT_IDSのアカウントを全件巡回して
直近48時間のいいね100+投稿を収集。
フックの冒頭パターン・感情トリガー・商品カテゴリをJSONで出力して
docs/research_YYYYMMDD.jsonとしてGitHubにpushして。
```

## GitHub Actions自動処理（push検知で起動）
`.github/workflows/apply_research.yml`: `docs/research_*.json` push検知 → `winning_patterns.json` 自動更新 → Slack通知

## Slackリマインダー（2日に1回 JST 8:00）
- slack_reminder.yml → 月水金日 UTC 23:00に通知

---

# ベンチマークアカウント

## 選定基準
- 直近1週間以内に投稿あり
- いいね100件以上の投稿あり
- ジャンル：美容・スキンケア・コスメ・メイク・垢抜け

## 確定リスト（5件）
| アカウント | いいね100+ | 特徴 |
|-----------|-----------|------|
| popo.biyou | 244・648 | Amazon系・垢抜け |
| km.room | あり | 1.2万人・楽天ROOM |
| momo_cosme_b | 396・1487 | 30代美容 |
| kajierimakeup | 238 | 2.6万人・メイクのプロ |
| ior_coco | 349・976 | 育児×美容 |

---

# 環境変数（affiliate-bot-share env groupに設定済み）
- ANTHROPIC_API_KEY
- THREADS_ACCESS_TOKEN（60日期限・月次自動更新あり）
- THREADS_USER_ID: 26498495833117828
- SLACK_WEBHOOK_URL
- GH_PAT
- BENCHMARK_ACCOUNT_IDS: popo.biyou,km.room,momo_cosme_b,kajierimakeup,ior_coco
- PYTHONUNBUFFERED / TZ

---

# ツール運用ルール

## 役割分担
- Cowork：ベンチマーク巡回・競合分析・docs/research_YYYYMMDD.json のpush
- Claude AI（このチャット）：投稿文生成・戦略・CLAUDE.md更新
- Claude Code：コード実装・Git管理・デプロイ・バグ修正（起動時「CLAUDE.mdを読んで続きをやって」で即再開）

## データ連携フロー
```
Cowork（リサーチ）
  → docs/research_YYYYMMDD.json をpush
  → GitHub Actions（apply_research.yml）が自動起動
  → winning_patterns.json 更新
  → Render cronが次の投稿生成時に参照
  → insights_analyzer.py がいいね分析 → 学習ループ
```

---

# プロジェクト概要
美容特化Threads自動投稿×楽天・Amazonアフィリエイト。最終目標：月50万円。

## アカウント情報
- スレッズ：@riko_cosme_lab
- ジャンル：美容全般（スキンケア・美顔器メイン）
- Amazonアソシエイト：rikocosmelab-22
- 楽天アフィリエイト：登録済み
- Meta Developerアプリ：affiliate-bot（ID: 707899495683413）
- Render APIキー：rnd_EkjoD9DODsbQNf0VIrj0zfN4wkVh

## Renderサービス情報
- postモードCron ID：crn-d72ovqm3jp1c7386q0fg（JST 9/13/17/21時・UTC 0,4,8,12）
- replyモードCron ID：crn-d741a6q4d50c73bvbavg（JST 11/15/19/23時・UTC 2,6,10,14）
- buildCommand：`pip install autopep8 -q && autopep8 --in-place --aggressive orchestrator.py && pip install -r requirements.txt`

## 投稿生成パイプライン
1. Coworkが2日1回ベンチマーク巡回 → docs/research_YYYYMMDD.json push
2. apply_research.yml → winning_patterns.json 自動更新
3. HookOptimizer → Writer（109文字・winning_patterns参照）
4. Threads API → リプライに楽天/Amazonアフィリリンク
5. insights_analyzer.py → いいね上位を学習 → ループ

---

# 絶対ルール
- orchestrator.pyを含む既存ファイルの編集はClaude Code経由のみ
- GitHub UIでの既存ファイル編集禁止
- git push --force禁止・rm -rf禁止
- APIキー・トークンをログに出力しない
- Python 3.10+構文禁止（Renderが3.9）
- コード変更後は必ず `python3 -c "import orchestrator"` で構文チェック

# Claudeへの必須指示
- 起動時は必ずCLAUDE.mdを読んで現状把握
- リスク・落とし穴は先に指摘する
- このプロジェクトは美容Threads専用。占い・fortune-bot・catman-videoは別リポジトリ
