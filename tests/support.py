"""Shared test base class and helpers: one game window, sound/high-score/randomness isolation"""

import functools
import hashlib
import math
import os
import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import arcade
import game_constants as game
import sprites

import ice_cream_truck as ict
from tests import GAME_DIR

REAL_HIGH_SCORES = GAME_DIR / "ice_cream_truck_high_scores"
DT = 1 / 60


def _file_digest(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


REAL_HIGH_SCORES_DIGEST = _file_digest(REAL_HIGH_SCORES)


def _cache_cat_textures():
    """Speed-only: memoize identical player-cat textures (ICT_TESTS_NO_TEXTURE_CACHE=1 disables)"""
    cls = getattr(sprites, "ColorCatTextures", None)
    original = getattr(cls, "_get_textures", None)
    if original is None or os.environ.get("ICT_TESTS_NO_TEXTURE_CACHE"):
        return
    cache = {}

    @functools.wraps(original)
    def cached(self, *args, **kwargs):
        key = (self.color_str, args, tuple(sorted(kwargs.items())))
        if key not in cache:
            cache[key] = original(self, *args, **kwargs)
        return cache[key]

    cls._get_textures = cached


_cache_cat_textures()

_window = None


def get_window():
    """The single game window shared by all tests"""
    global _window
    if _window is None:
        _window = ict.GameWindow()
    return _window


class approx:
    """Tolerant numeric equality for numbers and sequences (rel=1e-6/abs=1e-12, or abs only)"""

    def __init__(self, expected, rel=None, abs=None):
        self.expected, self.rel, self.abs = expected, rel, abs

    def _close(self, actual, expected):
        if self.abs is not None and self.rel is None:
            tolerance = self.abs
        else:
            rel = 1e-6 if self.rel is None else self.rel
            tolerance = max(rel * math.fabs(expected), 1e-12 if self.abs is None else self.abs)
        return math.fabs(actual - expected) <= tolerance

    def __eq__(self, actual):
        if isinstance(self.expected, (list, tuple)):
            try:
                return len(actual) == len(self.expected) and all(
                    self._close(a, e) for a, e in zip(actual, self.expected)
                )
            except TypeError:
                return False
        try:
            return self._close(actual, self.expected)
        except TypeError:
            return False

    def __repr__(self):
        return f"approx({self.expected!r})"


class GameTestCase(unittest.TestCase):
    """Base test case: shared window plus per-test isolation of scores, sounds and randomness"""

    @classmethod
    def setUpClass(cls):
        cls.window = get_window()

    def setUp(self):
        self.addCleanup(self._check_real_high_scores)
        self.addCleanup(self._reset_viewport)
        self.isolate()

    def isolate(self):
        """(Re)apply per-test isolation; call again at the start of each subTest case"""
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        self.high_scores_file = Path(tmp_dir.name) / "high_scores"
        self.patch(game, "HIGH_SCORES_FILENAME", str(self.high_scores_file))
        self.sounds = []
        sounds = self.sounds
        self.patch(arcade, "play_sound", lambda sound, *a, **kw: sounds.append(sound))
        random.seed(12345)

    def patch(self, target, name, value):
        """Set target.name = value until the end of the test"""
        patcher = mock.patch.object(target, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def closed(self):
        """Intercept window.close() so views can 'quit' without killing the shared window"""
        calls = []
        self.patch(self.window, "close", lambda: calls.append(True))
        return calls

    def no_throws(self):
        """Stop the truck from throwing popsicles (hearts included)"""
        self.patch(sprites.IceCreamTruck, "THROW_PROBABILITY", 0.0)

    def make_game_view(self):
        """A freshly set-up, shown and settled PlatformerView with no random spawns/throws"""
        self.no_throws()
        view = ict.PlatformerView()
        self.window.show_view(view)
        view.setup()
        view.new_cat_prob_frame = 0.0
        settle(view)
        return view

    def _reset_viewport(self):
        self.window.set_viewport(0, game.SCREEN_PROPS.width, 0, game.SCREEN_PROPS.height)

    def _check_real_high_scores(self):
        if _file_digest(REAL_HIGH_SCORES) != REAL_HIGH_SCORES_DIGEST:
            raise AssertionError("real high-scores file was modified!")


class GameViewTestCase(GameTestCase):
    """Test case with a fresh game view in self.game_view"""

    def setUp(self):
        super().setUp()
        self.game_view = self.make_game_view()


def run_frames(view, n, dt=DT):
    """Advance a view by n update frames"""
    for _ in range(n):
        view.on_update(dt)


def tick(window, n=1, dt=DT, draw=True):
    """Emulate the arcade loop: update then draw whatever view is current"""
    for _ in range(n):
        window.current_view.on_update(dt)
        if draw:
            window.current_view.on_draw()


def settle(view, max_frames=300):
    """Run frames until the player stands still on the ground"""
    for _ in range(max_frames):
        view.on_update(DT)
        p = view.player
        if not p.state.is_in_air and p.change_y == 0 and p.change_x == 0:
            return
    raise AssertionError("player never settled")


def make_popsicle(view, color_str, x=None, y=None):
    """Create a motionless regular popsicle (at the player by default) and add it to the game"""
    x = view.player.center_x if x is None else x
    y = view.player.center_y if y is None else y
    pop = sprites.RegularPopsicle(color_str, ict.Vector(x, y), 0, 90)
    view.popsicles.append(pop)
    return pop


def make_heart(view, x=None, y=None):
    """Create a motionless heart popsicle (at the player by default) and add it to the game"""
    x = view.player.center_x if x is None else x
    y = view.player.center_y if y is None else y
    heart = sprites.HeartPopsicle(ict.Vector(x, y), 0, 90)
    view.popsicles.append(heart)
    return heart


COMPETITOR_COLORS = sorted(game.COLORS - game.PLAYER_COLORS)


def make_cat(view, x, y, color_str="lime", scale=None, on_ground=False, add=True, run=100.0):
    """Create a competitor cat configured like the game does, optionally adding it to the game"""
    cat = sprites.CompetitorCat(
        init_position=ict.Vector(x, y),
        init_speed=ict.Vector(0, 0),
        speeds=SimpleNamespace(RUN=run, SLIDE=5 / 3, JUMP=20 / 3, POUNCE=35 / 3),
        acceleration_magnitude=100 * 60,
        color_str=color_str,
        game_view=view,
        scale=game.CHARACTER_SCALING if scale is None else scale,
    )
    cat.state.is_in_air = not on_ground
    if add:
        view.cats.append(cat)
        view.n_cats += 1
    return cat


def press(view, key, modifiers=0):
    view.on_key_press(key, modifiers)


def release(view, key, modifiers=0):
    view.on_key_release(key, modifiers)


def jump_to_apex(view):
    """Press and hold SPACE, then run frames until upward motion stops"""
    press(view, arcade.key.SPACE)
    for _ in range(200):
        view.on_update(DT)
        if view.player.change_y <= 0:
            return
    raise AssertionError("never reached apex")


h = SimpleNamespace(
    DT=DT,
    run_frames=run_frames,
    tick=tick,
    settle=settle,
    make_popsicle=make_popsicle,
    make_heart=make_heart,
    make_cat=make_cat,
    press=press,
    release=release,
    jump_to_apex=jump_to_apex,
    COMPETITOR_COLORS=COMPETITOR_COLORS,
)
