"""Popsicle physics, melting/point values, and screen-edge handling."""

import math

import arcade
import game_constants as game
from helper import Vector
from sprites import HeartPopsicle, Popsicle, RegularPopsicle

from tests.support import GameTestCase, approx


def _pop(color="lime", pos=(800, 400), speed=100, angle=90):
    return RegularPopsicle(color, Vector(*pos), speed, angle)


class TestThrowKinematics(GameTestCase):
    def test_initial_velocity_from_speed_and_angle(self):
        for angle in [45, 60, 90, 120, 135]:
            with self.subTest(angle=angle):
                pop = _pop(speed=400, angle=angle)
                self.assertEqual(pop.change_x, approx(-400 * math.cos(math.radians(angle))))
                self.assertEqual(pop.change_y, approx(400 * math.sin(math.radians(angle))))

    def test_spin_direction_follows_horizontal_direction(self):
        self.assertEqual(_pop(speed=300, angle=45).change_angle, 300)  # thrown left
        self.assertEqual(_pop(speed=300, angle=135).change_angle, -300)  # thrown right

    def test_move_applies_gravity_and_velocity(self):
        pop = _pop(speed=0, angle=90)
        pop.change_x = 60
        pop.change_angle = 30
        pop.move(0.5)
        self.assertEqual(pop.change_y, approx(-game.GRAVITY * 250 * 0.5))
        self.assertEqual(pop.center_x, approx(830))
        self.assertEqual(pop.center_y, approx(400 - 125 * 0.5))
        self.assertEqual(pop.angle, approx(15))

    def test_no_gravity_when_on_ground(self):
        pop = _pop(speed=0)
        pop.is_on_ground = True
        pop.move(1.0)
        self.assertEqual(pop.change_y, 0)
        self.assertEqual(pop.center_y, 400)

    def test_bounce_reverses_and_damps_fall(self):
        pop = _pop()
        for _ in range(20):
            pop.change_y = -100
            pop.bounce()
            self.assertTrue(30 <= pop.change_y <= 50)
            self.assertFalse(pop.is_on_ground)

    def test_bounce_when_barely_falling_lands_and_stops(self):
        pop = _pop(speed=300, angle=45)
        pop.angle = 42
        pop.change_y = -0.0005
        pop.bounce()
        self.assertTrue(pop.is_on_ground)
        self.assertEqual((pop.change_x, pop.change_y, pop.change_angle, pop.angle), (0, 0, 0, 0))

    def test_stop_keeps_vertical_speed_if_asked(self):
        pop = _pop(speed=300, angle=45)
        vy = pop.change_y
        pop.stop(should_stop_y=False)
        self.assertEqual(pop.change_x, 0)
        self.assertEqual(pop.change_y, vy)
        self.assertEqual(pop.change_angle, 0)


class TestPopsicleTypes(GameTestCase):
    def test_regular(self):
        pop = _pop(color="pink")
        self.assertEqual(pop.type, "regular")
        self.assertEqual(pop.color_str, "pink")
        self.assertTrue(pop.point_value == RegularPopsicle.BASE_POINTS == 10)
        self.assertFalse(pop.is_on_ground)
        self.assertFalse(pop.is_off_screen)
        self.assertIs(pop.texture, pop.loaded_textures.standing)

    def test_every_color_has_textures(self):
        for color in sorted(game.COLORS):
            with self.subTest(color=color):
                pop = _pop(color=color)
                self.assertEqual(len(pop.loaded_textures.melting), 10)

    def test_heart(self):
        heart = HeartPopsicle(Vector(10, 20), 100, 90)
        self.assertEqual(heart.type, "heart")
        self.assertEqual(heart.point_value, 100)
        self.assertIsNone(heart.color_str)
        self.assertIsInstance(heart, Popsicle)


class TestMelting(GameTestCase):
    def test_melt_schedule_and_points(self):
        pop = _pop()
        sprites = arcade.SpriteList()
        sprites.append(pop)
        # frozen: nothing changes until frozen for more than FROZEN_TIME (1s)
        for _ in range(5):
            pop.melt(0.25)
            self.assertEqual(pop.point_value, 10)
            self.assertIs(pop.texture, pop.loaded_textures.standing)
        # then loses 1 point per melt step (every > 0.2s), cycling through 10 melt textures
        for step in range(10):
            pop.melt(0.25)
            self.assertEqual(pop.point_value, 9 - step)
            self.assertIs(pop.texture, pop.loaded_textures.melting[step])
            self.assertIn(pop, sprites)
        pop.melt(0.25)
        self.assertNotIn(pop, sprites)
        self.assertEqual(pop.point_value, 0)

    def test_melt_needs_time_between_steps(self):
        pop = _pop()
        pop.melt(1.5)  # frozen
        pop.melt(0.1)
        self.assertEqual(pop.point_value, 10)
        pop.melt(0.15)
        self.assertEqual(pop.point_value, 9)


class TestRestrictPosition(GameTestCase):
    def test_kill_when_leaving_map(self):
        cases = [("left", -5), ("right", game.SCREEN_PROPS.width + 5), ("bottom", -1)]
        for attr, value in cases:
            with self.subTest(attr=attr, value=value):
                self.isolate()
                pop = _pop()
                sprites = arcade.SpriteList()
                sprites.append(pop)
                setattr(pop, attr, value)
                pop.restrict_position(game.SCREEN_PROPS.width, should_kill=True)
                self.assertNotIn(pop, sprites)
                self.assertTrue(pop.is_off_screen)

    def test_clamp_without_kill(self):
        pop = _pop()
        pop.left = -5
        pop.restrict_position(1000)
        self.assertEqual(pop.left, approx(0))
        self.assertFalse(pop.is_off_screen)
        pop.right = 1200
        pop.restrict_position(1000)
        self.assertEqual(pop.right, approx(1000))
        pop.bottom = -10
        pop.restrict_position(1000)
        self.assertEqual(pop.bottom, approx(0))

    def test_inside_is_untouched(self):
        pop = _pop()
        pop.restrict_position(game.SCREEN_PROPS.width, should_kill=True)
        self.assertEqual(pop.position, (800, 400))
        self.assertFalse(pop.is_off_screen)
