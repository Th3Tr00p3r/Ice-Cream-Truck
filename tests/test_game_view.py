"""PlatformerView rules: setup, scoring, lives, multiplier, cats, switching, timers, HUD."""

import arcade
import game_constants as game
from helper import Vector, save_high_scores
from sprites import (
    BlueCat,
    CompetitorCat,
    IceCreamTruck,
    RedCat,
    RegularPopsicle,
    YellowCat,
)

import ice_cream_truck as ict
from tests.support import GameTestCase, GameViewTestCase, approx, h

K = arcade.key


def _kill_current_player(view):
    view.player.lives = 0
    h.run_frames(view, 1)


class TestSetup(GameViewTestCase):
    def test_initial_state(self):
        v = self.game_view
        self.assertEqual(v.score, 0)
        self.assertEqual(v.score_multiplier, 1)
        self.assertIsInstance(v.player, BlueCat)
        self.assertEqual(set(v.player_color_cat_dict), {"deepskyblue", "crimson", "gold"})
        self.assertEqual(len(v.popsicles), 0)
        self.assertEqual(len(v.cats), 0)
        self.assertEqual(v.n_cats, 0)
        self.assertEqual(v.n_allowed_cats, 1)
        self.assertEqual(v.map_width, 1600)
        self.assertEqual(v.ground_height, 128)
        self.assertEqual(v.ice_cream_truck.position, tuple(game.TRUCK_START_POS))
        self.assertEqual(v.view_left, 0)
        self.assertEqual(v.view_bottom, 0)
        self.assertEqual(v.high_scores_list, [("???", 0)] * 3)
        self.assertEqual(v.level, 1)
        self.assertEqual(v.MAX_PLAYER_LIVES, 5)

    def test_setup_resets_a_played_game(self):
        v = self.game_view
        v.score, v.score_multiplier = 500, 4
        v.player.lives = 1
        h.make_cat(v, 300, 300)
        h.make_popsicle(v, "lime", 1000, 500)
        v.view_bottom = 50
        v.setup()
        self.assertEqual(v.score, 0)
        self.assertEqual(v.score_multiplier, 1)
        self.assertEqual(v.player.lives, 3)
        self.assertIsInstance(v.player, BlueCat)
        self.assertEqual(len(v.cats), 0)
        self.assertEqual(v.n_cats, 0)
        self.assertEqual(len(v.popsicles), 0)
        self.assertEqual(v.view_bottom, 0)


class TestSetupFresh(GameTestCase):
    def test_setup_starts_with_a_jump(self):
        self.no_throws()
        v = ict.PlatformerView()
        self.window.show_view(v)
        v.setup()
        self.assertEqual(v.player.position, tuple(game.PLAYER_START_POS))
        self.assertEqual(v.player.change_y, v.player.speeds.JUMP)
        self.assertEqual(v.physics_engine.jumps_since_ground, 1)
        self.assertEqual(v.new_cat_prob_frame, 0.001)
        self.assertEqual(v.game_timer, 0)
        self.assertEqual(v.game_over_timer, 0)
        self.assertEqual(v.slow_time_timer, 0)

    def test_setup_loads_saved_high_scores(self):
        self.no_throws()
        save_high_scores([("A", 30), ("B", 20), ("C", 10)])
        v = ict.PlatformerView()
        self.window.show_view(v)
        v.setup()
        self.assertEqual(v.high_scores_list, [("A", 30), ("B", 20), ("C", 10)])


