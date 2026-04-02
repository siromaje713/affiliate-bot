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
- scrape_benchmark.yml → Coworkリサーチに置き換え（下記参照）
- Threadsトークン月次自動更新（refresh_threads_token.yml）
- Render環境変数週次同期（sync_render_env.yml）
- ベンチマークアカウント5件確定・追加調査継続中

## 既知の問題
- GitHub UIでの既存ファイル編集禁止（orchestrator.pyが破損する）→ 必ずClaude Code経由
- ベンチマークアカウントを追加調査中

## 次にやること（優先順）
1. apply_research.yml を実装（Coworkリサーチ→自動学習パイプライン）
2. ベンチマークアカウントを追加（上限なし・基準を満たすものを随時追加）
3. healthcheck cronをRenderに追加

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
BENCHMARK_ACCOUNT_IDS のアカウントを全件巡回して
直近48時間のいいね100+投稿を収集。
フックの冒頭パターン・感情トリガー・商品カテゴリをJSONで出力して
docs/research_YYYYMMDD.jsonとしてGitHubにpushして。
```

## GitHub Actions自動処理（push検知で起動）
```yaml
# .github/workflows/apply_research.yml
on:
  push:
    paths:
      - 'docs/research_*.json'
# → Claude APIでフックパターンを分析
# → winning_patterns.json に統合・上位10件に絞る
# → コミット → 次のRender cron実行時に反映
```

## Slackリマインダー（2日に1回 JST 8:00）
GitHub Actionsで「Coworkリサーチの時間です」を自動通知

## 現行との比較
| 項目 | 旧（Playwright自動） | 新（Cowork置き換え） |
|------|-------------------|-------------------|
| コスト | API + Playwright実行 | Coworkセッション内無料 |
| 精度 | DOM解析のみ | 目視確認・文脈理解あり |
| 停止アカウント除外 | 掴みやすい | リアルタイムで判断可 |
| 頻度 | 週1回 | 2日1回 |

---

# ベンチマークアカウント（上限なし・基準を満たすものを随時追加）

## 選定基準
- 直近1週間以内に投稿あり
- いいね100件以上の投稿あり
- ジャンル：美容・スキンケア・コスメ・メイク・垢抜け

## 確定リスト（現在5件）
| アカウント | 直近投稿 | いいね100+ | 特徴 |
|-----------|---------|-----------|------|
| popo.biyou | 2時間前 | 244・648 | Amazon系・垢抜け |
| km.room | 活発 | あり | 1.2万人・楽天ROOM |
| momo_cosme_b | 1時間前 | 396・1487 | 30代美容・Amazon |
| kajierimakeup | 2026/03/15 | 238 | 2.6万人・メイクのプロ |
| ior_coco | 9時間前 | 349・976 | 育児×美容 |

## 調査継続中（Coworkで確認予定）
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

## 役割分担

### Cowork（ブラウザ操作・リサーチ専門）
- 担当：ベンチマーク巡回・競合分析・docs/research_YYYYMMDD.json のpush
- 制約：セッションごとにリセット。必ずdocs/research_latest.jsonに書き出すこと

### Claude AI（このチャット・戦略設計専門）
- 担当：投稿文生成・プロンプト改善・戦略の壁打ち・CLAUDE.md更新
- 運用：Coworkのリサーチ結果をここに貼れば自動でCLAUDE.md更新・GitHub push

### Claude Code（実装専門）
- 担当：コード実装・API接続・Git管理・デプロイ・バグ修正
- 起動時：「CLAUDE.mdを読んで続きをやって」で即再開

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

# プロジェクト概要（affiliate-bot）
美容特化Threads自動投稿×Amazonアフィリエイト。最終目標：月50万円。

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

## 投稿生成パイプライン
1. リサーチ：Coworkが2日1回ベンチマーク巡回 → docs/research_YYYYMMDD.json push
2. 学習：apply_research.yml → winning_patterns.json 自動更新
3. 生成：HookOptimizer → Writer（109文字・winning_patterns参照）
4. 投稿：Threads API → リプライにAmazonアフィリリンク
5. 分析：insights_analyzer.py → いいね上位を学習 → ループ

---

# 別プロジェクト（このリポジトリとは完全分離）
- fortune-bot：占い専用Threads → 別リポジトリで管理
- catman-video：AI動画（猫×男）Instagram/TikTok → 別リポジトリで管理
※ このCLAUDE.mdには記載しない

---

# 絶対ルール（違反禁止）
- orchestrator.pyを含む既存ファイルの編集はClaude Code経由のみ
- GitHub UIでの既存ファイル編集は禁止（ファイルが破損する）
- git push --force禁止・rm -rf禁止
- APIキー・トークンをログに出力しない
- 新規コードにstr|None等Python 3.10+構文を使わない（Renderが3.9）
- コード変更後は必ず `python3 -c "import orchestrator"` で構文チェック
- 占いや他プロジェクトの内容をこのファイルに混入しない

# Claudeへの必須指示
- 起動時は必ずCLAUDE.mdを読んで現状把握してから作業開始
- ユーザーが知らなそうなリスク・落とし穴・コストは先に指摘する
- 複数の選択肢がある場合はメリット・デメリットを比較してから推奨する
- このプロジェクトは美容Threads専用。他プロジェクトの話が出たら別リポジトリで対応
