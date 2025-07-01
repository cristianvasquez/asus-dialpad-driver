# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Linux driver for ASUS laptops with touchpad DialPad functionality. It creates a virtual circular input device that detects touch gestures on the touchpad and translates them into keyboard shortcuts or media controls. The driver supports both X11 and Wayland desktop environments.

## Development Commands

### Installation and Setup
```bash
# Standard installation
bash install.sh

# Custom installation with specific paths
INSTALL_DIR_PATH="/home/$USER/.local/share/asus-dialpad-driver" \
INSTALL_UDEV_DIR_PATH="/etc/udev" \
SERVICE_INSTALL_DIR_PATH="/home/$USER/.config/systemd/user/" \
bash install.sh

# Check device compatibility before installation
bash install_device_check.sh
```

### Testing and Debugging
```bash
# Manual driver execution (bypass systemd service)
/usr/share/asus-dialpad-driver/.env/bin/python3 \
/usr/share/asus-dialpad-driver/dialpad.py <layout_name>

# Enable/disable driver via config modification
sed -i "s/enabled = 0/enabled = 1/g" /usr/share/asus-dialpad-driver/dialpad_dev
sed -i "s/enabled = 1/enabled = 0/g" /usr/share/asus-dialpad-driver/dialpad_dev

# Check I2C device detection
ls /dev/i2c-*
i2cdetect -l
```

### Service Management
```bash
# Install systemd service
bash install_service.sh

# Service control
systemctl --user start asus-dialpad-driver
systemctl --user stop asus-dialpad-driver
systemctl --user status asus-dialpad-driver
systemctl --user enable/disable asus-dialpad-driver

# View logs
journalctl --user -u asus-dialpad-driver -f
```

### Development Environment
```bash
# Using Nix (preferred for reproducible builds)
nix develop  # Enter development shell
nix build    # Build package

# Manual Python environment setup
python3 -m venv .env
source .env/bin/activate
pip install -r requirements.txt
```

## Architecture Overview

### Core Components

**`dialpad.py` (1,477 lines)** - Main driver application with these key responsibilities:
- Session detection (X11/Wayland) with desktop environment support (KDE, GNOME)
- Device auto-detection from `/proc/bus/input/devices` 
- I2C communication for touchpad control
- Circular gesture recognition with configurable slice mapping
- Virtual input device management via libevdev
- Real-time configuration monitoring with inotify

**Layout System (`layouts/` directory):**
- Device-specific configuration modules (e.g., `proartp16.py`, `asusvivobook16x.py`)
- Each layout defines circle geometry, app-specific shortcuts, and trigger behaviors
- Support for nested (concentric circles) and non-nested designs

**Hardware Interface:**
- I2C bus communication for touchpad enable/disable
- Support for multiple ASUS touchpad variants (ASUE, ELAN, ASUP, etc.)
- Device compatibility database in `laptop_touchpad_dialpad_layouts.csv`

### Key Architectural Patterns

**Multi-Desktop Support:**
- Dynamic session type detection (X11/Wayland)
- Desktop-specific window title retrieval
- Fallback mechanisms for different environments

**Configuration Management:**
- INI-style config file (`dialpad_dev`) with runtime monitoring
- Persistent enable/disable state across reboots
- Real-time layout switching without service restart

**Input Processing Pipeline:**
1. Raw touchpad events → Coordinate mapping
2. Circular position calculation → Slice/sector determination  
3. App context detection → Shortcut mapping lookup
4. Virtual key event generation → System input injection

## Important Files and Directories

- **`dialpad.py`** - Main driver logic and event processing
- **`layouts/`** - Device-specific configuration modules
- **`install*.sh`** - Installation scripts with package manager detection
- **`asus_dialpad_driver.*.service`** - Systemd service definitions for X11/Wayland
- **`laptop_touchpad_dialpad_layouts.csv`** - Hardware compatibility database
- **`nix/`** - Nix package definitions for reproducible builds
- **`requirements*.txt`** - Python dependencies (libevdev, numpy, pyinotify, etc.)

## Development Notes

**No Traditional Testing Framework:** The project uses hardware compatibility validation and manual testing procedures rather than unit tests.

**Configuration Hot-Reloading:** The driver monitors config file changes via inotify and applies updates without restart.

**Hardware Detection:** Device compatibility is determined by matching touchpad device names against known patterns in the CSV database.

**Virtual Device Management:** Uses libevdev to create virtual input devices with dynamically enabled keycodes based on configured shortcuts.

## Common Troubleshooting

- Driver not responding: Check I2C permissions and device detection
- Wrong shortcuts triggered: Verify layout selection matches hardware model
- Service fails to start: Check desktop session type (X11 vs Wayland) and corresponding service file
- Configuration changes ignored: Ensure config file has proper permissions and inotify access