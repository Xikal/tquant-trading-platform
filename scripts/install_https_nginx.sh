#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${DOMAIN:-weisilianghua.cloud}"
APP_PORT="${APP_PORT:-18090}"
EMAIL="${EMAIL:-admin@${DOMAIN}}"
TEMPLATE_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/deploy/nginx/weisilianghua.conf.template"
TARGET_PATH="/etc/nginx/sites-available/weisilianghua.conf"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请使用 root 运行：sudo DOMAIN=$DOMAIN APP_PORT=$APP_PORT $0" >&2
  exit 1
fi

apt-get update
apt-get install -y nginx certbot python3-certbot-nginx gettext-base
mkdir -p /var/www/certbot

if [[ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]]; then
  certbot certonly --nginx --non-interactive --agree-tos -m "$EMAIL" -d "$DOMAIN" -d "www.$DOMAIN"
fi

DOMAIN="$DOMAIN" APP_PORT="$APP_PORT" envsubst '${DOMAIN} ${APP_PORT}' < "$TEMPLATE_PATH" > "$TARGET_PATH"
ln -sf "$TARGET_PATH" /etc/nginx/sites-enabled/weisilianghua.conf
nginx -t
systemctl reload nginx

echo "HTTPS 已配置：https://$DOMAIN -> 127.0.0.1:$APP_PORT"
