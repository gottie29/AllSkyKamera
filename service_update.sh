#!/usr/bin/env bash
# Normalize possible CRLF line endings on first run
if command -v dos2unix >/dev/null 2>&1; then
    dos2unix "$0" >/dev/null 2>&1 || true
else
    sed -i 's/\r$//' "$0" || true
fi

set -euo pipefail
export LANG=C.UTF-8
export LC_ALL=C.UTF-8

# --------------------------------------------------------------------
# 0. Basic checks
# --------------------------------------------------------------------
if [ ! -d "askutils" ]; then
    echo "This script must be executed in the project root (with askutils/)."
    exit 1
fi

PROJECT_ROOT="$(pwd)"
SETUPUI_DIR="${PROJECT_ROOT}/setupui"
SETUPUI_APP="${SETUPUI_DIR}/app.py"
INSTALL_USER="$(id -un)"
SYSTEMCTL_BIN="$(command -v systemctl || echo /bin/systemctl)"
SETUPUI_SERVICE_NAME="allsky-setupui.service"
SERVICE_FILE="/etc/systemd/system/${SETUPUI_SERVICE_NAME}"
SUDOERS_FILE="/etc/sudoers.d/allsky-setupui"

echo "Project root: ${PROJECT_ROOT}"
echo "SetupUI dir : ${SETUPUI_DIR}"
echo "Install user: ${INSTALL_USER}"
echo "systemctl   : ${SYSTEMCTL_BIN}"

if [ ! -d "${SETUPUI_DIR}" ]; then
    echo "SetupUI directory not found: ${SETUPUI_DIR}"
    exit 1
fi

if [ ! -f "${SETUPUI_APP}" ]; then
    echo "SetupUI app.py not found: ${SETUPUI_APP}"
    exit 1
fi

# --------------------------------------------------------------------
# 1. Check Flask
# --------------------------------------------------------------------
# --------------------------------------------------------------------
# 1. Check/install Python dependencies for SetupUI
# --------------------------------------------------------------------
echo
echo "=== 1. Checking SetupUI Python dependencies ==="

MISSING_DEPS=0

if ! python3 -c "import flask" >/dev/null 2>&1; then
    echo "> Missing Python module: flask"
    MISSING_DEPS=1
fi

if ! python3 -c "import werkzeug" >/dev/null 2>&1; then
    echo "> Missing Python module: werkzeug"
    MISSING_DEPS=1
fi

if [ "${MISSING_DEPS}" -eq 1 ]; then
    echo "> Installing required Python packages for SetupUI..."
    python3 -m pip install --user --upgrade pip --break-system-packages
    python3 -m pip install --user flask werkzeug --break-system-packages
    echo "> SetupUI dependencies installed."
else
    echo "> All required SetupUI Python modules are already available."
fi

# --------------------------------------------------------------------
# 2. Install/Update systemd service
# --------------------------------------------------------------------
echo
echo "=== 2. Installing SetupUI service ==="

sudo tee "${SERVICE_FILE}" >/dev/null <<EOF
[Unit]
Description=AllSky Setup UI
After=network.target

[Service]
Type=simple
User=${INSTALL_USER}
WorkingDirectory=${SETUPUI_DIR}
ExecStart=/usr/bin/python3 ${SETUPUI_APP}
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

echo "> Service file written: ${SERVICE_FILE}"

# --------------------------------------------------------------------
# 3. Install sudoers rule
# --------------------------------------------------------------------
echo
echo "=== 3. Installing sudoers rule ==="

sudo tee "${SUDOERS_FILE}" >/dev/null <<EOF
${INSTALL_USER} ALL=(ALL) NOPASSWD: ${SYSTEMCTL_BIN} restart ${SETUPUI_SERVICE_NAME}
${INSTALL_USER} ALL=(ALL) NOPASSWD: ${SYSTEMCTL_BIN} status ${SETUPUI_SERVICE_NAME}
${INSTALL_USER} ALL=(ALL) NOPASSWD: ${SYSTEMCTL_BIN} stop ${SETUPUI_SERVICE_NAME}
${INSTALL_USER} ALL=(ALL) NOPASSWD: ${SYSTEMCTL_BIN} start ${SETUPUI_SERVICE_NAME}
EOF

sudo chmod 440 "${SUDOERS_FILE}"
echo "> Sudoers file written: ${SUDOERS_FILE}"

# --------------------------------------------------------------------
# 4. Enable and start service
# --------------------------------------------------------------------
echo
echo "=== 4. Enabling and starting service ==="
sudo "${SYSTEMCTL_BIN}" daemon-reload
sudo "${SYSTEMCTL_BIN}" enable "${SETUPUI_SERVICE_NAME}"
sudo "${SYSTEMCTL_BIN}" restart "${SETUPUI_SERVICE_NAME}"

echo
echo "=== 5. Service status ==="
sudo "${SYSTEMCTL_BIN}" --no-pager --full status "${SETUPUI_SERVICE_NAME}" || true

# --------------------------------------------------------------------
# 6. Show IP addresses
# --------------------------------------------------------------------
echo
echo "=== 6. SetupUI access ==="

LAN_IPV4S="$(ip -4 -o addr show scope global 2>/dev/null | awk '$2 !~ /^zt/ {print $4}' | cut -d/ -f1 | xargs || true)"
LAN_IPV6S="$(ip -6 -o addr show scope global 2>/dev/null | awk '$2 !~ /^zt/ {print $4}' | cut -d/ -f1 | xargs || true)"

if [ -n "${LAN_IPV4S}" ]; then
    echo "Local network:"
    for ip in ${LAN_IPV4S}; do
        echo "  http://${ip}:5001"
    done
else
    echo "Local network: not detected"
fi

if [ -n "${LAN_IPV6S}" ]; then
    echo
    echo "IPv6 (optional):"
    for ip in ${LAN_IPV6S}; do
        echo "  http://[${ip}]:5001"
    done
fi

echo
echo "Tip:"
echo "  Open one of the addresses above in your browser."
echo
echo "Done."