class TestScoring(GameViewTestCase):
    def test_favorite_color_scores_five_times(self):
        v = self.game_view
        pop = h.make_popsicle(v, v.player.color_str)
        n_sounds = len(self.sounds)
        h.run_frames(v, 1)
        self.assertEqual(v.score, 50)
        self.assertNotIn(pop, v.popsicles)
        self.assertTrue(pop.is_off_screen)
        self.assertEqual(v.player.n_favorite_pops_collected, 1)
        self.assertEqual(len(self.sounds), n_sounds + 1)

    def test_other_color_scores_base_points(self):
        v = self.game_view
        h.make_popsicle(v, "lime")
        h.run_frames(v, 1)
        self.assertEqual(v.score, 10)
        self.assertEqual(v.player.n_favorite_pops_collected, 0)

    def test_multiplier_applies(self):
        v = self.game_view
        v.score_multiplier = 3
        v.score_multiplier_timer = 5
        h.make_popsicle(v, "lime")
        h.make_popsicle(v, v.player.color_str)
        h.run_frames(v, 1)
        self.assertEqual(v.score, 3 * (10 + 50))

    def test_melted_popsicle_is_worth_less(self):
        v = self.game_view
        pop = h.make_popsicle(v, "lime", 1000, 300)
        pop.point_value = 4
        pop.center_x, pop.center_y = v.player.position
        h.run_frames(v, 1)
        self.assertEqual(v.score, 4)

    def test_fully_melted_popsicle_not_collected(self):
        v = self.game_view
        pop = h.make_popsicle(v, v.player.color_str)
        pop.point_value = 0
        n_sounds = len(self.sounds)
        h.run_frames(v, 1)
        self.assertIn(pop, v.popsicles)
        self.assertEqual(v.player.n_favorite_pops_collected, 0)
        self.assertEqual(len(self.sounds), n_sounds)

    def test_distant_popsicle_not_collected(self):
        v = self.game_view
        pop = h.make_popsicle(v, "lime", 1200, 600)
        h.run_frames(v, 1)
        self.assertEqual(v.score, 0)
        self.assertIn(pop, v.popsicles)

    def test_favorites_not_counted_while_superpower_ready_or_on(self):
        v = self.game_view
        v.player.state.superpower.is_ready = True
        h.make_popsicle(v, v.player.color_str)
        h.run_frames(v, 1)
        self.assertEqual(v.score, 50)
        self.assertEqual(v.player.n_favorite_pops_collected, 0)

    def test_heart_adds_life(self):
        v = self.game_view
        h.make_heart(v)
        h.run_frames(v, 1)
        self.assertEqual(v.player.lives, 4)
        self.assertEqual(v.score, 0)

    def test_heart_at_max_lives_scores(self):
        v = self.game_view
        v.player.lives = v.player.MAX_LIVES
        v.score_multiplier, v.score_multiplier_timer = 2, 5
        h.make_heart(v)
        h.run_frames(v, 1)
        self.assertEqual(v.player.lives, 5)
        self.assertEqual(v.score, 200)

    def test_superpower_ready_via_collection(self):
        v = self.game_view
        v.player.n_favorite_pops_collected = 24
        h.make_popsicle(v, v.player.color_str)
        h.run_frames(v, 2)
        self.assertTrue(v.player.state.superpower.is_ready)
        self.assertEqual(v.player.n_favorite_pops_collected, 0)


class TestMultiplier(GameViewTestCase):
    def test_decays_one_step_every_five_seconds(self):
        v = self.game_view
        v.score_multiplier, v.score_multiplier_timer = 3, 0.0
        h.run_frames(v, 1, dt=1.0)
        self.assertEqual(v.score_multiplier, 2)
        self.assertEqual(v.score_multiplier_timer, 5)
        h.run_frames(v, 5, dt=1.0)
        self.assertEqual(v.score_multiplier, 2)
        h.run_frames(v, 1, dt=1.0)
        self.assertEqual(v.score_multiplier, 1)
        h.run_frames(v, 20, dt=1.0)
        self.assertEqual(v.score_multiplier, 1)


