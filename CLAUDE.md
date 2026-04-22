## 新セッション開始時に必ず読む（全AI向け）

1. この CLAUDE.md
2. HANDOFF.md（前セッション引き継ぎ）
3. <https://raw.githubusercontent.com/siromaje713/bot-infrastructure-spec/main/INFRA.md>
4. <https://raw.githubusercontent.com/siromaje713/bot-infrastructure-spec/main/PATTERNS/session_startup.md>
5. 問題発生時は <https://github.com/siromaje713/bot-infrastructure-spec/tree/main/INCIDENTS> で類似事例を検索

このbotは bot-infrastructure-spec の共通資産を継承する。
認証情報は全て .env が唯一の正。CLAUDE.md に値を直書きしない。

---

# affiliate-bot

## 北極星

月50万円の自動収益（美容Threads × アフィリエイト）

## 中間目標

- 表示回数1000安定 → アフィリプ再開の判断基準
- エンゲージメント率改善（現状: view 300-500, いいね 1-3）
- 姉シリーズの安定生成確認

## ペルソナ（りこ）

27歳・敏感肌・プチプラ美容オタク。一人称「わたし」。
皮膚科クリニック勤務の姉（32歳）に仕込まれた知識で肌が変わった人。
友達にLINEするノリ。情報は正確、押し売りゼロ。
禁止：「！」多用、絵文字3連続以上、ステマ感、リンク（育成中）

## 現在地

- アフィリプ全停止中（アカウントパワー育成フェーズ）
- post cron JST 9/13/17/21 稼働中（engage70% / list30%）
- reply cron JST 11/15/19/23 稼働中（engage→conversation→insights）
- engage_agent: 自分のリプ者の投稿にリプ（上限10件/回）
- 画像投稿停止（imgur CDN shadowban）
- API使用量削減済み（3パターン生成・ask_short/ask_medium適用）

## 投稿スタイル（黄金パターン）

1. 知識暴露型：「[事実]って[数字/根拠]。[返信誘導]？😳」
2. 行動訂正型：「[NG行動]してる人まだいる？[正解]が正解。やってた？」
3. やり方暴露型：「[方法]って[意外な事実]知ってた？[返信誘導]🙌」
4. 保存型リスト：「[テーマ]【保存用】悩み→解決策×5〜8項目」
5. 姉シリーズ：皮膚科クリニック勤務の姉（32歳）の知見を引用

## 過去の失敗（二度と繰り返すな）

- SyntaxError本番流出 → 変更後 python3 -c "import orchestrator" 必須
- imgur画像 → shadowban。テキストのみ運用
- Threads API: since パラメータ → 400エラー。使うな
- Threads API: 他人のlike_count取得不可
- GitHub UI直接編集 → ファイル破損。Claude Code経由のみ
- git push --force / rm -rf 禁止
- APIキー・トークンをログ・ファイル・チャットに出すな

## Render Cron 追加

- daily_report: `0 16 * * *` UTC（= JST 1時）→ Slackに日次パフォーマンスレポート
  - フォロワー前日比 / 今日の投稿metrics / エンゲージリプ / 投稿型TOP3(7日)
  - 観察ポイント: 勝ち型把握、減衰すべき型の特定、投稿バランス調整指針
- ~~healthcheck cron~~ **廃案** — Slack日次レポート(daily_report)が代替として機能するため毎時heartbeat不要

## 重要な設定値

- Render cron (post): crn-d72ovqm3jp1c7386q0fg
- Render cron (reply): crn-d741a6q4d50c73bvbavg
- Render env group: evg-d75m22chg0os73arufsg
- THREADS_TOKEN_EXPIRES_AT: 2026-05-30
- Python 3.9（3.10+構文禁止）
- 作業ディレクトリ: ~/affiliate-bot

## 現在の進捗

### 完了済み

- post cron / reply cron 稼働確認済み
- engage_agent（自分のリプ者の投稿にリプ方式）導入済み
- API使用量削減（6→3パターン、ask_medium/ask_short導入）
- daily_report cron 設定済み（JST 1時 Slack通知）
- 姉シリーズ投稿テンプレート実装済み
- imgur画像停止・テキストのみ運用に切替済み
- **2026-04-22 Phase 1 完全成功**: writer.py JSON廃止・ask_plain導入・3 call逐次分割で Writer 7日間停止を解消
  - 復活初動 5分で 630 imp（過去最高ペース）・Writer失敗0件・engage 3 call全採用（61/88/30字）
  - 真因は Render auto-deploy 停滞（c0b6689 push が7日間反映されず）
  - 詳細: <https://github.com/siromaje713/bot-infrastructure-spec/blob/main/INCIDENTS/2026-04-22_render_deploy_stuck.md>
- 2026-04-22 bot-infrastructure-spec を public化（web_fetch 経由で新セッション初期読み込み可）
- CLAUDE.md から Render API Key 平文削除（700173a）
- **2026-04-22 深夜 RENDER_API_KEY rotation 実施**: 旧Key revoke・新Key 発行→両.envに反映
  - 詳細: <https://github.com/siromaje713/bot-infrastructure-spec/blob/main/INCIDENTS/2026-04-22_render_key_leak.md>

### 既知の問題・バグ

- エンゲージメント率が低い（view 300-500に対し、いいね 1-3）
- 表示回数1000安定に未到達
- **Render auto-deploy 停滞リスク**: 2026-04-22事例で7日間反映遅延。push後は `python3 scripts/_render_check.py` で active deploy commit と main HEAD を照合する運用
- **Threads permalink URL 404**: `https://www.threads.net/t/{post_id}` 形式は404実例あり（18061464617694785で確認）。正規形式 `/@{username}/post/{shortcode}` 想定だが post_id→shortcode 変換方法は未確定（orchestrator.py:570/598 の通知URL修正要）

## 次にやること

1. **現状確認**（最優先）: Slack daily_report で姉シリーズ生成・リプ者投稿リプ・API削減反映を検証
2. Threads permalink URL 正規形式調査（orchestrator.py:570/598 修正・post_id→shortcode or API permalink field）
3. `scripts/_render_*.py` 9ファイルを `scripts/render_ops/` へ整理（`_inject_render_key.py`, `_inject_anthropic_key.py`, `_render_check.py`, `_render_trigger_job.py`, `_render_poll_job.py`, `_render_fetch_stdout.py`, `_fetch_render_logs.py`, `_list_hoshi_keys.py`, `_repro_writer_local.py`）
4. benchmark_raw 収集（Step E/F/G: `scripts/collect_benchmark_raw.py` 実装 + gitignore 更新 + TOP20サンプル生成）
5. プロフィール改善（bio・アイコン・ハイライト見直し）
6. 投稿分析（伸びた/死んだパターン特定 → daily_reportデータ活用）
7. 論争型投稿の導入（化粧水不要説等）
8. 表示回数1000安定を目指す施策
9. THREADS_TOKEN更新準備（期限: 2026-05-30 — 残り約38日）

## 判断履歴

- ベンチマーク垢リプ廃止 → 自分のリプ者の投稿にリプ方式
- 姉設定: 皮膚科クリニック勤務（看護師/カウンセラー）確定
- 相互フォロー: 却下（コンテンツ質でリーチ決まる）
- API削減: 6→3パターン、ask_medium(512)/ask_short(256)導入

---

最終更新: 2026-04-22
