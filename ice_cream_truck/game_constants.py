"""
Game Constants
"""

from types import SimpleNamespace

from helper import ScreenProps, Vector

# Physics
GRAVITY = 1.0
FRICTION = 0.95

# Window dimensions
SCREEN_PROPS = ScreenProps(1500, 975)
SCREEN_TITLE = "Ice Cream Truck"

# Viewport margins
# How close do we have to be to scroll the viewport?
LEFT_VIEWPORT_MARGIN = 500
RIGHT_VIEWPORT_MARGIN = 500
TOP_VIEWPORT_MARGIN = 150
BOTTOM_VIEWPORT_MARGIN = 0

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

# Player constants
PLAYER_ACCELERATION_MAGNITUDE = 0.75  # TESTESTEST
PLAYER_MOVE_SPEED = SimpleNamespace(RUN=10, SLIDE=5, JUMP=20, POUNCE=35)  # pixels per frame
PLAYER_START_POS = Vector(100, 450)  # pixels from bottom, pixels from left
N_JUMPS = 2

# Ice Cream Truck constants
TRUCK_START_POS = Vector(750, 305)  # pixels from bottom, pixels from left
POPSICLE_COLORS = ["red", "blue", "green", "yellow", "brown", "white", "purple", "pink"]
