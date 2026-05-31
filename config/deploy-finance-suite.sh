#!/bin/bash
# ============================================================
# finance-suite 服务器部署脚本
# 功能：
#   1. 补 /api/health 路由到 FastAPI
#   2. 下发完整 nginx 三域名配置
#   3. 扩展 SSL 证书覆盖 www / api 子域
#   4. 重载 nginx
# 用法：bash deploy-finance-suite.sh
# ============================================================
set -e

PROJECT_DIR="/home/ubuntu/finance-suite-web"
NGINX_CONF="/etc/nginx/sites-available/finance-suite"
NGINX_ENABLED="/etc/nginx/sites-enabled/finance-suite"

echo "[1/4] 补 /api/health 路由..."

MAIN_PY="$PROJECT_DIR/app/main.py"

# 检查是否已存在
if grep -q "/api/health" "$MAIN_PY"; then
  echo "  已存在，跳过"
else
  # 在最后一个 @app. 路由或 include_router 之后插入
  # 用 Python 直接追加到文件末尾（在 if __name__ 之前）
  python3 - <<'PYEOF'
import re

path = "/home/ubuntu/finance-suite-web/app/main.py"
with open(path, "r") as f:
    src = f.read()

health_route = '''
@app.get("/api/health")
async def health():
    return {"status": "ok"}
'''

# 插在 if __name__ == "__main__": 之前，或直接追加
if 'if __name__ == "__main__":' in src:
    src = src.replace(
        'if __name__ == "__main__":',
        health_route + '\nif __name__ == "__main__":'
    )
else:
    src += health_route

with open(path, "w") as f:
    f.write(src)

print("  /api/health 路由已注入")
PYEOF
fi

echo "[2/4] 下发 nginx 配置..."

sudo tee "$NGINX_CONF" > /dev/null << 'NGINXEOF'
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

upstream backend {
    server 127.0.0.1:8000;
    keepalive 64;
}

# ─── HTTP → HTTPS ─────────────────────────────────────────────────────────────
server {
    listen 80;
    listen [::]:80;
    server_name touziagent.com www.touziagent.com api.touziagent.com;
    return 301 https://$host$request_uri;
}

# ─── touziagent.com → www（主站只做跳转）─────────────────────────────────────
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name touziagent.com;

    ssl_certificate     /etc/letsencrypt/live/touziagent.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/touziagent.com/privkey.pem;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;
    ssl_protocols       TLSv1.2 TLSv1.3;

    return 301 https://www.touziagent.com$request_uri;
}

# ─── www.touziagent.com（前端 CDN 加速源站）──────────────────────────────────
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name www.touziagent.com;

    ssl_certificate     /etc/letsencrypt/live/touziagent.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/touziagent.com/privkey.pem;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;
    ssl_protocols       TLSv1.2 TLSv1.3;

    client_max_body_size 20m;

    location /static/ {
        alias /home/ubuntu/finance-suite-web/static/;
        expires 7d;
        add_header Cache-Control "public, max-age=604800, immutable";
        add_header Vary "Accept-Encoding";
        access_log off;
        gzip_static on;
    }

    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        add_header Cache-Control "no-store" always;

        proxy_pass         http://backend;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_set_header   Upgrade           $http_upgrade;
        proxy_set_header   Connection        $connection_upgrade;
        proxy_read_timeout 120s;
    }

    location / {
        add_header Cache-Control "no-cache" always;

        proxy_pass         http://backend;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}

# ─── api.touziagent.com（API 直连，绕过 CDN）─────────────────────────────────
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name api.touziagent.com;

    ssl_certificate     /etc/letsencrypt/live/touziagent.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/touziagent.com/privkey.pem;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;
    ssl_protocols       TLSv1.2 TLSv1.3;

    client_max_body_size 20m;

    add_header Access-Control-Allow-Origin      "https://www.touziagent.com" always;
    add_header Access-Control-Allow-Methods     "GET, POST, OPTIONS" always;
    add_header Access-Control-Allow-Headers     "Content-Type, Authorization" always;
    add_header Access-Control-Allow-Credentials "true" always;

    location / {
        if ($request_method = OPTIONS) {
            return 204;
        }

        limit_req zone=api_limit burst=20 nodelay;
        add_header Cache-Control "no-store" always;

        proxy_pass         http://backend;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_set_header   Upgrade           $http_upgrade;
        proxy_set_header   Connection        $connection_upgrade;
        proxy_read_timeout 120s;
    }
}
NGINXEOF

# 确保 sites-enabled 软链存在
if [ ! -L "$NGINX_ENABLED" ]; then
  sudo ln -s "$NGINX_CONF" "$NGINX_ENABLED"
  echo "  已创建 sites-enabled 软链"
fi

echo "[3/4] 扩展 SSL 证书（覆盖 www / api 子域）..."

# 检查证书是否已包含 www 和 api
CERT_DOMAINS=$(sudo certbot certificates 2>/dev/null | grep "Domains:" | head -1)
if echo "$CERT_DOMAINS" | grep -q "www.touziagent.com" && echo "$CERT_DOMAINS" | grep -q "api.touziagent.com"; then
  echo "  证书已覆盖所有域名，跳过"
else
  sudo certbot certonly --nginx --expand \
    -d touziagent.com \
    -d www.touziagent.com \
    -d api.touziagent.com \
    --non-interactive --agree-tos \
    --email admin@touziagent.com
fi

echo "[4/4] 验证并重载 nginx..."
sudo nginx -t
sudo systemctl reload nginx

echo ""
echo "============================================"
echo "  部署完成，验证："
echo "============================================"
echo ""
echo "  # 健康检查"
echo "  curl -s https://api.touziagent.com/api/health"
echo ""
echo "  # 注册接口"
echo "  curl -si -X POST https://api.touziagent.com/api/register \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"username\":\"test\",\"email\":\"t@t.com\",\"password\":\"test123456\"}'"
echo ""
echo "  # 静态资源"
echo "  curl -sI https://www.touziagent.com/static/css/style.css"
echo ""
echo "  # 主站跳转"
echo "  curl -sI https://touziagent.com/"
echo ""
