"""Menu/overlay views (title, instructions, scores, pause, game over, name entry) and drawing."""

import arcade
import game_constants as game
from helper import load_high_scores, save_high_scores

import ice_cream_truck as ict
from tests.support import GameTestCase, GameViewTestCase, h

K = arcade.key


class TitleTestCase(GameTestCase):
    """Test case with a shown TitleView in self.title"""

    def setUp(self):
        super().setUp()
        self.title = ict.TitleView()
        self.window.show_view(self.title)

    def make_ready(self):
        """Draw once and update once so the title has set up its game"""
        self.no_throws()
        self.title.on_draw()
        self.title.on_update(1 / 60)
        return self.title


class TestTitleView(TitleTestCase):
    def test_game_is_set_up_only_after_first_draw(self):
        self.no_throws()
        title = self.title
        self.assertFalse(title.is_game_ready)
        title.on_update(1 / 60)
        self.assertFalse(title.is_game_ready)
        self.assertIsNone(title.game_view.player)
        title.on_draw()
        self.assertTrue(title.is_screen_drawn)
        title.on_update(1 / 60)
        self.assertTrue(title.is_game_ready)
        self.assertIsNot(title.game_view.player, None)
        self.assertEqual(title.game_view.score, 0)
        self.assertEqual(title.high_scores_list, [("???", 0)] * 3)

    def test_blinking_instructions(self):
        title = self.title
        self.assertFalse(title.show_instructions)
        title.on_update(1.0)
        self.assertFalse(title.show_instructions)
        title.on_update(1.1)
        self.assertTrue(title.show_instructions)
        self.assertEqual(title.display_timer, 1.0)
        title.on_update(0.5)
        self.assertTrue(title.show_instructions)
        title.on_update(0.6)
        self.assertFalse(title.show_instructions)

    def test_enter_starts_game(self):
        ready_title = self.make_ready()
        ready_title.on_key_press(K.RETURN, 0)
        self.assertIs(self.window.current_view, ready_title.game_view)

    def test_alt_enter_does_not_start_game(self):
        ready_title = self.make_ready()
        ready_title.on_key_press(K.RETURN, K.MOD_ALT)
        self.assertIs(self.window.current_view, ready_title)

    def test_instructions_and_back(self):
        ready_title = self.make_ready()
        ready_title.on_key_press(K.I, 0)
        view = self.window.current_view
        self.assertIsInstance(view, ict.InstructionsView)
        self.assertIs(view.title_view, ready_title)
        view.on_draw()
        view.on_key_press(K.SPACE, 0)
        self.assertIs(self.window.current_view, ready_title)

    def test_high_scores_and_back(self):
        self.no_throws()
        save_high_scores([("AAA", 30), ("BBB", 20), ("CCC", 10)])
        title = ict.TitleView()
        self.window.show_view(title)
        title.on_draw()
        title.on_update(1 / 60)
        title.on_key_press(K.H, 0)
        view = self.window.current_view
        self.assertIsInstance(view, ict.HighScoresView)
        self.assertEqual(view.high_scores_list, [("AAA", 30), ("BBB", 20), ("CCC", 10)])
        self.assertEqual(view.text_list[2].text, "High Scores:\nAAA - 30\nBBB - 20\nCCC - 10")
        view.on_draw()
        view.on_key_press(K.X, 0)
        self.assertIs(self.window.current_view, title)

    def test_escape_quits(self):
        ready_title = self.make_ready()
        closed = self.closed()
        ready_title.on_key_press(K.ESCAPE, 0)
        self.assertEqual(closed, [True])

    def test_other_keys_ignored(self):
        ready_title = self.make_ready()
        closed = self.closed()
        for key in (K.A, K.SPACE, K.P):
            ready_title.on_key_press(key, 0)
        self.assertIs(self.window.current_view, ready_title)
        self.assertFalse(closed)

    def test_draw_states(self):
        title = self.title
        title.on_draw()  # loading
        title.on_update(1 / 60)
        title.show_instructions = True
        title.on_draw()
        title.show_instructions = False
        title.on_draw()


