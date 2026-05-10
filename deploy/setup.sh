#!/bin/bash
# EC2 setup script — Ubuntu 22.04 LTS
# Run once on a fresh instance: bash setup.sh
# Prerequisites: EC2 must have an IAM role with s3:GetObject / s3:ListBucket on the data bucket.

set -e

APP_DIR="/opt/dash-clinical-trials"
REPO="https://github.com/ronald13/dash-clinical-trials.git"
SERVICE="clinical-trials"
APP_USER="ubuntu"

echo "=== 1. System packages ==="
sudo apt-get update -y
sudo apt-get install -y python3.11 python3.11-venv python3-pip git

echo "=== 2. Clone repo ==="
sudo git clone "$REPO" "$APP_DIR" 2>/dev/null || (cd "$APP_DIR" && sudo git pull)
sudo chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

echo "=== 3. Python venv + dependencies ==="
cd "$APP_DIR"
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "=== 4. Install systemd service ==="
sudo cp "$APP_DIR/deploy/clinical-trials.service" "/etc/systemd/system/$SERVICE.service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE"
sudo systemctl restart "$SERVICE"

echo ""
echo "=== Done ==="
echo "Status: sudo systemctl status $SERVICE"
echo "Logs:   sudo journalctl -u $SERVICE -f"
echo "App:    http://$(curl -s ifconfig.me):8050"
