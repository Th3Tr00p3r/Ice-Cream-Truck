"""PlayerCat state logic: stats, running, friction, jumping, pounce, air-dash, drop, hits, kills."""

import unittest

import arcade
import game_constants as game
from sprites import BlueCat, PlayerCat, RedCat, YellowCat

from tests.support import GameViewTestCase, approx, h

K = arcade.key


def _switch_to(view, cls):
    """Press Z (respecting the switch cooldown) until the player is of the given class"""
    for _ in range(3):
        if isinstance(view.player, cls):
            return view.player
        h.press(view, K.Z)
        h.run_frames(view, 1, dt=0.31)
    if not isinstance(view.player, cls):
        raise AssertionError(f"could not switch to {cls.__name__}")
    return view.player


def _run_to_full_speed(view, key=K.RIGHT):
    h.press(view, key)
    for _ in range(60):
        view.on_update(h.DT)
        if abs(view.player.change_x) == view.player.speeds.RUN:
            return
    raise AssertionError("never reached full speed")


class TestStats(GameViewTestCase):
    def test_cat_stats(self):
        cases = [
            (BlueCat, "deepskyblue", 3, (10, 5, 20, 35), 45, 1.5),
            (RedCat, "crimson", 2, (12, 6, 24, 42), 54, 1.35),
            (YellowCat, "gold", 4, (8, 4, 16, 28), 36, 1.65),
        ]
        for cls, color, lives, speeds, accel, scale in cases:
            with self.subTest(cls=cls.__name__):
                self.isolate()
                game_view = self.make_game_view()
                cat = game_view.player_color_cat_dict[color]
                self.assertIsInstance(cat, cls)
                self.assertEqual(cat.color_str, color)
                self.assertEqual(cat.lives, lives)
                self.assertTrue(cat.is_alive)
                s = cat.speeds
                self.assertEqual((s.RUN, s.SLIDE, s.JUMP, s.POUNCE), speeds)
                self.assertEqual(cat.acceleration_magnitude, approx(accel))
                self.assertEqual(cat.scale_x, approx(scale))

    def test_abilities(self):
        blue, red, yellow = (
            self.game_view.player_color_cat_dict[c] for c in ("deepskyblue", "crimson", "gold")
        )
        self.assertTrue(blue.can_pounce_kill)
        self.assertFalse(blue.can_swipe)
        self.assertTrue(yellow.can_swipe)
        self.assertFalse(yellow.can_pounce_kill)
        self.assertFalse(red.can_pounce_kill)
        self.assertFalse(red.can_swipe)
        self.assertTrue(hasattr(red, "air_dash"))
        self.assertFalse(hasattr(blue, "air_dash"))
        self.assertTrue(hasattr(yellow, "drop"))
        self.assertFalse(hasattr(red, "drop"))


class TestClassConstants(unittest.TestCase):
    def test_class_constants(self):
        self.assertEqual(PlayerCat.MAX_LIVES, 5)
        self.assertEqual(PlayerCat.N_REQUIRED_FOR_SUPERPOWER, 25)
        self.assertEqual(PlayerCat.INVULNERABILITY_DURATION_s, 1.5)
        self.assertEqual(
            (PlayerCat.POUNCE_RECOV, RedCat.POUNCE_RECOV, YellowCat.POUNCE_RECOV), (50, 40, 60)
        )


