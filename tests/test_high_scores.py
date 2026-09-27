"""High-score persistence (helper) and the new-high-score ranking logic (NewHighScoreView)."""

import pickle
import sys
from types import SimpleNamespace
from unittest import mock

import game_constants as game
import helper
from helper import load_high_scores, save_high_scores

import ice_cream_truck as ict
from tests.support import GameTestCase

DEFAULT = [("???", 0)] * 3


class TestPersistence(GameTestCase):
    def test_load_defaults_when_file_missing(self):
        self.assertFalse(self.high_scores_file.exists())
        self.assertEqual(load_high_scores(), DEFAULT)
        self.assertFalse(self.high_scores_file.exists())  # loading does not create the file

    def test_save_then_load_roundtrip(self):
        scores = [("ANN", 300), ("BOB", 200), ("CAT", 100)]
        save_high_scores(scores)
        self.assertTrue(self.high_scores_file.exists())
        self.assertEqual(load_high_scores(), scores)

    def test_file_is_a_pickled_list(self):
        save_high_scores([("A", 3), ("B", 2), ("C", 1)])
        with open(self.high_scores_file, "rb") as f:
            self.assertEqual(pickle.load(f), [("A", 3), ("B", 2), ("C", 1)])

    def test_save_overwrites(self):
        save_high_scores([("A", 3), ("B", 2), ("C", 1)])
        save_high_scores([("Z", 9), ("Y", 8), ("X", 7)])
        self.assertEqual(load_high_scores(), [("Z", 9), ("Y", 8), ("X", 7)])


def _rank(current, name, score):
    """Run NewHighScoreView.update_high_scores against a minimal game view"""
    game_view = SimpleNamespace(score=score, high_scores_list=list(current))
    view = ict.NewHighScoreView(game_view)
    view.new_name = name
    view.update_high_scores()
    return game_view.high_scores_list


class TestRanking(GameTestCase):
    def test_ranking_keeps_top_three(self):
        cases = [
            (DEFAULT, "ABC", 50, [("ABC", 50), ("???", 0), ("???", 0)]),
            (
                [("A", 300), ("B", 200), ("C", 100)],
                "NEW",
                250,
                [("A", 300), ("NEW", 250), ("B", 200)],
            ),
            (
                [("A", 300), ("B", 200), ("C", 100)],
                "TOP",
                999,
                [("TOP", 999), ("A", 300), ("B", 200)],
            ),
            (
                [("A", 300), ("B", 200), ("C", 100)],
                "LOW",
                150,
                [("A", 300), ("B", 200), ("LOW", 150)],
            ),
            # equal scores are ordered by name, descending
            ([("A", 300), ("B", 200), ("C", 100)], "Z", 200, [("A", 300), ("Z", 200), ("B", 200)]),
            ([("A", 300), ("M", 200), ("C", 100)], "B", 200, [("A", 300), ("M", 200), ("B", 200)]),
        ]
        for current, name, score, expected in cases:
            with self.subTest(current=current, name=name, score=score):
                self.isolate()
                self.assertEqual(_rank(current, name, score), expected)

    def test_ranking_is_saved_to_file(self):
        ranked = _rank(DEFAULT, "ME", 10)
        self.assertTrue(load_high_scores() == ranked == [("ME", 10), ("???", 0), ("???", 0)])

    def test_empty_name_is_allowed(self):
        self.assertEqual(_rank(DEFAULT, "", 10)[0], ("", 10))


class FakeLocalStorage:
    """Dict-backed stand-in for the browser's localStorage"""

    def __init__(self):
        self.items = {}

    def getItem(self, key):
        return self.items.get(key)

    def setItem(self, key, value):
        self.items[key] = str(value)


class TestBrowserPersistence(GameTestCase):
    def setUp(self):
        super().setUp()
        self.storage = FakeLocalStorage()
        self.key = str(self.high_scores_file)
        self.patch(game, "IN_BROWSER", True)
        patcher = mock.patch.dict(sys.modules, js=SimpleNamespace(localStorage=self.storage))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_load_defaults_when_nothing_stored(self):
        self.assertEqual(load_high_scores(), DEFAULT)
        self.assertEqual(self.storage.items, {})

    def test_save_then_load_roundtrip(self):
        scores = [("ANN", 300), ("BOB", 200), ("CAT", 100)]
        save_high_scores(scores)
        self.assertEqual(load_high_scores(), scores)
        self.assertFalse(self.high_scores_file.exists())  # nothing written to the filesystem

    def test_stored_as_json_under_one_key(self):
        save_high_scores([("A", 3), ("B", 2), ("C", 1)])
        self.assertEqual(self.storage.items, {self.key: '[["A", 3], ["B", 2], ["C", 1]]'})

    def test_load_defaults_when_corrupt(self):
        for stored in ["", "not json", "{", "5", "[1, 2]", "null"]:
            with self.subTest(stored=stored):
                self.storage.items[self.key] = stored
                self.assertEqual(load_high_scores(), DEFAULT)

    def test_blocked_storage_falls_back_without_crashing(self):
        class BlockedJs:
            @property
            def localStorage(self):
                raise RuntimeError("SecurityError: Access is denied for this document.")

        with mock.patch.dict(sys.modules, js=BlockedJs()):  # as when the browser denies storage
            save_high_scores([("A", 3), ("B", 2), ("C", 1)])
            self.assertEqual(load_high_scores(), DEFAULT)
        self.assertFalse(self.high_scores_file.exists())

    def test_ranking_is_saved_to_storage(self):
        ranked = _rank(DEFAULT, "ME", 10)
        self.assertTrue(load_high_scores() == ranked == [("ME", 10), ("???", 0), ("???", 0)])