class TestCompetitors(GameViewTestCase):
    def test_jump_kill(self):
        v = self.game_view
        p = v.player
        cat = h.make_cat(v, 400, 400, on_ground=True)
        h.run_frames(v, 1)
        p.center_x = cat.center_x
        p.bottom = cat.top - cat.height / 2 + 5
        p.change_y = 0
        n_sounds = len(self.sounds)
        h.run_frames(v, 1)
        self.assertNotIn(cat, v.cats)
        self.assertEqual(v.n_cats, 0)
        self.assertEqual(v.score_multiplier, 2)
        self.assertEqual(v.score_multiplier_timer, approx(5.0))
        self.assertEqual(p.lives, 3)
        self.assertGreater(p.change_y, 0)  # bounced
        self.assertEqual(len(v.poofs), 1)
        self.assertGreater(len(self.sounds), n_sounds)

    def test_same_color_kills_each_get_a_poof(self):
        v = self.game_view
        cats = [h.make_cat(v, x, 400, color_str="lime", on_ground=True) for x in (400, 1200)]
        h.run_frames(v, 1)
        for cat in cats:
            v.player.center_x = cat.center_x
            v.player.bottom = cat.top - cat.height / 2 + 5
            v.player.change_y = 0
            h.run_frames(v, 1)
            self.assertNotIn(cat, v.cats)
        self.assertEqual(len(v.poofs), 2)
        self.assertEqual(sorted(p.center_x for p in v.poofs), approx([400, 1200], abs=20))

    def test_poof_disappears_after_animation(self):
        v = self.game_view
        cat = h.make_cat(v, 400, 400, on_ground=True)
        h.run_frames(v, 1)
        v.player.center_x = cat.center_x
        v.player.bottom = cat.top - cat.height / 2 + 5
        h.run_frames(v, 1)
        self.assertEqual(len(v.poofs), 1)
        h.run_frames(v, 12, dt=0.06)  # 15 animation frames, one per > 0.05s
        self.assertEqual(len(v.poofs), 1)
        h.run_frames(v, 5, dt=0.06)
        self.assertEqual(len(v.poofs), 0)

    def test_touching_cat_costs_a_life(self):
        v = self.game_view
        p = v.player
        p.center_x = 400
        h.make_cat(v, 400, 400, on_ground=True)
        h.run_frames(v, 1)
        self.assertEqual(p.lives, 2)
        self.assertGreater(p.hit_timer, 1)
        h.run_frames(v, 10)
        self.assertEqual(p.lives, 2)  # invulnerable for a while
        self.assertEqual(v.n_cats, 1)
        self.assertEqual(v.score_multiplier, 1)

    def test_blue_pounce_kills(self):
        v = self.game_view
        p = v.player
        p.center_x = 300
        h.press(v, K.RIGHT)
        for _ in range(30):
            h.run_frames(v, 1)
            if p.state.pounce.can_pounce:
                break
        h.press(v, K.DOWN)
        cat = h.make_cat(v, p.center_x + 60, 400, on_ground=True)
        h.run_frames(v, 4)
        self.assertNotIn(cat, v.cats)
        self.assertEqual(p.lives, 3)
        self.assertEqual(v.score_multiplier, 2)

    def test_cat_eats_own_color_popsicle_only(self):
        v = self.game_view
        cat = h.make_cat(v, 1200, 400, color_str="lime", on_ground=True)
        h.run_frames(v, 1)
        own = h.make_popsicle(v, "lime", cat.center_x, cat.center_y)
        other = h.make_popsicle(v, "pink", cat.center_x, cat.center_y)
        own.is_on_ground = other.is_on_ground = True
        h.run_frames(v, 1)
        self.assertNotIn(own, v.popsicles)
        self.assertIn(other, v.popsicles)
        self.assertEqual(v.score, 0)

    def test_cat_retargets_when_another_cat_eats_its_popsicle(self):
        v = self.game_view
        eater = h.make_cat(v, 700, 400, color_str="lime", on_ground=True)
        chaser = h.make_cat(v, 400, 400, color_str="lime", on_ground=True)
        h.run_frames(v, 1)
        eaten = h.make_popsicle(v, "lime", eater.center_x, eater.center_y)
        other = h.make_popsicle(v, "lime", 1500, eater.center_y)
        eaten.is_on_ground = other.is_on_ground = True
        h.run_frames(v, 1)
        self.assertNotIn(eaten, v.popsicles)
        h.run_frames(v, 1)
        self.assertIs(chaser.sought_popsicle, other)

    def test_cat_spawning(self):
        v = self.game_view
        v.new_cat_prob_frame = 1.0
        h.run_frames(v, 1)
        self.assertTrue(v.n_cats == len(v.cats) == 1)
        cat = v.cats[0]
        self.assertIsInstance(cat, CompetitorCat)
        self.assertIn(cat.color_str, game.COLORS - game.PLAYER_COLORS)
        self.assertIn(cat.center_x, (0, game.SCREEN_PROPS.width))
        self.assertTrue(0 <= cat.center_y <= game.SCREEN_PROPS.height / 2)
        self.assertTrue(game.CHARACTER_SCALING <= cat.scale_x <= game.CHARACTER_SCALING * 1.5)
        self.assertTrue(75 <= cat.speeds.RUN <= 125)
        h.run_frames(v, 5)
        self.assertEqual(v.n_cats, 1)  # capped by n_allowed_cats
        v.n_allowed_cats = 3
        h.run_frames(v, 5)
        self.assertTrue(v.n_cats == len(v.cats) == 3)

    def test_spawned_cats_land_and_head_to_truck(self):
        v = self.game_view
        v.new_cat_prob_frame = 1.0
        v.n_allowed_cats = 2
        h.run_frames(v, 2)
        v.new_cat_prob_frame = 0.0
        truck_x = v.ice_cream_truck.center_x
        start = {cat: abs(cat.center_x - truck_x) for cat in v.cats}
        h.run_frames(v, 60)
        for cat in v.cats:
            self.assertFalse(cat.state.is_in_air)
            self.assertEqual(cat.mode, "returning")
            self.assertLess(abs(cat.center_x - truck_x), start[cat])
            self.assertEqual(cat.change_x > 0, cat.center_x < truck_x)

    def test_begging_cat_doubles_its_color_probability(self):
        self.patch(IceCreamTruck, "THROW_PROBABILITY", 0.03)
        v = self.game_view
        truck = v.ice_cream_truck
        cat = h.make_cat(v, truck.center_x, 400, color_str="brown", on_ground=True)
        h.run_frames(v, 1)
        self.assertEqual(cat.mode, "begging")
        probs = truck.color_pop_probs_dict
        self.assertEqual(probs["brown"], approx(0.06))
        self.assertTrue(all(probs[c] == approx(0.03) for c in game.COLORS - {"brown"}))


