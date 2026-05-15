#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
#  TeacherPro — Server optimisation deployment script
#  Run once from the server:  bash /var/www/teacherpro/current/deploy/apply.sh
#
#  What this does:
#    1. Pull latest code
#    2. Stop old single-worker service
#    3. Install HTTP + WS gunicorn services
#    4. Apply PostgreSQL performance tuning
#    5. Apply Redis performance tuning
#    6. Add nginx rate-limit zones + replace site config
#    7. Start/enable everything
# ══════════════════════════════════════════════════════════════════════════
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="/var/www/teacherpro/current"
VENV="$APP_DIR/venv"

echo ""
echo "══════════════════════════════════════════"
echo " TeacherPro — applying server optimisations"
echo "══════════════════════════════════════════"
echo ""

# ── 1. Stop old service ────────────────────────────────────────────────────
echo "[1/7] Stopping old teacherpro service..."
systemctl stop teacherpro 2>/dev/null || true
systemctl disable teacherpro 2>/dev/null || true
echo "    ✓ Old service stopped"

# ── 2. Install new systemd services ───────────────────────────────────────
echo "[2/7] Installing new systemd services..."

cp "$DEPLOY_DIR/teacherpro-http.service" /etc/systemd/system/teacherpro-http.service
cp "$DEPLOY_DIR/teacherpro-ws.service"   /etc/systemd/system/teacherpro-ws.service

systemctl daemon-reload
systemctl enable teacherpro-http teacherpro-ws
echo "    ✓ Services installed and enabled"

# ── 3. PostgreSQL tuning ───────────────────────────────────────────────────
echo "[3/7] Applying PostgreSQL performance tuning..."

PG_CONF_DIR="/etc/postgresql/16/main/conf.d"
mkdir -p "$PG_CONF_DIR"
cp "$DEPLOY_DIR/postgresql-tuning.conf" "$PG_CONF_DIR/teacherpro.conf"
chown postgres:postgres "$PG_CONF_DIR/teacherpro.conf"
chmod 640 "$PG_CONF_DIR/teacherpro.conf"

echo "    Restarting PostgreSQL (this takes a few seconds)..."
systemctl restart postgresql
sleep 3
echo "    ✓ PostgreSQL restarted with tuned settings"

# ── 4. Redis tuning ────────────────────────────────────────────────────────
echo "[4/7] Applying Redis performance tuning..."

REDIS_CONF="/etc/redis/redis.conf"
# Only append if not already applied
if ! grep -q "# TeacherPro Redis tuning" "$REDIS_CONF" 2>/dev/null; then
    echo ""                                              >> "$REDIS_CONF"
    echo "# TeacherPro Redis tuning"                    >> "$REDIS_CONF"
    cat "$DEPLOY_DIR/redis-tuning.conf"                 >> "$REDIS_CONF"
    echo "    Applied Redis tuning to $REDIS_CONF"
else
    echo "    Redis tuning already applied — skipping"
fi

systemctl restart redis
echo "    ✓ Redis restarted with tuned settings"

# ── 5. nginx rate-limit zones ──────────────────────────────────────────────
echo "[5/7] Configuring nginx rate-limit zones..."

NGINX_CONF="/etc/nginx/nginx.conf"
# Insert rate-limit zones into http { } block if not already there
if ! grep -q "zone=general" "$NGINX_CONF" 2>/dev/null; then
    # Insert after the opening 'http {' line
    sed -i '/^http {/a\\n\t# TeacherPro rate limiting\n\tlimit_req_zone  $binary_remote_addr  zone=general:10m  rate=30r\/s;\n\tlimit_req_zone  $binary_remote_addr  zone=auth:10m     rate=5r\/m;\n\tlimit_conn_zone $binary_remote_addr  zone=connlimit:10m;' "$NGINX_CONF"
    echo "    Rate-limit zones added to $NGINX_CONF"
else
    echo "    Rate-limit zones already present — skipping"
fi

# ── 6. Install new nginx site config ──────────────────────────────────────
echo "[6/7] Installing new nginx site configuration..."

cp "$DEPLOY_DIR/nginx-teacherpro.conf" /etc/nginx/sites-available/teacherpro.uz
ln -sf /etc/nginx/sites-available/teacherpro.uz /etc/nginx/sites-enabled/teacherpro.uz

echo "    Testing nginx config..."
nginx -t
echo "    Reloading nginx..."
systemctl reload nginx
echo "    ✓ nginx reloaded"

# ── 7. Start new application services ─────────────────────────────────────
echo "[7/7] Starting TeacherPro HTTP + WS services..."

systemctl start teacherpro-http
systemctl start teacherpro-ws
sleep 2

# Verify both are running
HTTP_STATUS=$(systemctl is-active teacherpro-http)
WS_STATUS=$(systemctl is-active teacherpro-ws)

echo ""
echo "══════════════════════════════════════════"
echo " Deployment complete!"
echo "══════════════════════════════════════════"
echo "  teacherpro-http : $HTTP_STATUS"
echo "  teacherpro-ws   : $WS_STATUS"
echo "  PostgreSQL       : $(systemctl is-active postgresql)"
echo "  Redis            : $(systemctl is-active redis)"
echo "  nginx            : $(systemctl is-active nginx)"
echo ""
echo " Verify live:  curl -sk https://teacherpro.uz/health"
echo " HTTP logs:    journalctl -u teacherpro-http -f"
echo " WS logs:      journalctl -u teacherpro-ws -f"
echo "══════════════════════════════════════════"
