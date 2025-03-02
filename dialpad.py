#!/usr/bin/env python3

import logging
import os
import importlib
import sys
import threading
from time import sleep, time
import Xlib.display
import Xlib.X
from libevdev import EV_ABS, EV_KEY, EV_LED, EV_MSC, EV_SYN, Device, InputEvent, const, device
from pyinotify import WatchManager, IN_CLOSE_WRITE, IN_IGNORED, IN_MOVED_TO, AsyncNotifier
from smbus2 import SMBus, i2c_msg
from typing import Optional
import re
import math
from pywayland.client import Display
from pywayland.protocol.wayland import WlSeat
import subprocess
import configparser

# Logging setup
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(message)s',
    level=os.environ.get('LOG', 'INFO')
)
log = logging.getLogger('asus-dialpad-driver')

# Detect session type
xdg_session_type = os.environ.get('XDG_SESSION_TYPE')
if not xdg_session_type:
    log.error("XDG session type is not set. Exiting.")
    sys.exit(1)

# Setup display for X11
display = None
display_wayland = None
if xdg_session_type == "x11":
    try:
        display = Xlib.display.Display(os.environ.get('DISPLAY'))
        log.info("X11 session detected and connected.")
    except Exception as e:
        log.error(f"Failed to connect to X11 display: {e}")
        sys.exit(1)
else:
    try:
        display_wayland = Display(os.environ.get('WAYLAND_DISPLAY'))
        display_wayland.connect()
        log.info("Wayland session detected and connected.")
    except Exception as e:
        log.error(f"Failed to connect to Wayland display: {e}")
        sys.exit(1)

dialpad: bool = False

# DialPad layout model
model = None
if len(sys.argv) > 1:
    model = sys.argv[1]
try:
    model_layout = importlib.import_module('layouts.' + model)
except:
    log.error("DialPad layout *.py from dir layouts is required as first argument. Re-run install script or add missing first argument (valid value is default).")
    sys.exit(1)

# Config file dir
config_file_dir = ""
if len(sys.argv) > 2:
    config_file_dir = sys.argv[2]
# When is given config dir empty or is used default -> to ./ because inotify needs check folder (nor nothing = "")
if config_file_dir == "":
     config_file_dir = "./"

# Layout
circle_diameter = getattr(model_layout, "circle_diameter", 0)
center_button_diameter = getattr(model_layout, "center_button_diameter", 0)
circle_center_x = getattr(model_layout, "circle_center_x", 0)
circle_center_y = getattr(model_layout, "circle_center_y", 0)
top_right_icon_width = getattr(model_layout, "top_right_icon_width", 0)
top_right_icon_height = getattr(model_layout, "top_right_icon_height", 0)

# App-specific configuration (add more mappings as needed)
app_shortcuts = getattr(model_layout, "app_shortcuts", {})

# Figure out devices from devices file
touchpad: Optional[str] = None
touchpad_name: Optional[str] = None
device_id: Optional[str] = None
device_addr: Optional[int] = None

# Constants
try_times = 5
try_sleep = 0.1

