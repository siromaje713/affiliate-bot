# n8nワークフロールール
- ワークフローはJSONでエクスポートして .claude/workflows/ に保存する
- 本番稼働前に必ずTest実行で確認する
- 起動：N8N_SECURE_COOKIE=false npx n8n
- URL：http://localhost:5678
- Renderデプロイ時はN8N_SECURE_COOKIE=trueに戻す
