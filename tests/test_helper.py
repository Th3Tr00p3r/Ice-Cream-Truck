"""Unit tests for helper.py utilities and game_constants."""

import math
import unittest

import arcade
import game_constants as game
import numpy as np
import PIL.Image
from helper import (
    Limits,
    ScreenProps,
    Vector,
    can_float,
    crop_resize_concat_horizontally,
    generate_numbers_from_string,
    get_aura_image,
    number,
    tint_greyscale_pixels,
)


class TestLimits(unittest.TestCase):
    def test_default_is_unbounded(self):
        lim = Limits()
        self.assertEqual(lim.lower, -math.inf)
        self.assertEqual(lim.upper, math.inf)

    def test_construction_forms(self):
        cases = [(((1, 5),), (1, 5)), ((3,), (3, math.inf)), ((3, 7), (3, 7)), (([2, 4],), (2, 4))]
        for args, expected in cases:
            with self.subTest(args=args):
                self.assertEqual(tuple(Limits(*args)), expected)

    def test_from_string(self):
        self.assertEqual(Limits("between -2.5 and 10", from_string=True), (-2.5, 10))

    def test_three_iterable_raises(self):
        with self.assertRaises(TypeError):
            Limits((1, 2, 3))

    def test_none_lower(self):
        lim = Limits(None)
        self.assertIsNone(lim.lower)
        self.assertEqual(lim.upper, math.inf)

    def test_call_reinitialises(self):
        lim = Limits(1, 2)
        lim(5, 6)
        self.assertEqual(lim, (5, 6))

    def test_sequence_protocol(self):
        lim = Limits(1, 5)
        self.assertEqual(list(lim), [1, 5])
        self.assertEqual(lim[0], 1)
        self.assertEqual(lim[1], 5)
        self.assertEqual(lim[-1], 5)
        self.assertEqual(len(lim), 2)

    def test_equality(self):
        self.assertEqual(Limits(1, 5), (1, 5))
        self.assertEqual(Limits(1, 5), Limits(1, 5))
        self.assertNotEqual(Limits(1, 5), (1, 6))

    def test_repr_and_str(self):
        self.assertEqual(repr(Limits(1, 5)), "Limits(lower=1, upper=5)")
        self.assertEqual(str(Limits(1.0, 5.5)), "(1, 5.50)")
        self.assertEqual(str(Limits(1e3, 2.25)), "(1000, 2.25)")
        self.assertEqual(str(Limits()), "(-inf, inf)")

    def test_intersection(self):
        self.assertEqual(Limits(0, 10) & Limits(5, 20), (5, 10))
        self.assertEqual(Limits(0, 10) & None, (0, 10))

    def test_comparisons(self):
        lim = Limits(1, 5)
        self.assertGreater(lim, 0)
        self.assertFalse(lim > 1)
        self.assertLess(lim, 6)
        self.assertFalse(lim < 5)
        self.assertGreater(lim, Limits(-3, 0))
        self.assertLess(lim, Limits(6, 9))

    def test_contains(self):
        lim = Limits(1, 5)
        self.assertIn(3, lim)
        self.assertIn(1, lim)
        self.assertIn(5, lim)
        self.assertNotIn(0, lim)
        self.assertNotIn(5.1, lim)
        self.assertIn((2, 4), lim)
        self.assertIn(Limits(1, 5), lim)
        self.assertNotIn((0, 4), lim)
        self.assertNotIn(None, lim)

    def test_valid_indices(self):
        arr = np.array([0, 1, 3, 5, 6])
        lim = Limits(1, 5)
        self.assertEqual(lim.valid_indices(arr).tolist(), [False, True, True, True, False])
        self.assertEqual(lim.valid_indices(arr, as_bool=False).tolist(), [1, 2, 3])
        with self.assertRaises(TypeError):
            lim.valid_indices([1, 2])

    def test_as_dict(self):
        self.assertEqual(Limits(1, 5).as_dict(), {"lower": 1, "upper": 5})
        self.assertEqual(Limits(1, 5, dict_labels=("lo", "hi")).as_dict(), {"lo": 1, "hi": 5})

    def test_interval_center_range(self):
        lim = Limits(2, 6)
        self.assertEqual(lim.interval(), 4)
        self.assertEqual(lim.center(), 4)
        self.assertEqual(list(lim.as_range()), [2, 3, 4, 5])

    def test_clamp(self):
        lim = Limits(-10, 10)
        self.assertEqual(lim.clamp(15), 10)
        self.assertEqual(lim.clamp(-15.5), -10)
        self.assertEqual(lim.clamp(3.5), 3.5)
        self.assertEqual(lim.clamp(Limits(-20, 5)), (-10, 5))
        with self.assertRaises(TypeError):
            lim.clamp("5")


class TestNumberParsing(unittest.TestCase):
    def test_can_float(self):
        cases = [("1.5", True), ("-", True), ("3", True), ("a", False), (None, False)]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertIs(can_float(value), expected)

    def test_number(self):
        self.assertEqual(number("3"), 3)
        self.assertIsInstance(number("3"), int)
        self.assertEqual(number("3.5"), 3.5)
        self.assertEqual(number(math.inf), math.inf)

    def test_generate_numbers_from_string(self):
        self.assertEqual(list(generate_numbers_from_string("x=12, y=-3.5; z 7")), [12, -3.5, 7])
        self.assertEqual(list(generate_numbers_from_string("no numbers")), [])