# Look into the devices file #
while try_times > 0:

    touchpad_detected = 0

    with open('/proc/bus/input/devices', 'r') as f:
        lines = f.readlines()
        for line in lines:
            # Look for the touchpad #

            # https://github.com/mohamed-badaoui/asus-touchpad-numpad-driver/issues/87
            # https://github.com/asus-linux-drivers/asus-numberpad-driver/issues/95
            # https://github.com/asus-linux-drivers/asus-numberpad-driver/issues/110
            # https://github.com/asus-linux-drivers/asus-numberpad-driver/issues/161
            # https://github.com/asus-linux-drivers/asus-numberpad-driver/issues/198
            if (touchpad_detected == 0 and ("Name=\"ASUE" in line or "Name=\"ELAN" in line or "Name=\"ASUP" or "Name=\"ASUF" in line) and "Touchpad" in line and not "9009" in line):
                touchpad_detected = 1
                log.info('Detecting touchpad from string: \"%s\"', line.strip())
                touchpad_name = line.split("\"")[1]

                # https://github.com/asus-linux-drivers/asus-numberpad-driver/issues/161
                if ("ASUF1416" in line or "ASUF1205" in line or "ASUF1204" in line):
                  device_addr = 0x38
                else:
                  device_addr = 0x15

            if touchpad_detected == 1:
                if "S: " in line:
                    # search device id
                    device_id = re.sub(r".*i2c-(\d+)/.*$", r'\1', line).replace("\n", "")
                    log.info('Set touchpad device id %s from %s', device_id, line.strip())

                if "H: " in line:
                    touchpad = line.split("event")[1]
                    touchpad = touchpad.split(" ")[0]
                    touchpad_detected = 2
                    log.info('Set touchpad id %s from %s', touchpad, line.strip())

              # Do not stop looking if touchpad and keyboard have been found
            # because more drivers can be installed
            # https://github.com/mohamed-badaoui/asus-touchpad-numpad-driver/issues/87
            # https://github.com/asus-linux-drivers/asus-numberpad-driver/issues/95
            #if touchpad_detected == 2 and keyboard_detected == 2:
            #    break

    if touchpad_detected != 2:
        try_times -= 1
        if try_times == 0:
            with open('/proc/bus/input/devices', 'r') as f:
                lines = f.readlines()
                for line in lines:
                    log.error(line)
            if touchpad_detected != 2:
                log.error("Can't find touchpad (code: %s)", touchpad_detected)
                sys.exit(1)
            if touchpad_detected == 2 and not device_id.isnumeric():
                log.error("Can't find device id")
                sys.exit(1)
    else:
        break

    sleep(try_sleep)

# Open a handle to "/dev/i2c-x", representing the I2C bus
try:
    bus = SMBus()
    bus.open(int(device_id))
    bus.close()
except:
    log.error("Can't open the I2C bus connection (id: %s)", device_id)
    sys.exit(1)

# App-specific configuration (add more mappings as needed)


# Initialize the virtual device globally
uinput_device = None

# Config
CONFIG_FILE_NAME = "dialpad_dev"
CONFIG_SECTION = "main"
CONFIG_ENABLED = "enabled"
CONFIG_ENABLED_DEFAULT = False
CONFIG_SLICES_COUNT = "slices_count"
CONFIG_SLICES_COUNT_DEFAULT = 4
CONFIG_DISABLE_DUE_INACTIVITY_TIME = "disable_due_inactivity_time"
CONFIG_DISABLE_DUE_INACTIVITY_TIME_DEFAULT = 0
CONFIG_TOUCHPAD_DISABLES_DIALPAD = "touchpad_disables_dialpad"
CONFIG_TOUCHPAD_DISABLES_DIALPAD_DEFAULT = True
CONFIG_ACTIVATION_TIME = "activation_time"
CONFIG_ACTIVATION_TIME_DEFAULT = True
CONFIG_SUPPRESS_APP_SPECIFICS_SHORTCUTS = "config_supress_app_specifics_shortcuts"
CONFIG_SUPPRESS_APP_SPECIFICS_SHORTCUTS_DEFAULT = False

config_file_path = config_file_dir + CONFIG_FILE_NAME
config = configparser.ConfigParser()
config_lock = threading.Lock()

# Start monitoring the touchpad
fd_t = open('/dev/input/event' + str(touchpad), 'rb')
d_t = Device(fd_t)

# Get touchpad dimensions
abs_x = d_t.absinfo[EV_ABS.ABS_X]
abs_y = d_t.absinfo[EV_ABS.ABS_Y]
min_x, max_x = abs_x.minimum, abs_x.maximum
min_y, max_y = abs_y.minimum, abs_y.maximum
log.info('Touchpad min-max: x %d-%d, y %d-%d', min_x, max_x, min_y, max_y)

last_event_time = 0

def parse_value_from_config(value):
    if value == '0':
        return False
    elif value == '1':
        return True
    else:
        return value

def parse_value_to_config(value):
    if value == True:
        return '1'
    elif value == False:
        return '0'
    else:
        return str(value)

def config_save():
    global config_file_dir, config_file_path

    try:
        with open(config_file_path, 'w') as configFile:
            config.write(configFile)
            log.debug('Writting to config file: \"%s\"', configFile)
    except:
        log.error('Error during writting to config file: \"%s\"', config_file_path)
        pass