class TestRunning(GameViewTestCase):
    def test_idle_on_ground(self):
        p = self.game_view.player
        self.assertEqual(p.center_x, 100)
        self.assertGreaterEqual(p.bottom, self.game_view.ground_height - 1)
        self.assertEqual(p.texture_type, "standing")
        self.assertEqual(p.move_state, game.STOP)

    def test_accelerates_to_run_speed(self):
        game_view = self.game_view
        p = game_view.player
        h.press(game_view, K.RIGHT)
        self.assertEqual(p.move_state, game.RIGHT)
        speeds = []
        for _ in range(16):
            game_view.on_update(h.DT)
            speeds.append(p.change_x)
        self.assertEqual(speeds[0], approx(0.75))
        self.assertEqual(speeds[:14], approx([0.75 * i for i in range(1, 14)] + [10]))
        self.assertEqual(speeds[-1], 10)
        self.assertGreater(p.center_x, 150)
        self.assertEqual(p.texture_type, "running")
        self.assertEqual(p.face_direction, game.FACE_RIGHT)
        self.assertEqual(p.state.is_facing_left, 0)

    def test_run_left_faces_left(self):
        p = self.game_view.player
        p.center_x = 800
        _run_to_full_speed(self.game_view, K.LEFT)
        self.assertEqual(p.change_x, -10)
        self.assertEqual(p.face_direction, game.FACE_LEFT)
        self.assertEqual(p.state.is_facing_left, 1)
        self.assertLess(p.center_x, 800)

    def test_friction_stops_after_release(self):
        game_view = self.game_view
        p = game_view.player
        _run_to_full_speed(game_view)
        h.release(game_view, K.RIGHT)
        textures = set()
        for _ in range(40):
            game_view.on_update(h.DT)
            textures.add(p.texture_type)
        self.assertEqual(p.change_x, 0)
        self.assertIn("sliding", textures)
        self.assertEqual(p.texture_type, "standing")
        self.assertTrue(p.state.was_moving_right)

    def test_both_keys_last_pressed_wins(self):
        game_view = self.game_view
        p = game_view.player
        p.center_x = 800
        h.press(game_view, K.LEFT)
        h.press(game_view, K.RIGHT)
        self.assertEqual(p.move_state, game.RIGHT)
        h.release(game_view, K.RIGHT)
        h.run_frames(game_view, 1)
        self.assertEqual(p.move_state, game.LEFT)
        h.press(game_view, K.RIGHT)
        h.press(game_view, K.LEFT)
        self.assertEqual(p.move_state, game.LEFT)

    def test_key_release_tracking(self):
        game_view = self.game_view
        h.press(game_view, K.RIGHT)
        self.assertTrue(game_view.keys_pressed[K.RIGHT])
        self.assertEqual(game_view.keys_pressed["LAST"], K.RIGHT)
        h.release(game_view, K.RIGHT)
        self.assertFalse(game_view.keys_pressed[K.RIGHT])
        self.assertEqual(game_view.keys_pressed["LAST"], K.RIGHT)
        h.release(game_view, K.A)  # untracked keys are ignored
        self.assertNotIn(K.A, game_view.keys_pressed)

    def test_stays_inside_map(self):
        game_view = self.game_view
        p = game_view.player
        p.center_x = 1500
        _run_to_full_speed(game_view)
        h.run_frames(game_view, 8)
        self.assertEqual(p.right, approx(game_view.map_width))
        h.release(game_view, K.RIGHT)
        p.center_x = 100
        h.press(game_view, K.LEFT)
        h.run_frames(game_view, 45)
        self.assertEqual(p.left, approx(0))


class TestJumping(GameViewTestCase):
    def test_jump_from_ground(self):
        game_view = self.game_view
        p = game_view.player
        n_sounds = len(self.sounds)
        h.press(game_view, K.SPACE)
        self.assertEqual(p.change_y, p.speeds.JUMP)
        self.assertEqual(game_view.physics_engine.jumps_since_ground, 1)
        self.assertEqual(len(self.sounds), n_sounds + 1)
        h.run_frames(game_view, 2)
        self.assertTrue(p.state.is_in_air)
        self.assertTrue(p.state.jump.is_jumping)
        self.assertEqual(p.texture_type, "jumping")

    def test_holding_space_jumps_higher(self):
        game_view = self.game_view
        p = game_view.player
        start = p.center_y
        h.jump_to_apex(game_view)
        held_apex = p.center_y - start
        h.settle(game_view)
        h.release(game_view, K.SPACE)
        h.press(game_view, K.SPACE)
        h.release(game_view, K.SPACE)
        apex = 0
        for _ in range(60):
            game_view.on_update(h.DT)
            apex = max(apex, p.center_y - start)
        self.assertGreater(held_apex, apex * 1.3)

    def test_double_jump_then_no_more(self):
        game_view = self.game_view
        p = game_view.player
        h.jump_to_apex(game_view)
        first_apex = p.center_y
        h.press(game_view, K.SPACE)
        self.assertEqual(game_view.physics_engine.jumps_since_ground, 2)
        vy = p.change_y
        h.press(game_view, K.SPACE)  # third jump is ignored for BlueCat
        self.assertEqual(p.change_y, vy)
        self.assertEqual(game_view.physics_engine.jumps_since_ground, 2)
        h.run_frames(game_view, 5)
        self.assertNotEqual(p.angle, 0)  # double-jump spin
        for _ in range(60):
            game_view.on_update(h.DT)
            if p.change_y <= 0:
                break
        self.assertGreater(p.center_y, first_apex + 100)

    def test_lands_back_on_ground(self):
        game_view = self.game_view
        p = game_view.player
        ground_y = p.center_y
        h.jump_to_apex(game_view)
        h.release(game_view, K.SPACE)
        h.settle(game_view)
        self.assertEqual(p.center_y, approx(ground_y, abs=1))
        self.assertFalse(p.state.is_in_air)
        self.assertEqual(game_view.physics_engine.jumps_since_ground, 0)
        self.assertEqual(p.angle, 0)

    def test_fall_textures(self):
        game_view = self.game_view
        p = game_view.player
        h.jump_to_apex(game_view)
        seen = []
        for _ in range(60):
            game_view.on_update(h.DT)
            seen.append(p.texture_type)
        self.assertIn("stalling", seen)
        self.assertIn("falling", seen)