class TestDeathAndSwitching(GameViewTestCase):
    def test_z_cycles_blue_red_yellow(self):
        v = self.game_view
        seen = []
        for _ in range(4):
            seen.append(type(v.player))
            h.press(v, K.Z)
            h.run_frames(v, 1, dt=0.31)
        self.assertEqual(seen, [BlueCat, RedCat, YellowCat, BlueCat])

    def test_switch_cooldown(self):
        v = self.game_view
        h.press(v, K.Z)
        self.assertIsInstance(v.player, RedCat)
        h.press(v, K.Z)
        self.assertIsInstance(v.player, RedCat)
        h.run_frames(v, 1, dt=0.2)
        h.press(v, K.Z)
        self.assertIsInstance(v.player, RedCat)
        h.run_frames(v, 1, dt=0.11)
        h.press(v, K.Z)
        self.assertIsInstance(v.player, YellowCat)

    def test_switch_transfers_motion_and_state(self):
        v = self.game_view
        blue = v.player
        blue.center_x = 600
        h.press(v, K.RIGHT)
        h.run_frames(v, 5)
        x, y, vx = blue.center_x, blue.center_y, blue.change_x
        h.press(v, K.Z)
        red = v.player
        self.assertIsInstance(red, RedCat)
        self.assertEqual(red.center_x, x)
        self.assertEqual(red.center_y, approx(y + red.height))
        self.assertEqual(red.change_x, vx)
        self.assertIs(red.state, blue.state)
        self.assertEqual(blue.position, (0, 0))
        self.assertIs(red.physics_engine, v.physics_engine)
        self.assertEqual(red.lives, 2)
        self.assertEqual(blue.lives, 3)
        h.release(v, K.RIGHT)
        h.settle(v)
        self.assertFalse(red.state.is_in_air)

    def test_lives_are_per_cat(self):
        v = self.game_view
        v.player.get_hit(h.make_cat(v, 900, 400, add=False))
        h.press(v, K.Z)
        self.assertEqual(v.player.lives, 2)
        h.run_frames(v, 1, dt=0.31)
        h.press(v, K.Z)
        h.run_frames(v, 1, dt=0.31)
        h.press(v, K.Z)
        self.assertIsInstance(v.player, BlueCat)
        self.assertEqual(v.player.lives, 2)

    def test_death_switches_to_next_cat(self):
        v = self.game_view
        blue = v.player
        _kill_current_player(v)
        self.assertFalse(blue.is_alive)
        self.assertNotIn("deepskyblue", v.player_color_cat_dict)
        self.assertIsInstance(v.player, RedCat)
        self.assertGreater(v.player.hit_timer, 1.4)  # respawn invulnerability
        self.assertIn(blue.poof_sprite, v.poofs)
        self.assertEqual(v.game_over_timer, 0)

    def test_death_of_red_returns_to_blue(self):
        v = self.game_view
        h.press(v, K.Z)
        _kill_current_player(v)
        self.assertIsInstance(v.player, BlueCat)
        self.assertEqual(set(v.player_color_cat_dict), {"deepskyblue", "gold"})

    def test_z_skips_dead_cats(self):
        v = self.game_view
        _kill_current_player(v)  # blue dies -> red
        seen = []
        for _ in range(3):
            h.run_frames(v, 1, dt=0.31)
            h.press(v, K.Z)
            seen.append(type(v.player))
        self.assertNotIn(BlueCat, seen)
        self.assertEqual(set(seen), {RedCat, YellowCat})

    def test_all_dead_is_game_over(self):
        v = self.game_view
        for _ in range(3):
            _kill_current_player(v)
        self.assertEqual(v.player_color_cat_dict, {})
        self.assertFalse(v.player.is_alive)
        self.assertTrue(2.9 < v.game_over_timer < 3.0)
        self.assertIs(self.window.current_view, v)
        h.run_frames(v, 170)
        self.assertIs(self.window.current_view, v)
        h.run_frames(v, 15)
        self.assertIsInstance(self.window.current_view, ict.GameOverView)
        self.assertIs(self.window.current_view.game_view, v)

    def test_game_over_timer_landing_exactly_on_zero(self):
        v = self.game_view
        for _ in range(2):
            _kill_current_player(v)
        v.player.lives = 0
        h.run_frames(v, 7, dt=0.5)  # 3.0 - 6 * 0.5 == 0.0 exactly
        self.assertIsInstance(self.window.current_view, ict.GameOverView)

    def test_all_dead_with_high_score(self):
        v = self.game_view
        v.score = 120
        for _ in range(3):
            _kill_current_player(v)
        h.run_frames(v, 10, dt=0.35)
        self.assertIsInstance(self.window.current_view, ict.NewHighScoreView)
        self.assertEqual(self.window.current_view.new_score, 120)

    def test_score_equal_to_lowest_is_not_a_high_score(self):
        v = self.game_view
        v.high_scores_list = [("A", 300), ("B", 200), ("C", 100)]
        v.score = 100
        for _ in range(3):
            _kill_current_player(v)
        h.run_frames(v, 10, dt=0.35)
        self.assertIsInstance(self.window.current_view, ict.GameOverView)


