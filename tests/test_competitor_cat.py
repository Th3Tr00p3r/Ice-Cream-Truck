"""CompetitorCat AI: gravity, returning, begging, fetching popsicles, animation, poof."""

import unittest

import game_constants as game
from sprites import CompetitorCat

from tests.support import GameViewTestCase, approx, h

DT = 1 / 60


class TestCompetitorColors(unittest.TestCase):
    def test_competitor_colors_exclude_player_colors(self):
        self.assertEqual(set(CompetitorCat.color_textures_dict), game.COLORS - game.PLAYER_COLORS)


class TestCompetitorCat(GameViewTestCase):
    def test_initial_state(self):
        cat = h.make_cat(self.game_view, 300, 400, color_str="pink", add=False)
        self.assertTrue(cat.lives == CompetitorCat.MAX_LIVES == 1)
        self.assertEqual(cat.mode, "returning")
        self.assertTrue(cat.state.is_in_air)
        self.assertIsNone(cat.sought_popsicle)
        self.assertEqual(cat.color_str, "pink")
        self.assertEqual(cat.face_direction, game.FACE_RIGHT)

    def test_gravity_while_in_air(self):
        cat = h.make_cat(self.game_view, 300, 400, add=False)
        cat.change_y = 60
        cat.seek(0.5)
        self.assertEqual(cat.center_y, approx(430))
        self.assertEqual(cat.change_y, 60 - game.GRAVITY * 10)
        cat.seek(0.5)
        self.assertEqual(cat.center_y, approx(455))

    def test_on_ground_height_is_fixed(self):
        cat = h.make_cat(self.game_view, 300, 400, on_ground=True, add=False)
        cat.change_y = -40
        cat.seek(DT)
        y = cat.center_y
        self.assertEqual(cat.change_y, 0)
        for _ in range(5):
            cat.seek(DT)
            self.assertEqual(cat.center_y, y)
        self.assertLess(cat.bottom, self.game_view.ground_height + 20)

    def test_returns_towards_truck(self):
        for x, direction in [(100, 1), (1500, -1)]:
            with self.subTest(x=x, direction=direction):
                self.isolate()
                game_view = self.make_game_view()
                cat = h.make_cat(game_view, x, 300, on_ground=True, add=False, run=100)
                cat.seek(DT)
                self.assertEqual(cat.mode, "returning")
                self.assertGreater(cat.change_x * direction, 0)
                for _ in range(80):
                    cat.seek(DT)
                self.assertEqual(cat.change_x, direction * 100)  # capped at the run speed
                self.assertGreater((cat.center_x - x) * direction, 0)

    def test_returning_accelerates_like_fetching(self):
        returning = h.make_cat(self.game_view, 100, 300, on_ground=True, add=False, run=1000)
        fetching = h.make_cat(self.game_view, 100, 300, "pink", on_ground=True, add=False, run=1000)
        h.make_popsicle(self.game_view, "pink", 1000, 300)
        returning.seek(DT)
        fetching.seek(DT)
        self.assertEqual((returning.mode, fetching.mode), ("returning", "fetching"))
        self.assertEqual(returning.change_x, approx(fetching.change_x))
        self.assertEqual(returning.change_x, approx(100 * 60 * DT))

    def test_begs_at_truck_when_slow(self):
        truck = self.game_view.ice_cream_truck
        cat = h.make_cat(self.game_view, truck.center_x + 50, 300, on_ground=True, add=False)
        cat.seek(DT)
        self.assertEqual(cat.mode, "begging")
        self.assertEqual(cat.change_x, 0)
        x = cat.center_x
        for _ in range(10):
            cat.seek(DT)
        self.assertEqual(cat.mode, "begging")
        self.assertEqual(cat.center_x, x)

    def test_fast_cat_does_not_beg_from_either_side(self):
        truck = self.game_view.ice_cream_truck
        for side in (-1, 1):
            with self.subTest(side=side):
                cat = h.make_cat(self.game_view, truck.center_x + side * 50, 300, on_ground=True)
                cat.change_x = -side * 100
                cat.seek(DT)
                self.assertEqual(cat.mode, "returning")
                self.assertNotEqual(cat.change_x, 0)

    def test_fetches_own_color_popsicle(self):
        game_view = self.game_view
        cat = h.make_cat(game_view, 400, 300, color_str="lime", on_ground=True, add=False, run=150)
        h.make_popsicle(game_view, "pink", 1000, 300)
        cat.seek(DT)
        self.assertEqual(cat.mode, "returning")  # other colours are ignored
        pop = h.make_popsicle(game_view, "lime", 1000, 300)
        cat.seek(DT)
        self.assertEqual(cat.mode, "fetching")
        self.assertIs(cat.sought_popsicle, pop)
        self.assertGreater(cat.change_x, 50)  # accelerates much harder than when returning
        for _ in range(3):
            cat.seek(DT)
        self.assertEqual(cat.change_x, 150)

    def test_fetches_nearest_own_color_popsicle(self):
        cat = h.make_cat(self.game_view, 400, 300, color_str="lime", on_ground=True, add=False)
        h.make_popsicle(self.game_view, "lime", 1400, 300)
        near = h.make_popsicle(self.game_view, "lime", 600, 300)
        cat.seek(DT)
        self.assertIs(cat.sought_popsicle, near)

    def test_retargets_when_popsicle_melts_away(self):
        cat = h.make_cat(self.game_view, 400, 300, color_str="lime", on_ground=True, add=False)
        melting = h.make_popsicle(self.game_view, "lime", 600, 300)
        other = h.make_popsicle(self.game_view, "lime", 1400, 300)
        cat.seek(DT)
        self.assertIs(cat.sought_popsicle, melting)
        while melting in self.game_view.popsicles:
            melting.melt(0.25)
        cat.seek(DT)
        self.assertIs(cat.sought_popsicle, other)

    def test_fetch_towards_left(self):
        cat = h.make_cat(self.game_view, 1400, 300, color_str="lime", on_ground=True, add=False)
        h.make_popsicle(self.game_view, "lime", 200, 300)
        for _ in range(3):
            cat.seek(DT)
        self.assertLess(cat.change_x, 0)
        self.assertEqual(cat.mode, "fetching")

    def test_retargets_when_popsicle_gone(self):
        game_view = self.game_view
        cat = h.make_cat(game_view, 400, 300, color_str="lime", on_ground=True, add=False)
        first = h.make_popsicle(game_view, "lime", 1000, 300)
        cat.seek(DT)
        self.assertIs(cat.sought_popsicle, first)
        first.is_off_screen = True
        first.remove_from_sprite_lists()
        second = h.make_popsicle(game_view, "lime", 200, 300)
        cat.seek(DT)
        self.assertIs(cat.sought_popsicle, second)
        first.is_off_screen = False
        cat.sought_popsicle = None
        first.remove_from_sprite_lists()
        second.remove_from_sprite_lists()
        cat.seek(DT)
        self.assertEqual(cat.mode, "returning")
        self.assertIsNone(cat.sought_popsicle)

    def test_poof(self):
        cat = h.make_cat(self.game_view, 300, 300, color_str="white", scale=2.0, add=False)
        poof = cat.poof()
        self.assertEqual(poof.center_x, 300)
        self.assertEqual(poof.center_y, approx(300 - cat.height / 3))
        # drawn at 0.3x the cat's scale of the 400px frames, whatever size they're stored at
        self.assertEqual(poof.scale_x * poof.loaded_textures[0].width, approx(400 * 0.3 * 2.0))
        other = cat.poof()
        self.assertIsNot(other, poof)  # a new poof per kill
        self.assertEqual(poof.center_x, 300)
        self.assertIs(other.loaded_textures[0], poof.loaded_textures[0])  # textures are shared


class TestAnimation(GameViewTestCase):
    def test_running_on_ground(self):
        cat = h.make_cat(self.game_view, 200, 300, on_ground=True, add=False)
        for _ in range(3):
            cat.seek(DT)
            cat.update_animation(DT)
        self.assertEqual(cat.texture_type, "running")

    def test_begging(self):
        truck = self.game_view.ice_cream_truck
        cat = h.make_cat(self.game_view, truck.center_x, 300, on_ground=True, add=False)
        cat.seek(DT)
        cat.update_animation(DT)
        self.assertEqual(cat.texture_type, "begging")

    def test_falling(self):
        cat = h.make_cat(self.game_view, 200, 500, add=False)
        cat.change_y = -20
        cat.update_animation(DT)
        self.assertEqual(cat.texture_type, "falling")

    def test_facing_follows_acceleration_rate_limited(self):
        cat = h.make_cat(self.game_view, 1500, 300, on_ground=True, add=False)
        cat.seek(DT)
        cat.update_animation(0.1)
        self.assertFalse(cat.state.is_facing_left)  # not yet: face switch needs > 0.5s
        cat.update_animation(0.5)
        self.assertTrue(cat.state.is_facing_left)
        self.assertEqual(cat.move_state, -1)