class TestVector(unittest.TestCase):
    def test_basics(self):
        v = Vector(1, 2)
        self.assertEqual((v.x, v.y), (1, 2))
        self.assertEqual(tuple(v), (1, 2))
        self.assertEqual(v[0], 1)
        self.assertEqual(v[1], 2)
        self.assertEqual(len(v), 2)

    def test_setitem(self):
        v = Vector(1, 2)
        v[0] = 5
        v[-1] = 7
        self.assertEqual((v.x, v.y), (5, 7))
        with self.assertRaises(IndexError):
            v[2] = 0

    def test_arithmetic(self):
        self.assertEqual(Vector(1, 2) + Vector(3, 4), Vector(4, 6))
        self.assertEqual(Vector(1, 2) + (1, 1), (2, 3))
        self.assertEqual(Vector(5, 5) - Vector(1, 2), Vector(4, 3))
        with self.assertRaises(TypeError):
            Vector(1, 2) + 3
        with self.assertRaises(TypeError):
            Vector(1, 2) - 3

    def test_equality(self):
        self.assertEqual(Vector(1, 2), (1, 2))
        self.assertNotEqual(Vector(1, 2), Vector(2, 1))
        with self.assertRaises(TypeError):
            Vector(1, 2) == 5  # noqa: B015

    def test_call_reinitialises(self):
        v = Vector(1, 2)
        v(7, 8)
        self.assertEqual(v, (7, 8))


class TestScreenProps(unittest.TestCase):
    def test_screen_props(self):
        props = ScreenProps(1600, 800)
        self.assertEqual(props.center_x, 800)
        self.assertEqual(props.center_y, 400)
        self.assertEqual(
            props.as_dict(), {"width": 1600, "height": 800, "center_x": 800, "center_y": 400}
        )


class TestImageHelpers(unittest.TestCase):
    @staticmethod
    def _img(pixels):
        return PIL.Image.fromarray(np.array(pixels, dtype=np.uint8), "RGBA")

    def test_tint_dark_grey_only_by_default(self):
        img = self._img([[(50, 50, 50, 255), (255, 255, 255, 255), (200, 0, 0, 128)]])
        out = np.array(tint_greyscale_pixels(img, "red"))
        self.assertEqual(out.shape, (1, 3, 4))
        self.assertEqual(tuple(out[0, 0]), (255, 0, 0, 255))  # dark grey -> tinted
        self.assertEqual(tuple(out[0, 1]), (255, 255, 255, 255))  # light grey untouched
        self.assertEqual(tuple(out[0, 2]), (200, 0, 0, 128))  # coloured untouched

    def test_tint_light_grey(self):
        img = self._img([[(50, 50, 50, 255), (255, 255, 255, 200)]])
        out = np.array(
            tint_greyscale_pixels(img, "#204080", should_tint_black=False, linear_beta=(0, 1))
        )
        self.assertEqual(tuple(out[0, 0]), (50, 50, 50, 255))
        self.assertEqual(tuple(out[0, 1]), (0x20, 0x40, 0x80, 200))

    def test_tint_does_not_mutate_input(self):
        img = self._img([[(50, 50, 50, 255)]])
        tint_greyscale_pixels(img, "blue")
        self.assertEqual(img.getpixel((0, 0)), (50, 50, 50, 255))

    def test_aura(self):
        arr = np.zeros((21, 21, 4), dtype=np.uint8)
        arr[9:12, 9:12] = (10, 200, 10, 255)
        out = np.array(get_aura_image(PIL.Image.fromarray(arr, "RGBA"), "red", thickness=3))
        self.assertEqual(out.shape, arr.shape)
        self.assertEqual(tuple(out[10, 10]), (10, 200, 10, 255))  # original pixels kept on top
        self.assertEqual(tuple(out[10, 14]), (255, 0, 0, 255))  # 3px aura (8-connected dilation)
        self.assertEqual(tuple(out[6, 6]), (255, 0, 0, 255))
        self.assertEqual(out[10, 15, 3], 0)
        self.assertEqual(out[5, 5, 3], 0)  # nothing beyond thickness
        self.assertEqual((out[..., 3] > 0).sum(), 9 * 9)

    def test_crop_resize_concat(self):
        a = PIL.Image.new("RGBA", (30, 30))
        a.paste((255, 0, 0, 255), (0, 0, 10, 10))
        b = PIL.Image.new("RGBA", (40, 40))
        b.paste((0, 0, 255, 255), (5, 5, 25, 25))
        out = crop_resize_concat_horizontally([a, b])
        self.assertEqual(out.size, (20, 10))
        self.assertEqual(out.getpixel((2, 2)), (255, 0, 0, 255))
        self.assertEqual(out.getpixel((15, 5)), (0, 0, 255, 255))


class TestGameConstants(unittest.TestCase):
    def test_key_str_dict_maps_letters(self):
        self.assertEqual(game.KEY_STR_DICT[arcade.key.A], "A")
        self.assertEqual(game.KEY_STR_DICT[arcade.key.Z], "Z")
        self.assertEqual(len(game.KEY_STR_DICT), 26)

    def test_any_key(self):
        for key in (arcade.key.A, arcade.key.ENTER, arcade.key.ESCAPE, arcade.key.SPACE):
            self.assertIn(key, game.ANY_KEY)

    def test_colors(self):
        self.assertEqual(game.PLAYER_COLORS, {"deepskyblue", "crimson", "gold"})
        self.assertLess(game.PLAYER_COLORS, game.COLORS)
        self.assertEqual(len(game.COLORS), 8)

    def test_screen_and_physics(self):
        self.assertEqual((game.SCREEN_PROPS.width, game.SCREEN_PROPS.height), (1600, 800))
        self.assertEqual(game.GRAVITY, 1.0)
        self.assertEqual(game.FRICTION, 0.9)
        self.assertEqual(game.N_JUMPS, 2)
        self.assertEqual(game.PLAYER_START_POS, (100, 450))
        self.assertEqual(game.TRUCK_START_POS, (750, 305))