class TestTimersAndTruck(GameViewTestCase):
    def test_difficulty_ramps_every_minute(self):
        v = self.game_view
        v.new_cat_prob_frame = 1e-9
        h.run_frames(v, 2, dt=29.0)
        self.assertEqual(v.n_allowed_cats, 1)
        h.run_frames(v, 1, dt=2.0)
        self.assertEqual(v.n_allowed_cats, 2)
        self.assertEqual(v.game_timer, 0)
        self.assertEqual(v.new_cat_prob_frame, approx(1.25e-9))

    def test_allowed_cats_capped_at_seven(self):
        v = self.game_view
        v.new_cat_prob_frame = 1e-12
        v.n_allowed_cats = 7
        v.game_timer = 59.99
        h.run_frames(v, 1, dt=0.02)
        self.assertEqual(v.n_allowed_cats, 7)
        self.assertEqual(v.new_cat_prob_frame, approx(1.25e-12))

    def test_truck_throws_popsicles(self):
        v = self.game_view
        truck = v.ice_cream_truck
        truck.heart_pop_prob, truck.throw_probability_frame = 0.0, 1.0
        truck.color_pop_probs_dict = {c: 1.0 for c in game.COLORS}
        h.run_frames(v, 1)
        self.assertEqual(len(v.popsicles), 1)
        pop = v.popsicles[0]
        self.assertIsInstance(pop, RegularPopsicle)
        self.assertEqual(pop.position, truck.position)
        h.run_frames(v, 5)
        self.assertEqual(len(v.popsicles), 1)  # throwing disabled again by no_throws()

    def test_heart_throw_slows_time(self):
        v = self.game_view
        v.ice_cream_truck.heart_pop_prob = 1.0
        h.run_frames(v, 1)
        self.assertEqual([p.type for p in v.popsicles], ["heart"])
        self.assertEqual(v.slow_time_timer, 2.0)
        t = v.game_timer
        h.run_frames(v, 1)
        self.assertEqual(v.game_timer - t, approx(ict.PlatformerView.SLOW_TIME_FACTOR / 60))
        self.assertEqual(v.slow_time_timer, approx(2.0 - 1 / 60))
        h.run_frames(v, 3, dt=1.0)
        t = v.game_timer
        h.run_frames(v, 1)
        self.assertEqual(v.game_timer - t, approx(1 / 60))

    def test_superpower_boosts_truck(self):
        self.patch(IceCreamTruck, "THROW_PROBABILITY", 0.03)
        v = self.game_view
        v.player.state.superpower.is_ready = True
        h.press(v, K.LCTRL)
        h.run_frames(v, 1)
        truck = v.ice_cream_truck
        self.assertEqual(truck.throw_probability_frame, approx(0.09))
        self.assertEqual(truck.color_pop_probs_dict[v.player.color_str], approx(30))
        self.assertEqual(truck.color_pop_probs_dict["lime"], approx(0.03))

    def test_popsicle_falls_bounces_melts_and_vanishes(self):
        v = self.game_view
        pop = RegularPopsicle("lime", Vector(1200, 300), 200, 90)
        v.popsicles.append(pop)
        peak = 0
        for _ in range(70):
            v.on_update(1 / 30)
            peak = max(peak, pop.center_y)
        self.assertGreater(peak, 370)  # rose before falling
        self.assertTrue(pop.is_on_ground)
        self.assertEqual(pop.change_y, 0)
        self.assertEqual(pop.center_x, 1200)
        self.assertEqual(pop.point_value, 10)
        self.assertLess(pop.frozen_timer, 1)
        values = []
        for _ in range(30):
            v.on_update(0.25)
            values.append(pop.point_value)
            if pop not in v.popsicles:
                break
        self.assertNotIn(pop, v.popsicles)
        self.assertTrue(pop.is_off_screen)
        self.assertEqual(values[:4], [10] * 4)
        self.assertEqual(values[-2:], [0, 0])
        self.assertEqual(values, sorted(values, reverse=True))
        self.assertLessEqual(len(values), 17)

    def test_popsicle_leaving_map_is_removed(self):
        v = self.game_view
        pop = RegularPopsicle("lime", Vector(1590, 500), 600, 180)  # thrown right, flat
        v.popsicles.append(pop)
        h.run_frames(v, 5)
        self.assertNotIn(pop, v.popsicles)
        self.assertTrue(pop.is_off_screen)


