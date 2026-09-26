"""End-to-end sessions driven through the window's current view with simulated key presses."""

import random

import arcade
import game_constants as game
from helper import load_high_scores, save_high_scores
from sprites import BlueCat, IceCreamTruck

import ice_cream_truck as ict
from tests.support import GameTestCase, h

K = arcade.key


def _key(window, key, modifiers=0):
    window.current_view.on_key_press(key, modifiers)


def _key_up(window, key):
    window.current_view.on_key_release(key, 0)


def _start_game(window):
    title = ict.TitleView()
    window.show_view(title)
    h.tick(window, 2)
    if not title.is_game_ready:
        raise AssertionError("title never set up the game")
    _key(window, K.RETURN)
    game_view = window.current_view
    if not isinstance(game_view, ict.PlatformerView):
        raise AssertionError("Enter did not start the game")
    game_view.new_cat_prob_frame = 0.0
    return game_view


def _lose_all_cats(window):
    view = window.current_view
    while view.player_color_cat_dict:
        view.player.lives = 0
        h.tick(window, 1)
    for _ in range(200):
        if window.current_view is not view:
            return
        h.tick(window, 1, draw=False)
    raise AssertionError("game never ended")


class TestSessions(GameTestCase):
    def test_full_session(self):
        window = self.window
        self.no_throws()
        closed = self.closed()
        game_view = _start_game(window)
        h.tick(window, 50)
        self.assertFalse(game_view.player.state.is_in_air)

        # run right into a favourite popsicle
        player = game_view.player
        pop = h.make_popsicle(game_view, player.color_str, player.center_x + 120, player.center_y)
        _key(window, K.RIGHT)
        for _ in range(40):
            h.tick(window, 1, draw=False)
            if game_view.score:
                break
        self.assertEqual(game_view.score, 50)
        self.assertNotIn(pop, game_view.popsicles)
        _key_up(window, K.RIGHT)

        # jump
        _key(window, K.SPACE)
        h.tick(window, 3)
        self.assertTrue(game_view.player.state.is_in_air)
        _key_up(window, K.SPACE)

        # pause / unpause
        _key(window, K.P)
        self.assertIsInstance(window.current_view, ict.PauseView)
        t = game_view.game_timer
        h.tick(window, 10)
        self.assertEqual(game_view.game_timer, t)
        _key(window, K.P)
        self.assertIs(window.current_view, game_view)
        h.tick(window, 3)
        self.assertGreater(game_view.game_timer, t)

        # lose every cat -> new high score
        _lose_all_cats(window)
        entry = window.current_view
        self.assertIsInstance(entry, ict.NewHighScoreView)
        for key in (K.Z, K.O, K.E):
            _key(window, key)
        h.tick(window, 1)
        _key(window, K.RETURN)
        over = window.current_view
        self.assertIsInstance(over, ict.GameOverView)
        h.tick(window, 1)
        self.assertEqual(load_high_scores(), [("ZOE", 50), ("???", 0), ("???", 0)])

        # restart
        _key(window, K.RETURN)
        self.assertIs(window.current_view, game_view)
        self.assertEqual(game_view.score, 0)
        self.assertEqual(game_view.score_multiplier, 1)
        self.assertIsInstance(game_view.player, BlueCat)
        self.assertEqual(game_view.player.lives, 3)
        self.assertEqual(len(game_view.player_color_cat_dict), 3)
        self.assertEqual(game_view.high_scores_list[0], ("ZOE", 50))
        h.tick(window, 5)

        # quit via Q then Esc
        _key(window, K.Q)
        self.assertIsInstance(window.current_view, ict.GameOverView)
        _key(window, K.ESCAPE)
        self.assertEqual(closed, [True])

    def test_session_without_high_score(self):
        self.no_throws()
        save_high_scores([("A", 300), ("B", 200), ("C", 100)])
        game_view = _start_game(self.window)
        game_view.score = 80
        _lose_all_cats(self.window)
        self.assertIsInstance(self.window.current_view, ict.GameOverView)
        self.assertEqual(load_high_scores(), [("A", 300), ("B", 200), ("C", 100)])

    def test_game_over_takes_three_seconds(self):
        window = self.window
        self.no_throws()
        game_view = _start_game(window)
        for _ in range(3):
            game_view.player.lives = 0
            h.tick(window, 1, draw=False)
        h.tick(window, 170, draw=False)
        self.assertIs(window.current_view, game_view)
        h.tick(window, 15, draw=False)
        self.assertIsInstance(window.current_view, ict.GameOverView)

    def test_random_play_smoke(self):
        """Play with real throws and competitors; check invariants each frame"""
        window = self.window
        for seed in [1, 2]:
            with self.subTest(seed=seed):
                self.isolate()
                random.seed(seed)
                self.patch(IceCreamTruck, "THROW_PROBABILITY", 0.2)
                game_view = _start_game(window)
                game_view.new_cat_prob_frame = 0.05
                game_view.n_allowed_cats = 3
                script = {10: K.RIGHT, 40: K.SPACE, 55: K.SPACE, 90: K.LEFT, 130: K.Z, 160: K.DOWN}
                for frame in range(240):
                    if window.current_view is not game_view:
                        break
                    if frame in script:
                        _key(window, script[frame])
                    if frame - 20 in script:
                        _key_up(window, script[frame - 20])
                    h.tick(window, 1, draw=frame % 20 == 0)
                    v = game_view
                    self.assertGreaterEqual(v.score, 0)
                    self.assertEqual(v.score % 1, 0)
                    self.assertTrue(v.n_cats == len(v.cats) <= v.n_allowed_cats)
                    self.assertLessEqual(0, v.player.left)
                    self.assertLessEqual(v.player.right, v.map_width + 1e-6)
                    self.assertEqual(v.view_left, 0)
                    self.assertGreaterEqual(v.view_bottom, 0)
                    self.assertTrue(all(0 <= p.point_value <= 100 for p in v.popsicles))
                    self.assertGreaterEqual(v.score_multiplier, 1)
                self.assertGreater(game_view.game_timer, 0)
                self.assertTrue(
                    len(game_view.popsicles) + game_view.score > 0 or game_view.n_cats > 0
                )
                self.assertLessEqual(set(game_view.player_color_cat_dict), game.PLAYER_COLORS)