class TestPauseView(GameViewTestCase):
    def test_pause_freezes_and_resumes(self):
        game_view, window = self.game_view, self.window
        game_view.score = 70
        h.press(game_view, K.P)
        pause = window.current_view
        self.assertIsInstance(pause, ict.PauseView)
        t, pos = game_view.game_timer, game_view.player.position
        h.tick(window, 5)
        self.assertEqual(game_view.game_timer, t)
        self.assertEqual(game_view.player.position, pos)
        pause.on_key_press(K.SPACE, 0)
        self.assertIs(window.current_view, pause)
        pause.on_key_press(K.ESCAPE, 0)
        self.assertIs(window.current_view, game_view)
        self.assertEqual(game_view.score, 70)
        h.tick(window, 1)
        self.assertGreater(game_view.game_timer, t)

    def test_p_unpauses(self):
        h.press(self.game_view, K.ESCAPE)
        self.window.current_view.on_key_press(K.P, 0)
        self.assertIs(self.window.current_view, self.game_view)


class TestGameOverView(GameViewTestCase):
    def test_enter_restarts(self):
        game_view, window = self.game_view, self.window
        game_view.score = 300
        game_view.player.lives = 1
        h.press(game_view, K.Q)
        over = window.current_view
        self.assertIsInstance(over, ict.GameOverView)
        over.on_draw()
        over.on_key_press(K.A, 0)
        self.assertIs(window.current_view, over)
        over.on_key_press(K.RETURN, 0)
        self.assertIs(window.current_view, game_view)
        self.assertEqual(game_view.score, 0)
        self.assertEqual(game_view.player.lives, 3)

    def test_escape_quits(self):
        closed = self.closed()
        h.press(self.game_view, K.Q)
        self.window.current_view.on_key_press(K.ESCAPE, 0)
        self.assertEqual(closed, [True])

    def test_shows_high_scores(self):
        self.game_view.high_scores_list = [("X", 3), ("Y", 2), ("Z", 1)]
        h.press(self.game_view, K.Q)
        texts = [t.text for t in self.window.current_view.text_list]
        self.assertIn("Game Over!", texts)
        self.assertIn("High Scores:\nX - 3\nY - 2\nZ - 1", texts)


class TestNewHighScoreView(GameViewTestCase):
    def setUp(self):
        super().setUp()
        self.game_view.score = 420
        self.entry = ict.NewHighScoreView(self.game_view)
        self.window.show_view(self.entry)

    def test_typing_name(self):
        entry = self.entry
        for key in (K.C, K.A, K.T):
            entry.on_key_press(key, 0)
        self.assertEqual(entry.new_name, "CAT")
        self.assertEqual(entry.text_list[-2].text, "CAT")
        entry.on_key_press(K.BACKSPACE, 0)
        self.assertEqual(entry.new_name, "CA")

    def test_name_limited_to_five_letters(self):
        for key in (K.A, K.B, K.C, K.D, K.E, K.F, K.G):
            self.entry.on_key_press(key, 0)
        self.assertEqual(self.entry.new_name, "ABCDE")

    def test_non_letters_ignored(self):
        entry = self.entry
        for key in (K.KEY_1, K.SPACE, K.LSHIFT, K.UP):
            entry.on_key_press(key, 0)
        self.assertEqual(entry.new_name, "")
        entry.on_key_press(K.BACKSPACE, 0)
        self.assertEqual(entry.new_name, "")

    def test_enter_saves_and_shows_game_over(self):
        entry, game_view = self.entry, self.game_view
        for key in (K.B, K.O):
            entry.on_key_press(key, 0)
        entry.on_key_press(K.RETURN, 0)
        self.assertEqual(load_high_scores(), [("BO", 420), ("???", 0), ("???", 0)])
        self.assertEqual(game_view.high_scores_list, [("BO", 420), ("???", 0), ("???", 0)])
        over = self.window.current_view
        self.assertIsInstance(over, ict.GameOverView)
        self.assertIs(over.game_view, game_view)
        self.assertIn("High Scores:\nBO - 420\n??? - 0\n??? - 0", [t.text for t in over.text_list])

    def test_escape_saves_with_empty_name(self):
        self.entry.on_key_press(K.Q, 0)
        self.entry.on_key_press(K.ESCAPE, 0)
        self.assertEqual(load_high_scores()[0], ("", 420))
        self.assertIsInstance(self.window.current_view, ict.GameOverView)


