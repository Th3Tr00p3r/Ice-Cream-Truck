"""
Game Constants
"""

from types import SimpleNamespace

from helper import ScreenProps, Vector

# Physics
GRAVITY = 1.0

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
CHARACTER_SCALING = 1.0
ICE_CREAM_TRUCK_SCALING = 0.4

# General Sprite Constants
FACE_DIRECTION = SimpleNamespace(RIGHT=0, LEFT=1)

# Player constants
PLAYER_MOVE_SPEED = Vector(10, 20)  # pixels per frame
PLAYER_START_POS = Vector(100, 300)  # pixels from bottom, pixels from left

# Ice Cream Truck constants
TRUCK_START_POS = Vector(1000, 260)  # pixels from bottom, pixels from left
