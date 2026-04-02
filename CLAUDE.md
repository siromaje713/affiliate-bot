# affiliate-bot 現状（毎回更新）
最終更新：2026-04-02

## 稼働状況
- postモード cron: crn-d72ovqm3jp1c7386q0fg（JST 9/13/17/21時）
- replyモード cron: crn-d741a6q4d50c73bvbavg（JST 11/15/19/23時）
- healthcheck cron: 作成中

## 完了済み（2026-04-02）
- ANTHROPIC_API_KEY未設定による投稿停止 → 復旧済み（UTC 13:00手動テストで確認）
- affiliate-bot-share env groupをpost/reply両cronにリンク済み
- GH_PAT / BENCHMARK_ACCOUNT_IDS をRender env groupに追加済み
- scrape_benchmark.yml: 毎週水曜 JST 6:00 GitHub Actionsで自動実行
- Threadsトークン月次自動更新（refresh_threads_token.yml）
- Render環境変数週次同期（sync_render_env.yml）
- ベンチマークアカウント5件確定（下記参照）

## 既知の問題
- GitHub UIでの既存ファイル編集禁止（orchestrator.pyが破損する）→ 必ずClaude Code経由
- ベンチマークアカウントを15件に拡張する作業が途中（現在5件）

## 次にやること（優先順）
1. ベンチマークアカウントを15件に拡張（Coworkで調査継続）
2. apply_research.yml を実装（Coworkリサーチ→自動学習パイプライン）
3. healthcheck cronをRenderに追加

---

# Coworkリサーチ自動学習パイプライン（2日1回）

## 設計思想
リサーチエージェント（Playwright）をCoworkに置き換え。
Coworkがベンチマーク15件を目視巡回 → JSONをpush → GitHub Actionsが自動でwinning_patterns.jsonに統合。

## フロー
```
【2日に1回・手動起動】
Cowork起動
  → ベンチマーク15件を巡回（直近48時間・いいね100+投稿を収集）
  → フックパターン・感情トリガー・商品カテゴリをJSONに整形
  → docs/research_YYYYMMDD.json をGitHubにpush

【自動・push検知】
GitHub Actions（apply_research.yml）
  → research_*.json を検知してトリガー
  → Claude APIでフックパターンを分析
  → winning_patterns.json に統合・上位10件に絞る
  → コミット → 次のRender cron実行時に反映
```

## Cowork起動時の固定プロンプト
```
docs/research_latest.json を読み込んで現状把握。
ベンチマーク15件（BENCHMARK_ACCOUNT_IDS参照）を巡回して
直近48時間のいいね100+投稿を収集。
フックの冒頭パターン・感情トリガー・商品カテゴリをJSONで出力して
docs/research_YYYYMMDD.jsonとしてGitHubにpushして。
```

## Slackリマインダー（2日に1回 JST 8:00）
GitHub Actionsで通知送信 → 「Coworkリサーチの時間です」

## 軽量化される部分
- Playwright/Chromiumのインストールコスト削減（GitHub Actionsで毎週5〜10分かかってた）
- Threads APIの投稿取得ループ不要（API制限リスク減）
- scrape_benchmark.yml（週次）はCoworkリサーチ（2日1回）に置き換え可能

## 残すもの
- insights_analyzer.py（自分の投稿のいいね分析）→ APIで自動取得が正解
- winning_patterns.json のGitHub永続化

---

# ベンチマークアカウント

## 確定5件（拡張目標：15件）
選定基準：直近1週間以内に投稿あり かつ いいね100件以上の投稿あり

| アカウント | 直近投稿 | いいね100+ | 特徴 |
|-----------|---------|-----------|------|
| popo.biyou | 2時間前 | 244・648 | Amazon系・垢抜け |
| km.room | 活発 | あり | 1.2万人・楽天ROOM |
| momo_cosme_b | 1時間前 | 396・1487 | 30代美容・Amazon |
| kajierimakeup | 2026/03/15 | 238 | 2.6万人・メイクのプロ |
| ior_coco | 9時間前 | 349・976 | 育児×美容 |

## 次回追加候補（Cowork調査継続）
reimama_select, _nurse_beauty_, minamininaritaiol, nana_beauty1225, arasa.300 他

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

## 3つのツールの役割分担

### Cowork（デスクトップアプリ・ブラウザ操作可能）
- 担当：ベンチマークリサーチ・競合分析・設計書作成・research_YYYYMMDD.jsonのpush
- なぜ：Claude in Chromeでブラウザを操作できる唯一のツール。Threadsを目視確認できる
- 成果物：docs/research_YYYYMMDD.json、.mdファイル（設計書など）
- 制約：セッションごとにリセット。文脈はdocs/research_latest.jsonに全部書き出すこと

