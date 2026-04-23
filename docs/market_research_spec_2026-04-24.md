# Threads 美容アカウント市場リサーチ仕様書

作成日: 2026-04-24
目的: @riko_cosme_lab のプロフィール全面再構築・属性ペルソナ再設計のための競合データ収集

## 調査対象

日本語美容系 Threads アカウント（個人・美容愛好家・美容クリエイター・属性特化型美容クリエイター）

## 収集件数目標

- 合計: 60-75 アカウント
- 各アカウント直近 20 投稿

## キーワード群（4層）

### 基本層（美容ジャンル全般）

- スキンケア
- 美容
- コスメ
- 垢抜け

### 悩み層（悩み特化で集客してる個人）

- 毛穴
- 敏感肌
- くすみ
- ニキビ

### ターゲット層（年代・属性ターゲティング）

- 30代美容
- アラサー美容
- OL 美容
- 美容オタク

### 属性掛け算層（ここが最重要）

- 元ナース 美容
- 元キャバ嬢 美容
- 元ホステス 美容
- 元エステティシャン 美容
- 整形 美容
- 美容部員 美容

## 除外基準（該当したら収集対象から外す）

- ブランド公式アカウント（資生堂・SK-II・花王 等）
- 大手 EC・メディア公式（@cosme・LIPS・美的 等）
- 美容皮膚科・クリニック公式
- 男性向け美容専門
- 現役の施術者本人による集客（現役美容師・現役ネイリスト・現役エステティシャン等・「元◯◯」は含める）
- フォロワー 1,000 未満
- 直近 30 日以内に投稿がない
- 非公開・削除済み

## 収集データ JSON スキーマ

各アカウントごとに以下を収集：

```json
{
  "username": "string（@抜き）",
  "display_name": "string",
  "profile_url": "https://www.threads.com/@username",
  "bio": "string（全文）",
  "followers": "number（K/M 展開した推定値）",
  "followers_raw": "string（元表記 例: '12.3K'）",
  "following": "number",
  "posts_count": "number",
  "avatar_url": "string",
  "is_verified": "boolean",
  "has_pinned_post": "boolean",
  "pinned_post_text": "string or null",
  "pinned_post_likes": "number or null",
  "discovery_keyword": "string（どのキーワードで発掘したか）",
  "category_guess": "string（skincare / makeup / device / lifestyle / mixed のいずれか Cowork が推定）",
  "attribute_tags": [
    "bio から Cowork が推定する属性掛け算タグ。例: '元ナース', '元キャバ嬢', '敏感肌', 'アラサー', 'シンママ', '整形経験あり', '皮膚科医' 等。該当がなければ空配列。複数該当可。"
  ],
  "authority_claim": "string or null（bio で主張されてる権威・経歴。例: '美容部員10年', '看護師歴8年', '元No.1キャバ嬢'。なければ null）",
  "persona_hook": "string or null（bio の差別化メッセージを Cowork が 1 行要約。例: '敏感肌OLの時短ケア', '元ホステスの男ウケ美容'）",
  "recent_posts": [
    {
      "post_url": "string",
      "text": "string（全文）",
      "char_count": "number",
      "line_count": "number",
      "emoji_count": "number",
      "has_image": "boolean",
      "has_video": "boolean",
      "likes": "number",
      "likes_raw": "string",
      "replies": "number",
      "reposts": "number",
      "posted_at": "ISO8601 or relative（'2日前'等）",
      "posted_at_raw": "string（UI 表記そのまま）"
    }
  ]
}
```

## バッチ分割

### バッチ 1（基本層・15-20 アカウント）

キーワード: スキンケア / 美容 / コスメ / 垢抜け
出力: logs/market_research/2026-04-24_batch1.json

### バッチ 2（悩み層 + ターゲット層・20-25 アカウント）

キーワード: 毛穴 / 敏感肌 / くすみ / ニキビ / 30代美容 / アラサー美容 / OL 美容 / 美容オタク
出力: logs/market_research/2026-04-24_batch2.json

### バッチ 3（属性掛け算層・20-30 アカウント）★最重要

キーワード: 元ナース 美容 / 元キャバ嬢 美容 / 元ホステス 美容 / 元エステティシャン 美容 / 整形 美容 / 美容部員 美容
このバッチは属性ペルソナ設計の核になるので、件数確保を優先。
出力: logs/market_research/2026-04-24_batch3.json

### 最終統合

logs/market_research/2026-04-24_accounts_raw.json
（全バッチのマージ版・重複除去済み）

## 進捗管理

logs/market_research/2026-04-24_progress.md に以下を記録：

- 各バッチ開始時刻・完了時刻
- 各バッチ収集件数
- スキップしたアカウントと理由
- エラー発生時の詳細
- 最終 HEAD SHA

## エラー処理

- Threads アクセス失敗・レート制限: 30 秒待機 → 3 回リトライ → スキップ（理由を progress.md に）
- フォロワー数が K/M 表記のみ: 推定値と元表記両方保存
- 非公開・削除済みアカウント: スキップ
- ログインセッション切れ検出: 即停止・progress.md に "SESSION_EXPIRED" 記録・人間判断待ち

## 絶対禁止

- 書き込みアクション一切禁止（投稿・いいね・フォロー・リポスト・DM）
- API キー・トークン・パスワードを収集データに含めない
- プライベート DM・非公開コンテンツへのアクセス禁止
- 仕様書に記載のない追加作業禁止
- riko_cosme_lab 本体のログインセッション使用絶対禁止

## 完了基準

- batch1.json / batch2.json / batch3.json / accounts_raw.json の 4 ファイルが存在
- accounts_raw.json の accounts 配列が 60 件以上
- バッチ 3（属性掛け算層）が 20 件以上含まれる ★必須
- 各アカウントに recent_posts が 20 件（または取得可能な全件）含まれる
- 各アカウントに attribute_tags / authority_claim / persona_hook が埋まってる（該当なしなら空値でよい）
- progress.md に全バッチ完了記録
- git log に 4 commit 以上
- grep で token/key/password の値が混入してないこと確認済み
