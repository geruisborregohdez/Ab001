#!/bin/bash
set -euo pipefail
APP_NAME="ab001"
REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)

# Install dependencies
dnf update -y
dnf install -y docker git

# Docker Compose plugin
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

systemctl enable --now docker

# Pull secrets from SSM Parameter Store
get_param() {
  aws ssm get-parameter --name "/${APP_NAME}/$1" --with-decryption \
    --region "${REGION}" --query "Parameter.Value" --output text
}

ANTHROPIC_API_KEY=$(get_param "ANTHROPIC_API_KEY")
DATABASE_URL=$(get_param "DATABASE_URL")
QB_MODE=$(get_param "QB_MODE")

# Clone repository
git clone https://github.com/YOUR_ORG/Ab001.git /opt/ab001
cd /opt/ab001

# Write .env
cat > .env <<EOF
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
DATABASE_URL=${DATABASE_URL}
QB_MODE=${QB_MODE}
EOF

mkdir -p data

# Start application
docker compose up -d --build

# Systemd service to restart on reboot
cat > /etc/systemd/system/ab001.service <<'UNIT'
[Unit]
Description=Ab001 Application
After=docker.service
Requires=docker.service

[Service]
WorkingDirectory=/opt/ab001
ExecStart=/usr/local/lib/docker/cli-plugins/docker-compose up
ExecStop=/usr/local/lib/docker/cli-plugins/docker-compose down
Restart=always

[Install]
WantedBy=multi-user.target
UNIT

systemctl enable ab001