### Claude AI（claude.ai チャット・プロジェクト機能）
- 担当：投稿文生成・プロンプト改善・戦略の壁打ち・マルチエージェント設計
- なぜ：プロジェクト機能でCLAUDE.mdを常時保持。対話型の改善が得意
- 成果物：投稿テンプレ、フックパターン、プロンプト設計、戦略メモ
- 制約：ブラウザ操作不可。ファイルの直接保存不可

### Claude Code（ターミナルCLI）
- 担当：コード実装・API接続・Git管理・デプロイ・バグ修正
- なぜ：リポジトリ全体を把握した上でコードを書ける
- 成果物：Pythonスクリプト、GitHub Actions yml、Renderデプロイ設定
- 制約：ブラウザ操作不可

## 同期フロー
```
Cowork（リサーチ・docs/research_YYYYMMDD.json push）
  ↓ GitHub Actions自動トリガー
apply_research.yml（Claude APIで分析・winning_patterns.json更新）
  ↓ 次のRender cron実行時に反映
Render（投稿生成・posting）
  ↓ insights_analyzer.pyがいいね分析
Claude AI（戦略改善・プロンプト設計）
  ↓
Claude Code（実装・デプロイ）
```

## タスク別使い分け早見表
| やりたいこと | ツール | 理由 |
|------------|-------|------|
| ベンチマークアカウントのリサーチ | Cowork | ブラウザ操作でThreadsを巡回 |
| API料金・仕様の調査 | Cowork | Web検索+ブラウザで公式ドキュメント確認 |
| 設計書・企画書の作成 | Cowork | ファイル作成・保存が可能 |
| 投稿文のフック・本文・CTA設計 | Claude AI | プロジェクト内で文脈保持しながら改善 |
| マルチエージェントのプロンプト設計 | Claude AI | 対話型で繰り返し改善 |
| 投稿戦略の壁打ち | Claude AI | CLAUDE.md参照しながら議論 |
| n8nワークフロー実装 | Claude Code | コード生成・テスト |
| Threads/Instagram API接続 | Claude Code | トークン取得・リクエスト実装 |
| orchestrator.pyバグ修正 | Claude Code | リポジトリ全体を見てデバッグ |
| Renderデプロイ・env設定 | Claude Code | CLIでデプロイ操作 |
| 投稿結果の検証・改善案出し | Cowork + Claude AI | データ確認→戦略改善 |

---

# プロジェクト概要
楽天アフィリエイト×スレッズの完全自動投稿システム。最終目標：月50万円の自動収益化。

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
- postモードbuildCommand：`pip install autopep8 -q && autopep8 --in-place --aggressive orchestrator.py && pip install -r requirements.txt`

## 投稿生成のマルチエージェント設計
1. リサーチ：Coworkが2日1回ベンチマーク巡回 → docs/research_YYYYMMDD.json
2. フックエージェント：冒頭1行を3パターン生成・スコアリング（winning_patterns.json参照）
3. 本文エージェント：109文字制限で商品訴求を書く
4. 品質チェックエージェント：訴求力をスコアリング・差し戻し
5. 投稿エージェント：スレッズに投稿・反応データ収集

---

# 横展開プロジェクト（別リポジトリ）
- fortune-bot：占い＋恋愛＋副業のThreads横展開 → LINE公式→有料鑑定・電話占いアフィリ
- catman-video：AI動画（猫×男）Instagram/TikTok → Fal.ai×Kling API（$0.14/本・10000本≒21万円）

---

# 絶対ルール（違反禁止）
- orchestrator.pyを含む既存ファイルの編集はClaude Code経由のみ
- GitHub UIでの既存ファイル編集は禁止（ファイルが破損する）
- git push --force禁止・rm -rf禁止
- APIキー・トークンをログに出力しない
- 新規コードにstr|None等Python 3.10+構文を使わない（Renderが3.9）
- コード変更後は必ず `python3 -c "import orchestrator"` で構文チェック

# Claudeへの必須指示
- orchestrator.pyはGitHub UIで直接編集禁止（必ずClaude Code経由）
- 起動時は必ずCLAUDE.mdを読んで現状把握してから作業開始
- ユーザーが知らなそうなリスク・落とし穴・コストは先に指摘する
- 複数の選択肢がある場合はメリット・デメリットを比較してから推奨する