class TestPounce(GameViewTestCase):
    def test_can_pounce_only_at_full_speed_on_ground(self):
        game_view = self.game_view
        p = game_view.player
        h.press(game_view, K.RIGHT)
        h.run_frames(game_view, 5)
        self.assertFalse(p.state.pounce.can_pounce)
        _run_to_full_speed(game_view)
        h.run_frames(game_view, 1)
        self.assertTrue(p.state.pounce.can_pounce)
        h.press(game_view, K.SPACE)
        h.run_frames(game_view, 1)
        self.assertFalse(p.state.pounce.can_pounce)

    def test_not_near_edge(self):
        game_view = self.game_view
        p = game_view.player
        p.center_x = 1450
        _run_to_full_speed(game_view)
        h.run_frames(game_view, 20)
        self.assertTrue(p.state.is_near_edge)
        self.assertFalse(p.state.pounce.can_pounce)

    def test_blue_pounce(self):
        game_view = self.game_view
        p = game_view.player
        _run_to_full_speed(game_view)
        h.run_frames(game_view, 1)
        h.press(game_view, K.DOWN)
        self.assertTrue(p.state.pounce.is_pouncing)
        self.assertEqual(p.state.pounce.recovery_timer, p.POUNCE_RECOV - 0)
        self.assertEqual(p.pounce_timer, p.POUNCE_DURATION)
        x0 = p.center_x
        h.run_frames(game_view, 1)
        self.assertEqual(p.change_x, p.speeds.POUNCE)
        self.assertEqual(p.texture_type, "scratching")
        h.run_frames(game_view, 5)
        self.assertGreaterEqual(p.center_x - x0, 5 * p.speeds.POUNCE)
        for _ in range(100):
            game_view.on_update(h.DT)
            if not p.state.pounce.is_pouncing:
                break
        self.assertFalse(p.state.pounce.is_pouncing)
        self.assertGreater(p.state.pounce.recovery_timer, 0)
        # during recovery the running speed is capped at a third
        h.run_frames(game_view, 30)
        self.assertEqual(p.max_run_speed, approx(p.speeds.RUN / 3))
        self.assertFalse(p.state.pounce.can_pounce)

    def test_pounce_is_not_possible_again_until_recovered(self):
        game_view = self.game_view
        p = game_view.player
        _run_to_full_speed(game_view)
        h.run_frames(game_view, 1)
        h.press(game_view, K.DOWN)
        h.run_frames(game_view, 55)
        self.assertEqual(p.state.pounce.recovery_timer, 0)
        self.assertEqual(p.max_run_speed, p.speeds.RUN)

    def test_red_pounce_texture(self):
        game_view = self.game_view
        red = _switch_to(game_view, RedCat)
        h.settle(game_view)
        _run_to_full_speed(game_view)
        h.run_frames(game_view, 1)
        h.press(game_view, K.DOWN)
        h.run_frames(game_view, 1)
        self.assertTrue(red.state.pounce.is_pouncing)
        self.assertEqual(red.change_x, red.speeds.POUNCE)
        self.assertEqual(red.texture_type, "pouncing")


