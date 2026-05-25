#!/usr/bin/env bash
set -euo pipefail

echo "=== Telescope Handcontroller Replacement - Setup ==="

# Check we're on a Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "Warning: Not running on a Raspberry Pi (no /proc/device-tree/model)"
else
    echo "Running on: $(tr -d '\0' < /proc/device-tree/model)"
fi

# 1. System packages
echo ""
echo "==> Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    build-essential cmake git \
    python3-dev python3-pip python3-setuptools python3-pyqt5 \
    libindi-dev libindi-plugins \
    indi-eqmod \
    indi-asi \
    swig \
    libcfitsio-dev libnova-dev \
    libusb-1.0-0-dev \
    libgsl-dev libfftw3-dev \
    libraw-dev libjpeg-dev \
    libcurl4-gnutls-dev \
    libtheora-dev

# 2. Install INDI 3rd-party drivers (EQMOD, ASI)
echo ""
echo "==> Building/Installing INDI 3rd-party drivers..."
if ! command -v indi_eqmod_telescope &>/dev/null; then
    cd /tmp
    git clone --depth 1 https://github.com/indilib/indi-3rdparty.git
    cd indi-3rdparty
    mkdir -p build && cd build
    cmake -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_BUILD_TYPE=Release ..
    make -j$(nproc) || echo "Some drivers may not build on this platform"
    sudo make install || true
    cd /tmp
    rm -rf indi-3rdparty
else
    echo "INDI drivers already installed"
fi

# 3. Python virtual environment
echo ""
echo "==> Setting up Python virtual environment..."
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 -m venv "$PROJECT_DIR/venv"
source "$PROJECT_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt

# 4. ASTAP (offline plate solver)
echo ""
echo "==> Installing ASTAP plate solver..."
if ! command -v astap &>/dev/null; then
    cd /tmp
    ASTAP_VER="2024.01.01"
    wget -q "https://www.hnsky.org/software/astap_linux_arm64.zip" -O astap.zip || \
        wget -q "https://www.hnsky.org/software/astap_linux_arm.zip" -O astap.zip || \
        echo "ASTAP download failed. Install manually from https://www.hnsky.org/astap.htm"
    if [ -f astap.zip ]; then
        unzip -o astap.zip
        sudo cp astap /usr/local/bin/
        sudo chmod +x /usr/local/bin/astap
        echo "ASTAP installed"
    fi
    rm -f astap.zip astap
else
    echo "ASTAP already installed: $(astap --version 2>&1 || true)"
fi

# 5. udev rules for ZWO cameras and FTDI/EQDIR
echo ""
echo "==> Setting up udev rules..."
sudo bash -c 'cat > /etc/udev/rules.d/99-zwo.rules' <<'RULE'
SUBSYSTEM=="usb", ATTR{idVendor}=="03c3", MODE="0666"
SUBSYSTEM=="usb", ATTR{idVendor}=="0403", ATTR{idProduct}=="6001", MODE="0666"
SUBSYSTEM=="usb", ATTR{idVendor}=="0403", ATTR{idProduct}=="6014", MODE="0666"
SUBSYSTEM=="usb", ATTR{idVendor}=="10c4", ATTR{idProduct}=="ea60", MODE="0666"
RULE
sudo udevadm control --reload-rules
sudo udevadm trigger

# 6. Enable SPI/I2C (if needed for touchscreen)
echo ""
echo "==> Enabling interfaces..."
sudo raspi-config nonint do_spi 0 2>/dev/null || true
sudo raspi-config nonint do_i2c 0 2>/dev/null || true

# 7. Create systemd service
echo ""
echo "==> Creating systemd service..."
sudo bash -c "cat > /etc/systemd/system/telescope.service" <<SERVICE
[Unit]
Description=Telescope Handcontroller Replacement
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python3 $PROJECT_DIR/src/main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
echo "Virtual environment created at $PROJECT_DIR/venv"
echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start manually:  python3 src/main.py"
echo "To enable autostart: sudo systemctl enable telescope && sudo systemctl start telescope"
echo ""
echo "Connect EQDIR cable from mount RJ45 to Pi USB."
echo "Connect ZWO cameras to Pi USB."
echo "Logs: /tmp/telescope_controller.log"
