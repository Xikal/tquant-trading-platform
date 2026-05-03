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

CERT_NAME="$DOMAIN"
if [[ ! -f "/etc/letsencrypt/live/$CERT_NAME/fullchain.pem" && -f "/etc/letsencrypt/live/www.$DOMAIN/fullchain.pem" ]]; then
  CERT_NAME="www.$DOMAIN"
fi

if [[ ! -f "/etc/letsencrypt/live/$CERT_NAME/fullchain.pem" ]]; then
  certbot certonly --nginx --non-interactive --agree-tos -m "$EMAIL" -d "$DOMAIN" -d "www.$DOMAIN"
  CERT_NAME="$DOMAIN"
  if [[ ! -f "/etc/letsencrypt/live/$CERT_NAME/fullchain.pem" && -f "/etc/letsencrypt/live/www.$DOMAIN/fullchain.pem" ]]; then
    CERT_NAME="www.$DOMAIN"
  fi
fi
if [[ ! -f "/etc/letsencrypt/live/$CERT_NAME/fullchain.pem" ]]; then
  echo "证书文件不存在：/etc/letsencrypt/live/$CERT_NAME/fullchain.pem" >&2
  exit 1
fi

DOMAIN="$DOMAIN" CERT_NAME="$CERT_NAME" APP_PORT="$APP_PORT" envsubst '${DOMAIN} ${CERT_NAME} ${APP_PORT}' < "$TEMPLATE_PATH" > "$TARGET_PATH"
ln -sf "$TARGET_PATH" /etc/nginx/sites-enabled/weisilianghua.conf
rm -f /etc/nginx/sites-enabled/weisilianghua.cloud
nginx -t
systemctl reload nginx

echo "HTTPS 已配置：https://$DOMAIN -> 127.0.0.1:$APP_PORT，证书目录：$CERT_NAME"
