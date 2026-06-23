import random
import unittest

from area_43.tak_level.tps import FLAT, WALL, CAP
from area_43.tak_level.tak_rules import State, generate_moves
from area_43.tak_level.tak_bot import evaluate, choose_move, WIN

SIZE = 5


def state(board, to_move=0, stones=(21, 21), caps=(1, 1)):
    return State(board, SIZE, to_move, (True, True), stones, caps)


def almost_road(player):
    # flats on (0..3, 0); (4,0) empty -> one flat/cap there completes the road
    return {(x, 0): [(player, FLAT)] for x in range(SIZE - 1)}


class EvaluateTests(unittest.TestCase):
    def test_win_is_positive_for_winner(self):
        s = state({(x, 0): [(0, FLAT)] for x in range(SIZE)})
        self.assertEqual(evaluate(s, 0), WIN)
        self.assertEqual(evaluate(s, 1), -WIN)

    def test_more_flats_scores_higher(self):
        few = state({(0, 0): [(0, FLAT)]})
        many = state({(0, 0): [(0, FLAT)], (2, 2): [(0, FLAT)], (4, 4): [(0, FLAT)]})
        self.assertGreater(evaluate(many, 0), evaluate(few, 0))


class ChooseMoveTests(unittest.TestCase):
    def test_always_returns_legal_move_every_level(self):
        s = state(almost_road(0))
        legal = generate_moves(s)
        rng = random.Random(1)
        for level in range(1, 11):
            self.assertIn(choose_move(s, level, rng, time_budget=0.02), legal)

    def test_takes_the_winning_move(self):
        s = state(almost_road(0))
        rng = random.Random(0)
        # any depth >= 2 sees the 1-ply road completion at (4,0)
        for _ in range(8):
            move = choose_move(s, 5, rng, time_budget=0.1)
            self.assertEqual(move[1], (4, 0))
            self.assertIn(move[2], (FLAT, CAP))  # a wall would not complete a road

    def test_blocks_opponent_one_move_win(self):
        # opponent (1) threatens to complete a road at (4,0); bot (0) must block it
        s = state(almost_road(1), to_move=0)
        move = choose_move(s, 3, random.Random(0), time_budget=0.3)
        self.assertEqual(move[1], (4, 0))  # occupy the only winning square

    def test_no_moves_returns_none(self):
        s = state({}, stones=(0, 0), caps=(0, 0))
        self.assertIsNone(choose_move(s, 5))


class FullGameTests(unittest.TestCase):
    def test_bot_vs_bot_game_terminates(self):
        from area_43.tak_level.tak_rules import apply_move
        from area_43.tak_level.win_resolver import check_win_grid
        from area_43.tak_level.tak_bot import _reserves_empty
        rng = random.Random(7)
        s = State({}, SIZE, 0, (False, False), [20, 20], [1, 1])
        mover, outcome = None, None
        for _ in range(400):
            outcome = (None if mover is None else
                       check_win_grid(s.board, SIZE, mover, _reserves_empty(s)))
            if outcome is not None:
                break
            move = choose_move(s, 4, rng, time_budget=0.02)
            self.assertIsNotNone(move)
            mover = s.to_move
            s = apply_move(s, move)
        self.assertIsNotNone(outcome, "game did not terminate")


if __name__ == "__main__":
    unittest.main()
