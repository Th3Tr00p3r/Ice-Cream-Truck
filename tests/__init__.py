"""Put the game dir on sys.path and make it the CWD (the game uses CWD-relative paths)"""

import os
import sys
from pathlib import Path

GAME_DIR = Path(__file__).resolve().parent.parent / "ice_cream_truck"

os.chdir(GAME_DIR)
if str(GAME_DIR) not in sys.path:
    sys.path.insert(0, str(GAME_DIR))