def config_set(key, value, no_save=False, already_has_lock=False):
    global config, config_file_dir, config_lock

    if not already_has_lock:
        #log.debug("config_set: config_lock.acquire will be called")
        config_lock.acquire()
        #log.debug("config_set: config_lock.acquire called succesfully")

    config.set(CONFIG_SECTION, key, parse_value_to_config(value))
    log.info('Setting up for config file key: \"%s\" with value: \"%s\"', key, value)

    if not no_save:
        config_save()

    if not already_has_lock:
        # because inotify (deadlock)
        sleep(0.1)
        config_lock.release()

    return value

# methods for read & write from config file
def config_get(key, key_default):
    try:
        value = config.get(CONFIG_SECTION, key)
        parsed_value = parse_value_from_config(value)
        return parsed_value
    except:
        config.set(CONFIG_SECTION, key, parse_value_to_config(key_default))
        return key_default

def read_config_file():
    global config, config_file_path

    try:
        if not config.has_section(CONFIG_SECTION):
            config.add_section(CONFIG_SECTION)

        config.read(config_file_path)
    except:
        pass

def load_all_config_values():
    global config
    global disable_due_inactivity_time
    global touchpad_disables_dialpad
    global activation_time
    global config_lock
    global slices_count
    global suppress_app_specifics_shortcuts

    #log.debug("load_all_config_values: config_lock.acquire will be called")
    config_lock.acquire()
    #log.debug("load_all_config_values: config_lock.acquire called succesfully")

    read_config_file()

    disable_due_inactivity_time = float(config_get(CONFIG_DISABLE_DUE_INACTIVITY_TIME, CONFIG_DISABLE_DUE_INACTIVITY_TIME_DEFAULT))
    touchpad_disables_dialpad = config_get(CONFIG_TOUCHPAD_DISABLES_DIALPAD, CONFIG_TOUCHPAD_DISABLES_DIALPAD_DEFAULT)
    activation_time = float(config_get(CONFIG_ACTIVATION_TIME, CONFIG_ACTIVATION_TIME_DEFAULT))
    enabled = config_get(CONFIG_ENABLED, CONFIG_ENABLED_DEFAULT)
    slices_count = int(config_get(CONFIG_SLICES_COUNT, CONFIG_SLICES_COUNT_DEFAULT))
    suppress_app_specifics_shortcuts = int(config_get(CONFIG_SUPPRESS_APP_SPECIFICS_SHORTCUTS, CONFIG_SUPPRESS_APP_SPECIFICS_SHORTCUTS_DEFAULT))

    config_lock.release()

    if enabled is not dialpad:
        toggle_top_right_icon(dialpad)

def send_value_to_touchpad_via_i2c(value):
    global device_id, device_addr

    try:
        with SMBus(int(device_id)) as bus:
            data = [0x05, 0x00, 0x3d, 0x03, 0x06, 0x00, 0x07, 0x00, 0x0d, 0x14, 0x03, int(value, 16), 0xad]
            msg = i2c_msg.write(device_addr, data)
            bus.i2c_rdwr(msg)
    except Exception as e:
        log.error('Error during sending via i2c: \"%s\"', e)

def initialize_virtual_device():
    global uinput_device, dev

    try:
        # Create the virtual device
        dev = Device()
        dev.name = touchpad_name.split(" ")[0] + " " + touchpad_name.split(" ")[1] + " DialPad"

        # Enable all keys from the configuration
        for shortcuts in app_shortcuts.values():
            for action, config in shortcuts.items():
                dev.enable(config["key"])

        # Create the uinput device
        uinput_device = dev.create_uinput_device()
        log.info("Virtual device initialized successfully.")
        sleep(0.5)  # Allow time for the device to initialize
    except Exception as e:
        log.error(f"Error initializing virtual device: {e}")
        sys.exit(1)  # Exit if initialization fails

def get_window_kde_wayland_title(window_id):
    try:
        cmd = ['qdbus', 'org.kde.KWin', f'/org/kde/KWin/Window/{window_id}', 'org.kde.KWin.Window.caption']
        output = subprocess.check_output(cmd).decode().strip()
        return output
    except Exception as e:
        log.error("Error getting KDE window title: %s", e)
        return None

