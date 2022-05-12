"""
Game Constants
"""

from helper import Position, ScreenProps

# Physics
GRAVITY = 1.0

# Window dimensions
SCREEN_PROPS = ScreenProps(1000, 650)
SCREEN_TITLE = "Ice Cream Truck"

# Viewport margins
# How close do we have to be to scroll the viewport?
LEFT_VIEWPORT_MARGIN = 50
RIGHT_VIEWPORT_MARGIN = 300
TOP_VIEWPORT_MARGIN = 150
BOTTOM_VIEWPORT_MARGIN = 150

# Scaling Constants
MAP_SCALING = 1.0
CHARACTER_SCALING = 1.0

# Ice Cream Man / Popsicle Constants

# Player constants
PLAYER_MOVE_SPEED = 10  # pixels per frame
PLAYER_JUMP_SPEED = 20  # pixels per frame
PLAYER_START_POS = Position(100, 300)  # pixels from bottom, pixels from left
