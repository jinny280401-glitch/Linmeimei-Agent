# 云服务器部署教程

## 推荐配置

| 项目 | 推荐 |
|------|------|
| 云服务商 | 腾讯云 / 阿里云 |
| 机型 | 轻量应用服务器 |
| 配置 | 2核4G（最低2核2G） |
| 系统 | Ubuntu 22.04 |
| 带宽 | 5Mbps |
| 月费 | 约 40-80 元 |

## 部署步骤

### 1. 购买服务器

- 腾讯云：https://cloud.tencent.com/act/pro/lighthouse
- 阿里云：https://www.aliyun.com/product/swas

选择 Ubuntu 22.04 系统镜像。

### 2. SSH 连接

```bash
ssh root@你的服务器IP
```

### 3. 一键部署

```bash
git clone https://github.com/jinny280401-glitch/lin-meimei-agent.git
cd lin-meimei-agent
cp .env.example ~/.env
nano ~/.env    # 填入 API 密钥
chmod +x deploy.sh
./deploy.sh
```

### 4. Claude Code 登录

```bash
claude
# 按提示完成 OAuth 登录
```

### 5. 微信扫码

```bash
cc-connect weixin setup --project lin-meimei
# 用手机微信扫码
```

### 6. 启动服务

```bash
sudo systemctl start lin-meimei
```

## 管理命令

```bash
# 查看状态
sudo systemctl status lin-meimei

# 查看日志
journalctl -u lin-meimei -f

# 重启
sudo systemctl restart lin-meimei

# 停止
sudo systemctl stop lin-meimei
```

## 注意事项

- 服务器不要休眠，否则微信消息无法响应
- 建议设置自动续费，避免服务器到期中断
- 定期检查日志确认服务正常运行
- 微信 Token 可能过期，过期后重新 `cc-connect weixin setup`