class TestKeys(GameViewTestCase):
    def test_pause_keys(self):
        game_view = self.game_view
        for key in (K.P, K.ESCAPE):
            self.window.show_view(game_view)
            h.press(game_view, key)
            self.assertIsInstance(self.window.current_view, ict.PauseView)
            self.assertIs(self.window.current_view.game_view, game_view)

    def test_q_ends_game(self):
        h.press(self.game_view, K.Q)
        self.assertIsInstance(self.window.current_view, ict.GameOverView)
        self.assertIs(self.window.current_view.game_view, self.game_view)

    def test_keys_pressed_tracking(self):
        v = self.game_view
        for key in (K.LEFT, K.RIGHT, K.DOWN, K.SPACE, K.LCTRL):
            h.press(v, key)
            self.assertTrue(v.keys_pressed[key])
            h.release(v, key)
            self.assertFalse(v.keys_pressed[key])

    def test_down_without_ability_is_harmless(self):
        h.press(self.game_view, K.DOWN)
        h.run_frames(self.game_view, 3)
        self.assertFalse(self.game_view.player.state.pounce.is_pouncing)


class TestScrolling(GameViewTestCase):
    def test_no_horizontal_scroll(self):
        v = self.game_view
        v.player.center_x = 1500
        h.press(v, K.RIGHT)
        h.run_frames(v, 30)
        self.assertEqual(v.view_left, 0)
        v.player.left = -30
        v.scroll_viewport()
        self.assertEqual(v.view_left, 0)

    def test_scroll_up_and_down(self):
        v = self.game_view
        p = v.player
        p.center_y = 1000
        v.scroll_viewport()
        top_margin = game.SCREEN_PROPS.height - game.TOP_VIEWPORT_MARGIN
        self.assertEqual(v.view_bottom, int(p.top - top_margin))
        first = v.view_bottom
        p.bottom = first + 500
        v.scroll_viewport()
        self.assertEqual(
            v.view_bottom, int(first - (first + game.BOTTOM_VIEWPORT_MARGIN - p.bottom))
        )
        p.bottom = 10
        v.scroll_viewport()
        self.assertEqual(v.view_bottom, 0)

    def test_viewport_follows_falling_player(self):
        v = self.game_view
        p = v.player
        p.center_y = 1400
        v.physics_engine.increment_jump_counter()
        h.run_frames(v, 1)
        self.assertGreater(v.view_bottom, 500)
        self.assertIsInstance(v.view_bottom, int)
        previous = v.view_bottom
        for _ in range(40):
            v.on_update(h.DT)
            self.assertLessEqual(v.view_bottom, previous)
            self.assertGreaterEqual(p.bottom, v.view_bottom)
            previous = v.view_bottom
        h.settle(v)
        self.assertEqual(v.view_bottom, 0)


