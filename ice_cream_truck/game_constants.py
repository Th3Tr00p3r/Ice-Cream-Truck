"""
Game Constants
"""

from helper import ScreenProps, Vector

# General
COLORS = {"red", "deepskyblue", "lime", "gold", "brown", "white", "mediumpurple", "pink"}
DEFAULT_FONT_SIZE = 40

# Physics
GRAVITY = 1.0
FRICTION = 0.95

# Window dimensions
SCREEN_PROPS = ScreenProps(1600, 800)
SCREEN_TITLE = "Ice Cream Truck"

# Viewport margins
# How close do we have to be to scroll the viewport?
LEFT_VIEWPORT_MARGIN = 0
RIGHT_VIEWPORT_MARGIN = 0
TOP_VIEWPORT_MARGIN = 10
BOTTOM_VIEWPORT_MARGIN = 600

# Scaling Constants
MAP_SCALING = 0.5
CHARACTER_SCALING = 1.1
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
PLAYER_COLORS = {"deepskyblue", "red", "gold"}

# Ice Cream Truck constants
TRUCK_START_POS = Vector(750, 305)  # pixels from bottom, pixels from left