class TestDrawing(GameViewTestCase):
    def test_game_view_draw_with_everything(self):
        v = self.game_view
        v.on_draw()
        h.make_cat(v, 300, 300)
        h.make_popsicle(v, "lime", 1000, 400)
        h.make_heart(v, 1100, 400)
        v.poofs.append(v.player.poof())
        v.score, v.score_multiplier, v.score_multiplier_timer = 98765, 7, 5
        v.player.state.superpower.is_ready = True
        h.run_frames(v, 2)
        v.on_draw()
        self.assertEqual(len(v.score_sprites), 5)

    def test_every_player_cat_draws(self):
        for _ in range(3):
            self.game_view.on_draw()
            h.press(self.game_view, K.Z)
            h.run_frames(self.game_view, 1, dt=0.31)

    def test_overlays_draw_after_scroll(self):
        overlays = {
            "pause": ict.PauseView,
            "game_over": ict.GameOverView,
            "new_high_score": ict.NewHighScoreView,
        }
        for name, overlay_cls in overlays.items():
            with self.subTest(overlay=name):
                self.isolate()
                v = self.make_game_view()
                v.player.center_y = 1200
                v.scroll_viewport()
                self.assertGreater(v.view_bottom, 0)
                v.on_draw()
                view = overlay_cls(v)
                self.window.show_view(view)
                view.on_draw()


class TestStaticViewsDraw(TitleTestCase):
    def test_static_views_draw(self):
        ready_title = self.make_ready()
        for view in (ict.InstructionsView(ready_title), ict.HighScoresView(ready_title)):
            self.window.show_view(view)
            view.on_draw()


class TestWindow(GameTestCase):
    def test_window_enter_without_alt_keeps_windowed(self):
        self.window.on_key_press(K.ENTER, 0)
        self.assertFalse(self.window.fullscreen)


class TestTouchWording(GameViewTestCase):
    """The browser build names the on-screen buttons; desktop keeps the keyboard wording"""

    def wording(self, is_browser):
        """Prompt texts (and their shades) of every menu and overlay screen"""
        self.patch(game, "IN_BROWSER", is_browser)
        title = ict.TitleView()
        title.high_scores_list = load_high_scores()
        pause = ict.PauseView(self.game_view)
        return {
            "title": [title.blinking_text.text, title.blinking_shade.text],
            "instructions": [t.text for t in ict.InstructionsView(title).text_list],
            "high_scores": [t.text for t in ict.HighScoresView(title).text_list[4:]],
            "pause": [pause.pause_text.text, pause.pause_shade.text],
            "game_over": [t.text for t in ict.GameOverView(self.game_view).text_list[4:]],
            "name_entry": [t.text for t in ict.NewHighScoreView(self.game_view).text_list[2:4]],
        }

    def test_desktop_keeps_keyboard_wording(self):
        start = "'Enter' to Start\n'H' for High Scores\n'I' for Instructions\n'Esc' to quit"
        keys = "Move - LEFT/RIGHT\nJump - SPACE\nPounce - DOWN (running at full speed)\nSwitch Cat: Z\nSuper Power - lCtrl\n\nCollect as many popsicles as you can!"
        prompt = "Please Type in your name (up to 5 characters):"
        expected = {
            "title": [
                start,
                " 'Enter' to Start\n 'H' for High Scores\n 'I' for Instructions\n 'Esc' to quit",
            ],
            "instructions": ["Instructions / Keys", keys],
            "high_scores": ["Press any key", " Press any key"],
            "pause": [
                "PAUSED\nPRESS 'P' OR 'Esc' TO CONTINUE",
                " PAUSED\n PRESS 'P' OR 'Esc' TO CONTINUE",
            ],
            "game_over": [
                "'Enter' to restart\n'Esc' to exit",
                " 'Enter' to restart\n 'Esc' to exit",
            ],
            "name_entry": [prompt, f" {prompt}"],
        }
        self.assertEqual(self.wording(is_browser=False), expected)

    def test_browser_names_touch_buttons(self):
        moves = "Move - arrows\nJump - Jump\nPounce - down arrow (while running fast)\nSwitch Cat - cat\nSuper Power - star\n\nCollect as many popsicles as you can!"
        expected = {
            "title": ["Tap Play to start!", " Tap Play to start!"],
            "instructions": ["How to Play", moves],
            "high_scores": ["Tap Back to go back", " Tap Back to go back"],
            "pause": ["PAUSED\nTAP RESUME TO PLAY", " PAUSED\n TAP RESUME TO PLAY"],
            "game_over": ["Tap Play again!", " Tap Play again!"],
            "name_entry": ["Type your name, then tap Done", " Type your name, then tap Done"],
        }
        wording = self.wording(is_browser=True)
        self.assertEqual(wording, expected)
        all_text = "\n".join(text for texts in wording.values() for text in texts).lower()
        for keyboard_word in ("enter", "esc", "'", "space", "ctrl", "key", "quit", "exit"):
            self.assertNotIn(keyboard_word, all_text)