def get_active_window_kde_wayland_title():
    try:
        cmd = ['qdbus', 'org.kde.KWin', '/KWin', 'org.kde.KWin.activeWindow']
        output = subprocess.check_output(cmd).decode().strip()
        match = re.search(r"(\d+)", output)
        if match:
            window_id = match.group(1)
            return get_window_kde_wayland_title(window_id)
    except Exception as e:
        log.error("Error getting active KDE window title: %s", e)
        return None

def get_active_window_gnome_wayland_title():
    try:
        session_bus = dbus.SessionBus()
        shell = session_bus.get_object('org.gnome.Shell', '/org/gnome/Shell')
        active_window = shell.Get('org.gnome.Shell', 'focusWindow')
        return active_window.get('title', None)
    except Exception as e:
        log.error("Error getting active GNOME Wayland window title: %s", e)
        return None

def get_active_window_title():
    if xdg_session_type == "x11" and display:
        try:
            root = display.screen().root
            window_id = root.get_full_property(display.intern_atom('_NET_ACTIVE_WINDOW'), Xlib.X.AnyPropertyType).value[0]
            window = display.create_resource_object('window', window_id)
            window_name = window.get_full_property(display.intern_atom('_NET_WM_NAME'), Xlib.X.AnyPropertyType)
            return window_name.value.decode() if window_name else None
        except Exception as e:
            log.error("Error retrieving active window title (X11): %s", e)
            return None
    else:
        kde_title = get_active_window_kde_wayland_title()
        if kde_title:
            return kde_title

        gnome_title = get_active_window_gnome_wayland_title()
        if gnome_title:
            return gnome_title

    log.error("Unsupported session type or display not connected.")
    return None

def emulate_shortcuts(touch_input, event_code):
    global suppress_app_specifics_shortcuts

    # Get the active window title
    window_title = get_active_window_title()

    # Determine the app configuration based on the window title
    app_name = None
    if window_title:
        app_name = next((app for app in app_shortcuts if app in window_title.lower()), None)

    # Use app-specific shortcuts if found; otherwise, fall back to default shortcuts
    shortcuts = app_shortcuts[app_name] if app_name and not suppress_app_specifics_shortcuts else app_shortcuts["none"]

    # Get the shortcut for the given touch input
    shortcut = shortcuts.get(touch_input, None)

    if shortcut:
        key_code = shortcut["key"]
        trigger_mode = shortcut.get("trigger", "release")  # Load trigger mode per shortcut

        if trigger_mode == "immediate" and event_code:
            send_key_event(key_code, press=True)
            send_key_event(key_code, press=False)
        if trigger_mode == "release" and not event_code:
            send_key_event(key_code, press=True)
            send_key_event(key_code, press=False)

        log.info(f"Executing shortcut for {'default' if not app_name else app_name}: {key_code.name} with trigger mode: {trigger_mode}")
    else:
        log.info(f"No shortcut mapped for touch input: {touch_input} in {'default' if not app_name else app_name}")


def send_key_event(key_code, press=True):
    global uinput_device

    if not uinput_device:
        log.error("Virtual device is not initialized. Cannot send key events.")
        return

    try:
        event_value = 1 if press else 0  # 1 for key press, 0 for key release
        uinput_device.send_events([
            InputEvent(key_code, event_value),
            InputEvent(EV_SYN.SYN_REPORT, 0)  # Sync event
        ])
        log.info(f"Sent key {'press' if press else 'release'} event: {key_code.name}")
    except Exception as e:
        log.error(f"Error sending key event: {e}")

def activate_dialpad():
    global dialpad

    # unlock
    send_value_to_touchpad_via_i2c("0x60")
    # activate
    send_value_to_touchpad_via_i2c("0x01")

    config_set(CONFIG_ENABLED, True)

    dialpad = True

def deactivate_dialpad():
    global dialpad

    # lock
    send_value_to_touchpad_via_i2c("0x61")
    # deactivate
    send_value_to_touchpad_via_i2c("0x00")

    config_set(CONFIG_ENABLED, False)

    dialpad = False

# Function to enable/disable the DialPad
def toggle_top_right_icon(current_state_is_enabled):

    if current_state_is_enabled:
        deactivate_dialpad()
    else:
        activate_dialpad()

    log.info(f"Toggling top-right icon: {'Disabling' if current_state_is_enabled else 'Enabling'}")