class TestHud(GameViewTestCase):
    def test_initial_hud(self):
        v = self.game_view
        v.on_draw()
        self.assertEqual([s.position for s in v.score_sprites], [(92, 742)])
        self.assertEqual(
            [s.position for s in v.life_sprites], [(1367 + 42 * i, 742) for i in range(5)]
        )
        multiplier_xy = [xy for s in v.multiplier_sprites for xy in s.position]
        self.assertEqual(multiplier_xy, approx([1504.4, 679.4, 1533.8, 679.4]))
        full = [s.texture is v.full_heart_texture for s in v.life_sprites]
        self.assertEqual(full, [True] * 3 + [False] * 2)
        self.assertIs(v.multiplier_sprites[0].texture, v.score_textures.x)

    def test_hud_updates(self):
        v = self.game_view
        v.on_draw()
        v.score = 1250
        v.score_multiplier, v.score_multiplier_timer = 12, 5
        v.player.lives = 1
        v.on_draw()
        self.assertEqual(len(v.score_sprites), 4)
        xs = [s.center_x for s in v.score_sprites]
        self.assertEqual(xs, sorted(xs))
        self.assertEqual(xs[0], 92)
        self.assertEqual({s.center_y for s in v.score_sprites}, {742})
        digits = [v.score_textures.digits.index(s.texture) for s in v.score_sprites]
        self.assertEqual(digits, [1, 2, 5, 0])
        self.assertEqual(len(v.multiplier_sprites), 3)
        self.assertEqual(
            [s.texture is v.full_heart_texture for s in v.life_sprites], [True] + [False] * 4
        )

    def test_hud_stays_on_screen_when_scrolled(self):
        v = self.game_view
        v.on_draw()
        v.player.center_y = 1200
        v.scroll_viewport()
        self.assertGreater(v.view_bottom, 0)
        screen_ys = []
        for sprite_list in (v.score_sprites, v.life_sprites, v.multiplier_sprites):
            draw = sprite_list.draw

            def record(*args, sprite_list=sprite_list, draw=draw, **kwargs):
                camera_bottom = self.window.game_camera.bottom_left[1]
                screen_ys.extend(s.center_y - camera_bottom for s in sprite_list)
                return draw(*args, **kwargs)

            self.patch(sprite_list, "draw", record)
        v.on_draw()
        self.assertEqual(screen_ys, approx([742] * 6 + [679.4] * 2))

    def test_lives_hud_follows_current_cat(self):
        v = self.game_view
        h.press(v, K.Z)
        v.on_draw()
        self.assertEqual(sum(s.texture is v.full_heart_texture for s in v.life_sprites), 2)
        self.assertEqual(len(v.life_sprites), 5)

    def test_score_spritelist(self):
        for score in [0, 7, 10, 999, 123456]:
            with self.subTest(score=score):
                sprites = self.game_view.get_score_spritelist(score, Vector(50, 700))
                self.assertEqual(len(sprites), len(str(score)))
                xs = [s.center_x for s in sprites]
                self.assertEqual(xs, sorted(set(xs)))

    def test_multiplier_spritelist(self):
        sprites = self.game_view.get_score_spritelist(3, Vector(50, 700), is_multiplier=True)
        self.assertEqual(len(sprites), 2)
        self.assertIs(sprites[0].texture, self.game_view.score_textures.x)
        self.assertEqual(sprites[0].scale_x, approx(0.7))

    def test_lives_spritelist(self):
        sprites = self.game_view.get_lives_spritelist(5, 2, Vector(100, 100))
        self.assertEqual(len(sprites), 5)
        full = [s.texture is self.game_view.full_heart_texture for s in sprites]
        self.assertEqual(full, [True, True] + [False] * 3)
