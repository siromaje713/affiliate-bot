# affiliate-bot 現状（毎回更新）
最終更新：2026-04-09

## 投稿設計
- engage型（有益情報×煽り短文）: 70%（reply_posterなし）
- list型（保存リスト型）: 30%（reply_posterなし・アフィリプ停止中）
- アフィ単体投稿: 停止中（アカウントパワー育成優先）
- 起動時jitter: random.uniform(-1800, 1800) → max(0, x)（前後30分）

## 投稿スタイル（黄金パターン）
1. 知識暴露型：「[事実]って[数字/根拠]。[返信誘導]？😳」
2. 行動訂正型：「[NG行動]してる人まだいる？[正解]が正解。やってた？」
3. やり方暴露型：「[方法]って[意外な事実]知ってた？[返信誘導]🙌」
4. 保存型リスト：「[テーマ]【保存用】
悩み→解決策×5〜8項目
全部やらなくていい。今いちばん気になるやつだけやれ。」

## 稼働状況
- postモード cron: crn-d72ovqm3jp1c7386q0fg（JST 9/13/17/21時・前後30分jitter）
- replyモード cron: crn-d741a6q4d50c73bvbavg（JST 11/15/19/23時）

## 完了済み（2026-04-08）
- 全投稿タイプのreply_poster停止（アフィリプなし）
- engage/list型のqualityチェックスキップ（二重保証）
- writer.py: engage・list・buzz型プロンプト刷新
- orchestrator.py: list/engage分岐・jitter前後30分
- buzz_researcher.py: BENCHMARK_ACCOUNT_IDSから動的読み込み
- insights_analyzer.py: views取得追加
- engage_agent.py: 他人投稿へ1日5件リプ・会話クローズ
- auto_research.yml: 毎日JST 8時実行に変更
- 作業ディレクトリ ~/affiliate-bot に一本化
- sync_render_env.yml/merge_env.py 削除（env groupはRenderダッシュボードで直接管理）
- .gitignore に .claude/settings.json と logs/ を追加
- list型締め文を命令形→共感トーンに変更（agents/writer.py:357,373）

## 既知の問題
- クローズリプ（相手リプ検出→自動返信）: Threads API挙動次第・Slackで要確認

## 次にやること
- Slackで投稿品質・リプ動作を確認
- アカウントパワーが付いたらlist型にアフィリプ再開を検討
- ベンチマークアカウントを15件に拡張（現在5件）

---

# Coworkの使い方
プロンプト冒頭に以下を入れるだけでCLAUDE.mdを読める：
```
まず以下のURLのCLAUDE.mdを読んで現状を把握してから作業して。
https://raw.githubusercontent.com/siromaje713/affiliate-bot/main/CLAUDE.md
```

## Cowork担当タスク（毎日自動・手動不要）
- auto_research.yml が毎日JST 8時に自動実行
- ベンチマーク巡回→buzz_patterns.json更新→winning_patterns.json更新
- Coworkの手動作業は不要になった

---

# ベンチマークアカウント（5件・拡張予定）
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
- Cowork：CLAUDE.mdのURLを冒頭に渡すだけ・手動作業不要
- Claude AI（このチャット）：戦略・CLAUDE.md更新・GitHubのrawから読み込み
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