class TestRedAirDash(GameViewTestCase):
    def test_air_dash_after_double_jump(self):
        game_view = self.game_view
        red = _switch_to(game_view, RedCat)
        h.settle(game_view)
        red.center_x = 300
        h.press(game_view, K.RIGHT)
        h.jump_to_apex(game_view)
        h.press(game_view, K.SPACE)
        h.run_frames(game_view, 3)
        self.assertEqual(game_view.physics_engine.jumps_since_ground, 2)
        h.press(game_view, K.SPACE)  # no jumps left -> air dash
        self.assertTrue(red.state.air_dash.is_dashing)
        self.assertEqual(game_view.physics_engine.jumps_since_ground, 3)
        h.run_frames(game_view, 1)
        self.assertEqual(red.change_x, red.speeds.POUNCE)
        self.assertEqual(red.change_y, 0)
        self.assertEqual(red.texture_type, "scratching")
        h.press(game_view, K.SPACE)  # only one dash per air-time
        self.assertEqual(game_view.physics_engine.jumps_since_ground, 3)
        h.run_frames(game_view, 20)
        self.assertFalse(red.state.air_dash.is_dashing)

    def test_dash_kills(self):
        red = _switch_to(self.game_view, RedCat)
        cat = h.make_cat(self.game_view, 900, 300, add=False)
        red.state.air_dash.is_dashing = True
        self.assertTrue(red.can_kill_cat(cat))


class TestYellowDrop(GameViewTestCase):
    def test_drop_needs_height(self):
        game_view = self.game_view
        yellow = _switch_to(game_view, YellowCat)
        h.settle(game_view)
        h.press(game_view, K.SPACE)
        h.run_frames(game_view, 2)
        h.press(game_view, K.DOWN)
        self.assertFalse(yellow.state.drop.is_dropping)

    def test_drop_from_high_double_jump(self):
        game_view = self.game_view
        yellow = _switch_to(game_view, YellowCat)
        h.settle(game_view)
        yellow.center_x = 400
        h.jump_to_apex(game_view)
        h.press(game_view, K.SPACE)
        h.run_frames(game_view, 3)
        yellow.bottom = game_view.ground_height + yellow.height * 3  # a standard jump can't reach
        x = yellow.center_x
        h.press(game_view, K.DOWN)
        self.assertTrue(yellow.state.drop.is_dropping)
        self.assertEqual(yellow.change_x, 0)
        self.assertEqual(yellow.change_y, 0)
        h.run_frames(game_view, 3)
        self.assertEqual(yellow.texture_type, "dropping")
        self.assertEqual(yellow.move_state, game.STOP)
        h.press(game_view, K.RIGHT)  # cannot steer while dropping
        h.run_frames(game_view, 5)
        self.assertEqual(yellow.center_x, x)
        h.release(game_view, K.RIGHT)
        h.settle(game_view)
        self.assertFalse(yellow.state.drop.is_dropping)

    def test_drop_area_kill(self):
        game_view = self.game_view
        yellow = _switch_to(game_view, YellowCat)
        cat = h.make_cat(game_view, 500, 200, add=False)
        yellow.state.drop.is_dropping = True
        yellow.change_y = -30
        yellow.bottom = game_view.ground_height + cat.height - 1
        yellow.center_x = cat.center_x + cat.width * 1.5
        self.assertTrue(yellow.can_kill_cat(cat))  # reach = cat.width * |change_y| / 15 = 2 widths
        yellow.center_x = cat.center_x + cat.width * 2.5
        self.assertFalse(yellow.can_kill_cat(cat))
        yellow.center_x = cat.center_x
        yellow.bottom = game_view.ground_height + cat.height + 10
        self.assertFalse(yellow.can_kill_cat(cat))  # still too high


