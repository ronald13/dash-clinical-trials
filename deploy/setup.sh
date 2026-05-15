#!/bin/bash
# EC2 setup script — Ubuntu 22.04 LTS, Docker deployment
# Run once on a fresh instance: bash setup.sh
# Prerequisites: EC2 must have an IAM role with s3:GetObject / s3:ListBucket on the data bucket.

set -e

APP_DIR="/opt/dash-clinical-trials"
REPO="https://github.com/ronald13/dash-clinical-trials.git"

echo "=== 1. Install Docker (if not present) ==="
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker ubuntu
    echo "Docker installed. Log out and back in if running manually."
fi

if ! command -v docker-compose &>/dev/null && ! docker compose version &>/dev/null 2>&1; then
    sudo apt-get install -y docker-compose-plugin
fi

echo "=== 2. Clone / update repo ==="
if [ -d "$APP_DIR/.git" ]; then
    cd "$APP_DIR" && sudo git pull
else
    sudo git clone "$REPO" "$APP_DIR"
fi
sudo chown -R ubuntu:ubuntu "$APP_DIR"

echo "=== 3. Build and start ==="
cd "$APP_DIR"
docker compose pull 2>/dev/null || true
docker compose up -d --build

echo ""
echo "=== Done ==="
echo "Logs:   docker compose -f $APP_DIR/docker-compose.yml logs -f"
echo "Status: docker compose -f $APP_DIR/docker-compose.yml ps"
echo "App:    http://$(curl -s ifconfig.me):8050"