def handle_rotation(direction):
    """
    Handle rotation events based on the detected direction.
    :param direction: "clockwise" or "counterclockwise"
    """
    log.info(f"Handling rotation: {direction}")
    if direction == "clockwise":
        # Example: Increase volume
        log.info("Volume up triggered")
        send_key_event(EV_KEY.KEY_VOLUMEUP)  # Replace with your specific action
    elif direction == "counterclockwise":
        # Example: Decrease volume
        log.info("Volume down triggered")
        send_key_event(EV_KEY.KEY_VOLUMEDOWN)  # Replace with your specific action

def is_pressed_touchpad_top_right_icon():
    global top_right_icon_width, top_right_icon_height, abs_mt_slot_x_values, abs_mt_slot_y_values, abs_mt_slot_value, maxx

    if abs_mt_slot_x_values[abs_mt_slot_value] >= maxx - top_right_icon_width and\
        abs_mt_slot_y_values[abs_mt_slot_value] >= 0 and abs_mt_slot_y_values[abs_mt_slot_value] <= top_right_icon_height:
            return True

    return False

def check_dialpad_automatical_disable_or_idle_due_inactivity():
    global disable_due_inactivity_time, last_event_time, dialpad, stop_threads

    while not stop_threads:

        if\
            disable_due_inactivity_time and\
            dialpad and\
            last_event_time != 0 and\
            time() > disable_due_inactivity_time + last_event_time:

            deactivate_dialpad()
            log.info("DialPad deactivated")

        sleep(1)


gsettings_failure_count = 0
gsettings_max_failure_count = 3

qdbus_failure_count = 0
qdbus_max_failure_count = 3

getting_device_via_xinput_status_failure_count = 0
getting_device_via_xinput_status_max_failure_count = 3

getting_device_via_synclient_status_failure_count = 0
getting_device_via_synclient_status_max_failure_count = 3

def qdbusSet(value):
    global qdbus_failure_count, qdbus_max_failure_count, touchpad

    if qdbus_failure_count < qdbus_max_failure_count:
        try:
            cmd = [
                'qdbus',
                'org.kde.KWin',
                f'/org/kde/KWin/InputDevice/event{touchpad}',
                'org.kde.KWin.InputDevice.sendEvents',
                str(value)
            ]
            subprocess.call(cmd)
        except Exception as e:
            log.debug(e, exc_info=True)
            qdbus_failure_count+=1
    else:
        log.debug('Qdbus failed more than: "%s" so is not trying anymore', qdbus_max_failure_count)

def qdbusSetTouchpadSendEvents(value):
    qdbusSet(value)

def gsettingsSet(path, name, value):
    global gsettings_failure_count, gsettings_max_failure_count

    if gsettings_failure_count < gsettings_max_failure_count:
        try:
            sudo_user = os.environ.get('SUDO_USER')
            if sudo_user is not None:
                cmd = ['runuser', '-u', sudo_user, 'gsettings', 'set', path, name, str(value)]
            else:
                cmd = ['gsettings', 'set', path, name, str(value)]

            log.debug(cmd)
            subprocess.call(cmd)
        except Exception as e:
            log.debug(e, exc_info=True)
            gsettings_failure_count+=1
    else:
        log.debug('Gsettings failed more than: "%s" so is not trying anymore', gsettings_max_failure_count)

def gsettingsSetTouchpadSendEvents(value):
    gsettingsSet('org.gnome.desktop.peripherals.touchpad', 'send-events', 'enabled' if value else 'disabled')

