# GitHub Secrets 設定ガイド

追加先: https://github.com/siromaje713/affiliate-bot/settings/secrets/actions

## 必須 Secrets

| Secret名               | 説明                       | 取得方法                       |
| ---------------------- | -------------------------- | ------------------------------ |
| `ANTHROPIC_API_KEY`    | Claude API キー            | https://console.anthropic.com/ |
| `THREADS_ACCESS_TOKEN` | Threads アクセストークン   | Meta Developer → Threads API   |
| `THREADS_USER_ID`      | Threads ユーザーID         | Meta Developer → Threads API   |
| `SLACK_WEBHOOK_URL`    | Slack Incoming Webhook URL | Slack App → Incoming Webhooks  |

## 設定手順

1. GitHub リポジトリ → Settings → Secrets and variables → Actions
2. "New repository secret" をクリック
3. 上記テーブルの Secret名と値を入力
4. "Add secret" で保存

## 確認

設定後、.github/workflows/ のワークフローが動作します：

- `weekly_research.yml`: 毎週日曜 JST 05:00 にバズリサーチ
- `weekly_insights.yml`: 毎日 JST 02:00 にインサイト分析
