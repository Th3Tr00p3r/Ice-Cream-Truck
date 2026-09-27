"""
Game Constants
"""

import sys

import arcade
from helper import ScreenProps, Vector

# Platform: the web build runs under Pyodide
IN_BROWSER = sys.platform == "emscripten"

# Paths and filenames
HIGH_SCORES_FILENAME = "ice_cream_truck_high_scores"

# General
COLORS = {"crimson", "deepskyblue", "lime", "gold", "brown", "white", "mediumpurple", "pink"}
DEFAULT_FONT_SIZE = 40
ANY_KEY = [key for key in arcade.key.__dict__.values() if isinstance(key, int)]
KEY_STR_DICT = {key: char for key, char in zip(range(97, 122 + 1), "ABCDEFGHIJKLMNOPQRSTUVWXYZ")}

# Physics
GRAVITY = 1.0
FRICTION = 0.9

# Window dimensions
SCREEN_PROPS = ScreenProps(1600, 800)
SCREEN_RECT = arcade.LBWH(0, 0, SCREEN_PROPS.width, SCREEN_PROPS.height)
SCREEN_TITLE = "Ice Cream Truck"

# Viewport margins
# How close do we have to be to scroll the viewport?
LEFT_VIEWPORT_MARGIN = 0
RIGHT_VIEWPORT_MARGIN = 0
TOP_VIEWPORT_MARGIN = 10
BOTTOM_VIEWPORT_MARGIN = 600

# Scaling Constants
MAP_SCALING = 0.5
CHARACTER_SCALING = 1.5
ICE_CREAM_TRUCK_SCALING = 0.6
POPSICLE_SCALING = 0.5

# General Sprite Constants
FACE_RIGHT = 1
FACE_LEFT = -1
LEFT = -1
RIGHT = 1
STOP = 0

# PlayerCat constants
PLAYER_START_POS = Vector(100, 450)  # pixels from bottom, pixels from left
N_JUMPS = 2
PLAYER_COLORS = {"deepskyblue", "crimson", "gold"}

# Ice Cream Truck constants
TRUCK_START_POS = Vector(750, 305)  # pixels from bottom, pixels from left