def set_touchpad_prop_send_events(value):
    global touchpad_name, gsettings_failure_count, gsettings_max_failure_count, qdbus_max_failure_count, qdbus_failure_count, getting_device_via_xinput_status_failure_count, getting_device_via_xinput_status_max_failure_count, getting_device_via_synclient_status_failure_count, getting_device_via_synclient_status_max_failure_count

    # 1. priority - gsettings (gnome) or qdbus (kde)
    if gsettings_failure_count < gsettings_max_failure_count:
        gsettingsSetTouchpadSendEvents(value)
    if qdbus_failure_count < qdbus_max_failure_count:
        qdbusSetTouchpadSendEvents(value)

    # 2. priority - xinput
    if getting_device_via_xinput_status_failure_count > getting_device_via_xinput_status_max_failure_count:
        log.debug('Setting libinput Send Events via xinput failed more than: "%s" times so is not trying anymore', getting_device_via_xinput_status_max_failure_count)
    else:
        try:
            cmd = ["xinput", "enable" if value else "disable", touchpad_name]
            log.debug(cmd)
            subprocess.call(cmd)
            return
        except:
            getting_device_via_xinput_status_failure_count+=1
            log.error('Setting libinput Send Events via xinput failed')

    # 3. priority - synclient
    if getting_device_via_synclient_status_failure_count > getting_device_via_synclient_status_max_failure_count:
        log.debug('Setting libinput Send Events via synclient failed more than: "%s" times so is not trying anymore', getting_device_via_xinput_status_max_failure_count)
    try:
        cmd = ["synclient", "TouchpadOff=" + str(value)]
        log.debug(cmd)
        subprocess.call(cmd)
        return
    except:
        getting_device_via_synclient_status_failure_count+=1

