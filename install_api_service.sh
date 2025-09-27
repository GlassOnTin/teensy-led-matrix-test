#!/bin/bash
# Install LED Matrix API Service

set -e

SERVICE_NAME="led-matrix-api"
SERVICE_FILE="led-matrix-api.service"
PROJECT_DIR="$(pwd)"
USER="$(whoami)"

echo "🔧 Installing LED Matrix API Service..."

# Check if running as regular user
if [ "$USER" = "root" ]; then
    echo "❌ Error: Do not run this script as root. Run as regular user with sudo access."
    exit 1
fi

# Check if service file exists
if [ ! -f "$SERVICE_FILE" ]; then
    echo "❌ Error: Service file '$SERVICE_FILE' not found in current directory"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Error: Virtual environment 'venv' not found. Run './setup.sh' first."
    exit 1
fi

# Create a dynamic service file with current user and paths
echo "📝 Creating service file with current user ($USER) and project path ($PROJECT_DIR)..."

cat > "/tmp/${SERVICE_NAME}.service" << EOF
[Unit]
Description=LED Matrix API Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${USER}
Group=${USER}
WorkingDirectory=${PROJECT_DIR}
Environment=PATH=${PROJECT_DIR}/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=${PROJECT_DIR}/venv/bin/python ${PROJECT_DIR}/python_utils/api_server.py --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${PROJECT_DIR}
ReadWritePaths=/tmp
ReadWritePaths=/dev

# Device access for serial communication
SupplementaryGroups=dialout

[Install]
WantedBy=multi-user.target
EOF

# Install the service
echo "🔐 Installing service (requires sudo)..."
sudo cp "/tmp/${SERVICE_NAME}.service" "/etc/systemd/system/"
sudo systemctl daemon-reload

# Check if user is in dialout group
if ! groups "$USER" | grep -q dialout; then
    echo "⚠️  Warning: User '$USER' is not in dialout group."
    echo "   Adding user to dialout group (requires sudo)..."
    sudo usermod -a -G dialout "$USER"
    echo "   ⚠️  You may need to log out and back in for group changes to take effect."
fi

echo "✅ Service installed successfully!"
echo ""
echo "📋 Service Management Commands:"
echo "   Start service:    sudo systemctl start $SERVICE_NAME"
echo "   Stop service:     sudo systemctl stop $SERVICE_NAME"
echo "   Enable at boot:   sudo systemctl enable $SERVICE_NAME"
echo "   Check status:     sudo systemctl status $SERVICE_NAME"
echo "   View logs:        sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "🌐 Once started, API will be available at:"
echo "   http://localhost:8080/docs    (API documentation)"
echo "   http://localhost:8080/web/    (Web interface)"
echo ""
echo "To start the service now:"
echo "   sudo systemctl start $SERVICE_NAME"