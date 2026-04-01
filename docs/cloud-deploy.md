# 云服务器一键部署指南

从零开始，在云服务器上部署林妹妹 Agent。全程约 15 分钟。

## 前置条件

| 项目 | 要求 |
|------|------|
| Claude 订阅 | Claude Max 或 Pro（用于 OAuth 登录） |
| Tavily API Key | 免费申请：https://tavily.com |
| Brave API Key | 免费申请：https://brave.com/search/api |
| 微信 | 需 iOS 最新版（支持 ClawBot / iLink） |

## 第一步：购买云服务器

推荐配置：

| 项目 | 推荐 |
|------|------|
| 云服务商 | 腾讯云 / 阿里云 |
| 机型 | 轻量应用服务器 |
| 配置 | 2核4G（最低2核2G） |
| 系统 | Ubuntu 22.04 |
| 带宽 | 5Mbps |
| 月费 | 约 40-80 元 |

购买链接：
- 腾讯云：https://cloud.tencent.com/act/pro/lighthouse
- 阿里云：https://www.aliyun.com/product/swas

选择 **Ubuntu 22.04** 系统镜像。

## 第二步：SSH 连接到服务器

```bash
ssh root@你的服务器IP
```

如果是首次连接，输入 `yes` 确认指纹。

## 第三步：一键部署

复制以下命令，粘贴到服务器终端，回车执行：

```bash
git clone https://github.com/jinny280401-glitch/Linmeimei-Agent.git
cd Linmeimei-Agent
chmod +x deploy.sh
./deploy.sh
```

脚本会自动安装以下内容：
- Node.js v24
- Python 3 + akshare/httpx
- Claude Code CLI
- cc-connect (beta)
- 林妹妹 workspace + 技能包
- systemd 守护服务

等待脚本执行完毕（约 3-5 分钟）。

## 第四步：填入 API 密钥

```bash
nano ~/.env
```

将以下两行改为你自己的密钥：

```
TAVILY_API_KEY=你的Tavily密钥
BRAVE_API_KEY=你的Brave密钥
```

按 `Ctrl+O` 保存，`Ctrl+X` 退出。

## 第五步：Claude OAuth 登录

```bash
claude
```

终端会显示一个链接，复制到浏览器打开，用你的 Claude 账号完成 OAuth 授权。

注意：
- 只需要你自己的 Claude 账号，微信用户不需要
- 登录一次即可，Token 会自动保存
- 登录成功后输入 `/exit` 退出 Claude

## 第六步：微信扫码绑定

```bash
cc-connect weixin setup --project lin-meimei
```

终端会显示二维码，用手机微信扫码确认授权。

扫码成功后，Token 自动写入配置文件。

## 第七步：启动服务

```bash
sudo systemctl start lin-meimei
```

验证服务是否正常运行：

```bash
sudo systemctl status lin-meimei
```

看到 `active (running)` 就说明成功了。

## 第八步：测试

用另一个微信号给绑定的微信发一条消息，比如"你好"。

林妹妹应该会回复自我介绍并询问性别。

## 完成

部署完成。你的 Mac 电脑可以关机了，服务器会 7x24 运行。

## 管理命令

```bash
# 查看状态
sudo systemctl status lin-meimei

# 查看实时日志
sudo journalctl -u lin-meimei -f

# 重启服务
sudo systemctl restart lin-meimei

# 停止服务
sudo systemctl stop lin-meimei
```

## 常见问题

### 微信发消息没回复？

1. 检查服务状态：`sudo systemctl status lin-meimei`
2. 查看日志：`sudo journalctl -u lin-meimei -f`
3. Token 过期重新扫码：`cc-connect weixin setup --project lin-meimei`

### 微信 Token 过期了？

```bash
sudo systemctl stop lin-meimei
cc-connect weixin setup --project lin-meimei
sudo systemctl start lin-meimei
```

### 怎么让更多人用？

默认配置 `allow_from = "*"` 允许所有人。生产环境建议改为指定用户：

```bash
nano ~/.cc-connect/config.toml
# 将 allow_from 改为具体的用户ID，逗号分隔
```

### 怎么更新林妹妹？

```bash
cd ~/Linmeimei-Agent
git pull
./install.sh
sudo systemctl restart lin-meimei
```

### 服务器需要一直开着吗？

是的。关机后微信消息无法响应。建议设置自动续费，避免服务器到期中断。

### Claude 账号需要几个？

只需要一个（你自己的）。所有微信用户共用这一个 Claude 后端，通过 sender_id 区分身份和记忆。
