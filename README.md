# ASUS Vivobook DialPad Driver (Simplified)

A simple Python driver for ASUS Vivobook 16X touchpad DialPad functionality on Linux.

## Quick Start

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Start the dialpad service:**
   ```bash
   ./vivodial-service-up
   ```

3. **Stop the dialpad service:**
   ```bash
   ./vivodial-service-down
   ```

## Features

- **Simple operation:** Just two commands to start/stop
- **Background service:** Runs in background with PID management
- **Vivobook 16X support:** Optimized for ASUS Vivobook 16X dialpad
- **Touch gesture recognition:** Circular gestures and center button
- **App-specific shortcuts:** Different shortcuts for different applications

## Files

- `dialpad.py` - Main driver application
- `layouts/asusvivobook16x.py` - Vivobook 16X configuration
- `vivodial-service-up` - Start the service
- `vivodial-service-down` - Stop the service
- `pyproject.toml` - Python dependencies and project config

## Configuration

The dialpad configuration is in `layouts/asusvivobook16x.py`:

```python
circle_diameter = 1400
center_button_diameter = 250
circle_center_x = 770
circle_center_y = 750
```

Customize the `app_shortcuts` dictionary to add shortcuts for different applications.

## Logs

Service logs are written to `.vivodial.log` in the project directory.

## Requirements

- Python 3
- ASUS Vivobook 16X with dialpad touchpad
- Linux with X11 or Wayland support
- Required Python packages (see pyproject.toml)

## License

GPL v2