"""IceCreamTruck throw probabilities, thrown popsicles and idle shaking."""

import math

import game_constants as game
from helper import Vector
from sprites import HeartPopsicle, IceCreamTruck, RegularPopsicle

from tests.support import GameTestCase, approx


def _speed_angle(pop):
    return math.hypot(pop.change_x, pop.change_y), math.degrees(
        math.atan2(pop.change_y, -pop.change_x)
    )


def _make_truck():
    return IceCreamTruck(game.TRUCK_START_POS, scale=game.ICE_CREAM_TRUCK_SCALING)


class TestTruck(GameTestCase):
    def setUp(self):
        super().setUp()
        self.truck = _make_truck()

    def test_initial_state(self):
        truck = self.truck
        self.assertEqual(truck.position, tuple(game.TRUCK_START_POS))
        self.assertTrue(truck.throw_probability_frame == IceCreamTruck.THROW_PROBABILITY == 0.03)
        self.assertEqual(truck.color_pop_probs_dict, {c: 0.03 for c in game.COLORS})
        self.assertEqual(truck.heart_pop_prob, approx(0.03 * 0.005))

    def test_reset_throw_probabilities(self):
        truck = self.truck
        truck.throw_probability_frame = 1
        truck.color_pop_probs_dict["lime"] = 99
        truck.heart_pop_prob = 1
        truck.reset_throw_probabilities()
        self.assertEqual(truck.throw_probability_frame, 0.03)
        self.assertEqual(truck.color_pop_probs_dict, {c: 0.03 for c in game.COLORS})
        self.assertEqual(truck.heart_pop_prob, approx(0.00015))

    def test_no_throw_when_probabilities_zero(self):
        truck = self.truck
        truck.throw_probability_frame = 0
        truck.heart_pop_prob = 0
        self.assertTrue(all(truck.throw_popsicle() is None for _ in range(200)))

    def test_heart_throw(self):
        truck = self.truck
        truck.heart_pop_prob = 1.0
        for _ in range(50):
            truck.shaking_timer = 0
            heart = truck.throw_popsicle()
            self.assertIsInstance(heart, HeartPopsicle)
            self.assertEqual(heart.type, "heart")
            self.assertEqual(heart.position, truck.position)
            speed, angle = _speed_angle(heart)
            self.assertTrue(600 * 0.75 - 1e-6 <= speed <= 600 * 1.15 + 1e-6)
            self.assertTrue(75 - 1e-6 <= angle <= 105 + 1e-6)
            self.assertEqual(truck.shaking_timer, IceCreamTruck.SHAKE_PAUSE)

    def test_regular_throw(self):
        truck = self.truck
        truck.heart_pop_prob = 0
        truck.throw_probability_frame = 1.0
        for _ in range(50):
            truck.shaking_timer = 0
            pop = truck.throw_popsicle()
            self.assertIsInstance(pop, RegularPopsicle)
            self.assertEqual(pop.type, "regular")
            self.assertIn(pop.color_str, game.COLORS)
            self.assertEqual(pop.position, truck.position)
            speed, angle = _speed_angle(pop)
            self.assertTrue(600 * 0.25 - 1e-6 <= speed <= 600 + 1e-6)
            self.assertTrue(45 - 1e-6 <= angle <= 135 + 1e-6)
            self.assertEqual(truck.shaking_timer, IceCreamTruck.SHAKE_PAUSE)

    def test_color_weights_select_color(self):
        for color in sorted(game.COLORS):
            with self.subTest(color=color):
                self.isolate()
                truck = _make_truck()
                truck.heart_pop_prob = 0
                truck.throw_probability_frame = 1.0
                truck.color_pop_probs_dict = {c: (1.0 if c == color else 0.0) for c in game.COLORS}
                self.assertEqual({truck.throw_popsicle().color_str for _ in range(20)}, {color})

    def test_throw_rate_roughly_matches_probability(self):
        n = 4000
        thrown = sum(self.truck.throw_popsicle() is not None for _ in range(n))
        self.assertTrue(0.015 * n < thrown < 0.05 * n)

    def test_heavily_weighted_color_dominates(self):
        truck = self.truck
        truck.heart_pop_prob = 0
        truck.throw_probability_frame = 1.0
        truck.color_pop_probs_dict["lime"] *= 1000
        colors = [truck.throw_popsicle().color_str for _ in range(200)]
        self.assertGreater(colors.count("lime"), 190)

    def test_no_shake_while_paused_after_throw(self):
        truck = self.truck
        truck.shaking_timer = IceCreamTruck.SHAKE_PAUSE
        truck.angle = 5
        truck.update_animation(0.5)
        self.assertEqual(truck.angle, 0)

    def test_idle_shake_alternates_direction(self):
        truck = self.truck
        truck.shaking_timer = 0
        truck.angle = 0
        angles = []
        for _ in range(10):
            truck.update_animation(0.2)
            angles.append(truck.angle)
        self.assertTrue(all(0.5 <= abs(a) <= 3 for a in angles))
        self.assertTrue(all(a * b < 0 for a, b in zip(angles, angles[1:])))

    def test_shake_rate_limited(self):
        truck = self.truck
        truck.shaking_timer = 0
        truck.update_animation(0.2)
        first = truck.angle
        truck.update_animation(0.05)  # animation timer 0.05 * 10 <= 1: keep angle
        self.assertEqual(truck.angle, first)

    def test_truck_position_is_fixed(self):
        truck = self.truck
        truck.shaking_timer = 0
        for _ in range(30):
            truck.update_animation(1 / 60)
            truck.throw_popsicle()
        self.assertEqual(truck.position, Vector(750, 305))
