# 常见问题

### 微信发消息没回复？

1. 检查 cc-connect 是否在运行：`sudo systemctl status lin-meimei`
2. 查看日志：`journalctl -u lin-meimei -f`
3. 微信 Token 可能过期，重新扫码：`cc-connect weixin setup --project lin-meimei`

### 其他人怎么用我的林妹妹？

他们不需要扫码。把你的微信名片发给他们，他们加你好友后直接发消息，cc-connect 会自动用林妹妹回复。每个用户的记忆按 sender_id 自动隔离。

### 多个用户的记忆会串吗？

不会。每个用户有独立的记忆文件（`memory/customers/{user_id}.md`），严格隔离。

### 需要 Anthropic API Key 吗？

不需要。本项目使用 Claude Code 订阅版（Claude Max/Pro），通过 OAuth 认证，不需要 API Key。

### 支持哪些平台？

通过 cc-connect 支持：个人微信、企业微信、飞书、钉钉、Telegram、Slack、Discord、QQ 等10个平台。

### 金融数据从哪来？

主要通过 AkShare（东方财富）获取A股实时数据，搜索引擎用 Tavily + Brave 双引擎。

### 服务器要一直开着吗？

是的。关机或休眠后微信消息无法响应。建议用云服务器 7x24 运行。

### 怎么自定义人设？

修改 `workspace/SOUL.md`（性格）和 `workspace/CLAUDE.md`（Claude Code 指令），重启 cc-connect 即可。