def listen_touchpad_events():
    global slices_count, activation_time, last_event_time, dialpad

    try:

            # Define circle and slices
            circle_radius = circle_diameter / 2
            center_button_radius = center_button_diameter / 2


            # Define the bounds for the top-right icon
            top_right_icon_bounds = {
                "x_min": max_x - top_right_icon_width,
                "x_max": max_x,
                "y_min": 0,
                "y_max": top_right_icon_height
            }

            log.info("Listening to touchpad events...")

            touch_x, touch_y = None, None
            finger_detected = False  # Track finger presence
            touch_start_time = None  # Track the time when the touch started
            within_top_right_icon = False  # Track if the touch is within the top-right icon bounds
            icon_activated = False  # Track if the icon has already been activated during this touch
            last_slice = None  # Track the last active slice in the circle
            center_button_triggered = False
            tap_disabled = False  # Track tap-to-click status

            for event in d_t.events():

                last_event_time = time()

                # Handle finger detection
                if event.matches(EV_KEY.BTN_TOOL_FINGER):
                    if event.value == 1:  # Finger down
                        finger_detected = True
                        touch_start_time = time()  # Record the touch start time
                        within_top_right_icon = False  # Reset the flag
                        icon_activated = False  # Reset activation status
                        last_slice = None  # Reset the last slice
                        log.debug("Finger detected.")
                    elif event.value == 0:  # Finger up
                        finger_detected = False
                        touch_start_time = None  # Reset the touch start time
                        within_top_right_icon = False  # Reset the flag
                        icon_activated = False  # Reset activation status
                        last_slice = None  # Reset the last slice
                        log.debug("Finger lifted.")
                        # Reset touch coordinates
                        touch_x, touch_y = None, None

                        if center_button_triggered:
                            emulate_shortcuts("center", event.value)
                            center_button_triggered = False
                        # Re-enable tap-to-click
                        if tap_disabled:
                            set_touchpad_prop_send_events(1)
                            tap_disabled = False

                # Detect touch positions
                if event.matches(EV_ABS.ABS_MT_POSITION_X):
                    touch_x = event.value
                elif event.matches(EV_ABS.ABS_MT_POSITION_Y):
                    touch_y = event.value

                # Check if the touch is in the top-right icon bounds
                if touch_x is not None and touch_y is not None and finger_detected:
                    if (top_right_icon_bounds["x_min"] <= touch_x <= top_right_icon_bounds["x_max"] and
                            top_right_icon_bounds["y_min"] <= touch_y <= top_right_icon_bounds["y_max"]):
                        if not within_top_right_icon:
                            log.debug("Touch entered top-right icon bounds.")
                        within_top_right_icon = True  # Mark that the touch is inside the bounds

                        # Check if the touch duration exceeds the threshold and hasn't been activated yet
                        if touch_start_time and not icon_activated:
                            if (time() - touch_start_time) >= activation_time:
                                log.info("Top-right icon held for the required duration.")
                                # Toggle the top-right icon state
                                toggle_top_right_icon(dialpad)
                                icon_activated = True  # Mark that the icon has been activated
                    else:
                        if within_top_right_icon:
                            log.debug("Touch left top-right icon bounds. Canceling the action.")
                        within_top_right_icon = False  # Mark that the touch has left the bounds
                        touch_start_time = None  # Cancel the action by resetting the start time
                        icon_activated = False  # Reset the activation status to allow future activation

                # Calculate distance and angle for circle-based detection
                if touch_x is not None and touch_y is not None and finger_detected:
                    dx = touch_x - circle_center_x
                    dy = touch_y - circle_center_y
                    distance = math.sqrt(dx**2 + dy**2)
                    angle = (math.atan2(dy, dx) * 180 / math.pi) % 360

                    if distance <= circle_radius and dialpad:

                        # Disable tap-to-click
                        if not tap_disabled:
                            set_touchpad_prop_send_events(0)
                            tap_disabled = True

                        #log.info("Distance: %f, Center button radius: %f", distance, center_button_radius)
                        if distance < center_button_radius and dialpad:  # Center button area
                            # Only trigger if it has not been triggered already in this touch cycle
                            if not center_button_triggered:
                                log.debug("Touch detected in center button area.")
                                # Trigger the center button shortcut
                                emulate_shortcuts("center", event.value)
                                center_button_triggered = True  # Set flag to indicate the button has been pressed
                                icon_activated = True  # Ensure it only triggers once per touch
                        else:
                            # Reset the center button triggered flag if the finger leaves the circle (but not the button area)
                            if center_button_triggered:
                                center_button_triggered = False
                                icon_activated = False  # Allow the center button action to be triggered again

                            # Determine the current slice based on the angle
                            current_slice = int(angle // (360 / slices_count))
                            if current_slice != last_slice:
                                if last_slice is not None:
                                    # Determine the direction of rotation
                                    direction = "clockwise" if (current_slice - last_slice) % slices_count == 1 else "counterclockwise"
                                    log.debug(f"Detected circular motion: {direction}")
                                    # Trigger rotation logic based on the direction
                                    emulate_shortcuts(direction, event.value)
                                last_slice = current_slice
                    else:
                        pass
                        #log.debug("Touch outside the circle. Ignoring.")

    except device.EventsDroppedException:
        for e in dev.sync(True):
            pass
    except Exception as e:
        log.error(f"Error in listen_touchpad_events: {e}")

def check_config_values_changes():
    global config_lock, stop_threads, event_notifier

    while not stop_threads:
        try:
            event_notifier.process_events()
            if event_notifier.check_events():
                event_notifier.read_events()

                if not config_lock.locked():
                    log.info("check_config_values_changes: detected external change of config file -> loading changes")
                    # because file might be read so fast that changes will not be there yet
                    sleep(0.1)
                    load_all_config_values()
                else:
                    log.info("check_config_values_changes: detected internal change of config file -> do nothing -> would be deadlock")

        except KeyboardInterrupt:
            break

    log.info("check_config_values_changes: inotify watching config file ended")


def cleanup():
    global dialpad, display, display_wayland, stop_threads, event_notifier

    log.info("Clean up started")

    # try deactivate first
    try:
        if dialpad:

            dialpad = False
            deactivate_dialpad()
            log.info("DialPad deactivated")

        # then clean up
        stop_threads=True

        if display_wayland:
            display_wayland.disconnect()

        if display:
            try:
                display.close()
            # because may be already closed (e.g. closed connection by server in load_keymap_listener_x11)
            except:
                pass

        if watch_manager:
            watch_manager.close()

        log.info("Clean up finished")
    except:
        log.exception("Clean up error")
        pass

threads = []
stop_threads = False
watch_manager = None
event_notifier = None

try:

    # Initialize the device
    initialize_virtual_device()

    # Load config values
    load_all_config_values()
    config_lock.acquire()
    config_save()
    config_lock.release()
    # because inotify (deadlock)
    sleep(0.5)

    watch_manager = WatchManager()

    path = os.path.abspath(config_file_dir)
    mask = IN_CLOSE_WRITE | IN_IGNORED | IN_MOVED_TO
    watch_manager.add_watch(path, mask)

    event_notifier = AsyncNotifier(watch_manager)

    t = threading.Thread(target=check_dialpad_automatical_disable_or_idle_due_inactivity)
    t.daemon = True
    threads.append(t)
    t.start()

    # Start the touchpad listener in a separate thread
    listen_touchpad_events()
except:
    logging.exception("Listening touchpad events unexpectedly failed")
finally:
    cleanup()
    log.info("Exiting")
    sys.exit(1)