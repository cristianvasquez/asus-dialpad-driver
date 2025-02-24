from libevdev import EV_KEY

top_right_icon_width = 250
top_right_icon_height = 250

# TODO: not validated (atleast the paddings have to be probably increased based on image = increasing circle_center_x and circle_center_y)
circle_diameter = 919
center_button_diameter = 364
circle_center_x = 586
circle_center_y = 573

app_shortcuts = {
    "code": {
        "center": {"key": EV_KEY.KEY_MUTE, "trigger": "release"},
        "clockwise": {"key": EV_KEY.KEY_VOLUMEUP, "trigger": "immediate"},
        "counterclockwise": {"key": EV_KEY.KEY_VOLUMEDOWN, "trigger": "immediate"}
    },
    "firefox": {
        "center": {"key": EV_KEY.KEY_MUTE, "trigger": "release"},
        "clockwise": {"key": EV_KEY.KEY_VOLUMEUP, "trigger": "immediate"},
        "counterclockwise": {"key": EV_KEY.KEY_VOLUMEDOWN, "trigger": "immediate"}
    },
    "none": {
        "center": {"key": EV_KEY.KEY_MUTE, "trigger": "release"},
        "clockwise": {"key": EV_KEY.KEY_VOLUMEUP, "trigger": "immediate"},
        "counterclockwise": {"key": EV_KEY.KEY_VOLUMEDOWN, "trigger": "immediate"}
    }
}