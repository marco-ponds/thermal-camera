#!/usr/bin/env bash
# One-shot Pi setup (Raspberry Pi OS Lite, 32-bit). Run from this directory:  ./setup.sh
#   1. apt packages        2. venv + pip packages
#   3. PiTFT driver        (Adafruit installer in "drivers" mode: no console, no HDMI mirror)
#      + touchscreen driver (stmpe_ts, loaded at every boot)
#   4. I2C on + bus speed  5. systemd service so the camera starts at boot
# Env overrides:
#   PITFT_ROTATION=90|270  landscape either way up (default 90)
#   I2C_BAUD=1000000       I2C clock; default 400000 (SPEC suggests 1 MHz if your wiring is short/solid)
#   SKIP_PITFT=1           skip the display driver step
set -euo pipefail
cd "$(dirname "$0")"
DIR="$(pwd)"
ROTATION="${PITFT_ROTATION:-90}"
BAUD="${I2C_BAUD:-400000}"

echo ">> apt packages"
sudo apt-get update
sudo apt-get install -y git python3-venv python3-pygame python3-numpy python3-evdev i2c-tools fonts-dejavu-core

echo ">> venv"
python3 -m venv --system-site-packages .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

if [ -z "${SKIP_PITFT:-}" ]; then
  echo ">> PiTFT 3.5\" driver (rotation $ROTATION)"
  # HDMI-mirror mode is refused on Bookworm+ Lite, so install only the driver;
  # the app writes straight into the PiTFT framebuffer.
  rm -rf /tmp/pitft-installer
  git clone --depth 1 https://github.com/adafruit/Raspberry-Pi-Installer-Scripts.git /tmp/pitft-installer
  (cd /tmp/pitft-installer && sudo -E env PATH="$DIR/.venv/bin:$PATH" python3 adafruit-pitft.py \
      --display=35r --rotation="$ROTATION" --install-type=drivers --reboot=no)
fi

echo ">> touchscreen driver"
# The PiTFT's STMPE610 probes, but its touchscreen part (stmpe_ts) isn't
# loaded automatically, so there's no touch input device. Load it on every boot.
echo stmpe_ts | sudo tee /etc/modules-load.d/stmpe-ts.conf >/dev/null
sudo modprobe stmpe_ts || echo "   (stmpe_ts not loaded now; it will load after the reboot)"

echo ">> I2C at $BAUD Hz"
sudo raspi-config nonint do_i2c 0
CONFIG=/boot/firmware/config.txt
[ -f "$CONFIG" ] || CONFIG=/boot/config.txt
if grep -q '^dtparam=i2c_arm_baudrate=' "$CONFIG"; then
  sudo sed -i "s/^dtparam=i2c_arm_baudrate=.*/dtparam=i2c_arm_baudrate=$BAUD/" "$CONFIG"
else
  echo "dtparam=i2c_arm_baudrate=$BAUD" | sudo tee -a "$CONFIG" >/dev/null
fi
sudo usermod -aG i2c,video,input,gpio "$USER"

echo ">> boot service"
sed -e "s|__USER__|$USER|" -e "s|__DIR__|$DIR|g" thermalcam.service | sudo tee /etc/systemd/system/thermalcam.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable thermalcam.service

cat <<MSG

>> Done. Reboot now:  sudo reboot
   First boot: tap the 3 crosses on the PiTFT (touch calibration), then the Live view appears.
   Checks:  i2cdetect -y 1              (expect 33)
            journalctl -u thermalcam -b
MSG