class TestHitsAndKills(GameViewTestCase):
    def test_get_hit(self):
        p = self.game_view.player
        cat = h.make_cat(self.game_view, 500, 200, add=False)
        p.get_hit(cat)
        self.assertEqual(p.lives, 2)
        self.assertEqual(p.hit_timer, p.INVULNERABILITY_DURATION_s)
        self.assertEqual(abs(p.change_x), p.speeds.POUNCE)
        self.assertTrue(0 <= p.change_y <= p.speeds.POUNCE)
        self.assertTrue(self.sounds)
        p.get_hit(cat)  # invulnerable
        self.assertEqual(p.lives, 2)

    def test_invulnerability_flicker_and_expiry(self):
        game_view = self.game_view
        p = game_view.player
        p.get_hit(h.make_cat(game_view, 500, 200, add=False))
        alphas = []
        for _ in range(10):
            game_view.on_update(h.DT)
            alphas.append(p.alpha)
        self.assertEqual(set(alphas), {0, 255})
        self.assertEqual(p.texture_type, "getting_hit")
        h.run_frames(game_view, 10, dt=0.15)
        self.assertLessEqual(p.hit_timer, 0)
        self.assertEqual(p.alpha, 255)

    def test_last_life_hit_has_no_knockback(self):
        p = self.game_view.player
        p.lives = 1
        p.get_hit(h.make_cat(self.game_view, 500, 200, add=False))
        self.assertEqual(p.lives, 0)
        self.assertEqual(p.hit_timer, 0)
        self.assertEqual(p.change_x, 0)

    def test_dropping_or_red_pouncing_is_immune(self):
        game_view = self.game_view
        cat = h.make_cat(game_view, 500, 200, add=False)
        p = game_view.player
        p.state.drop.is_dropping = True
        p.get_hit(cat)
        self.assertEqual(p.lives, 3)
        p.state.drop.is_dropping = False
        p.state.pounce.is_pouncing = True  # BlueCat pouncing is not immune
        p.get_hit(cat)
        self.assertEqual(p.lives, 2)
        red = game_view.player_color_cat_dict["crimson"]
        red.state.pounce.is_pouncing = True
        red.get_hit(cat)
        self.assertEqual(red.lives, 2)

    def test_jump_kill_from_above(self):
        p = self.game_view.player
        cat = h.make_cat(self.game_view, 500, 200, add=False)
        mid_height = cat.top - cat.height / 2
        p.bottom = mid_height + 1
        self.assertTrue(p.can_kill_cat(cat))
        self.assertEqual(p.change_y, 2 * p.speeds.JUMP)  # bounce off the cat
        p.change_y = 0
        p.bottom = mid_height - 1
        self.assertFalse(p.can_kill_cat(cat))
        p.bottom = mid_height + 1
        p.hit_timer = 1
        self.assertFalse(p.can_kill_cat(cat))  # no kills while invulnerable

    def test_blue_pounce_kill(self):
        game_view = self.game_view
        p = game_view.player
        cat = h.make_cat(game_view, 500, 200, add=False)
        p.state.pounce.is_pouncing = True
        p.change_x = 30
        p.bottom = cat.bottom
        self.assertTrue(p.can_kill_cat(cat))
        self.assertFalse(p.state.pounce.is_pouncing)
        self.assertEqual(p.change_x, 15)
        self.assertEqual(p.change_y, 2 * p.speeds.JUMP)
        self.assertGreaterEqual(game_view.physics_engine.jumps_since_ground, 2)

    def test_red_pounce_does_not_kill(self):
        game_view = self.game_view
        red = game_view.player_color_cat_dict["crimson"]
        red.physics_engine = game_view.physics_engine
        cat = h.make_cat(game_view, 500, 200, add=False)
        red.state.pounce.is_pouncing = True
        red.bottom = cat.bottom
        self.assertFalse(red.can_kill_cat(cat))

    def test_yellow_swipe_needs_similar_size(self):
        for cat_scale, expected in [(1.6, True), (1.8, True), (2.0, False), (1.4, False)]:
            with self.subTest(cat_scale=cat_scale):
                self.isolate()
                game_view = self.make_game_view()
                yellow = game_view.player_color_cat_dict["gold"]  # scale 1.65
                cat = h.make_cat(game_view, 500, 200, scale=cat_scale, add=False)
                yellow.state.pounce.is_pouncing = True
                yellow.bottom = cat.bottom
                self.assertIs(yellow.can_kill_cat(cat), expected)


class TestSuperpower(GameViewTestCase):
    def test_ready_after_25_favorites(self):
        game_view = self.game_view
        p = game_view.player
        p.n_favorite_pops_collected = 24
        h.run_frames(game_view, 1)
        self.assertFalse(p.state.superpower.is_ready)
        p.n_favorite_pops_collected = 25
        h.run_frames(game_view, 1)
        self.assertTrue(p.state.superpower.is_ready)
        self.assertEqual(p.n_favorite_pops_collected, 0)
        self.assertTrue(p.texture_type.endswith("_aura"))

    def test_activate_and_expire(self):
        game_view = self.game_view
        p = game_view.player
        h.press(game_view, K.LCTRL)
        self.assertFalse(p.state.superpower.is_on)  # not ready yet
        p.state.superpower.is_ready = True
        h.press(game_view, K.LCTRL)
        self.assertTrue(p.state.superpower.is_on)
        self.assertFalse(p.state.superpower.is_ready)
        self.assertEqual(p.superpower_timer, 10)
        h.run_frames(game_view, 5, dt=1.0)
        self.assertTrue(p.state.superpower.is_on)
        h.run_frames(game_view, 6, dt=1.0)
        self.assertFalse(p.state.superpower.is_on)
        self.assertEqual(p.superpower_timer, 0)
        self.assertFalse(p.texture_type.endswith("_aura"))
