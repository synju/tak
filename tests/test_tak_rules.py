import unittest

from area_43.tak_level.tps import FLAT, WALL, CAP
from area_43.tak_level.tak_rules import (
    State, generate_moves, apply_move, empty_cells, _spread_moves,
)

SIZE = 5


def fresh(board=None, to_move=0, opening_done=(True, True),
          stones=(21, 21), caps=(1, 1)):
    return State(board or {}, SIZE, to_move, opening_done, stones, caps)


class OpeningTests(unittest.TestCase):
    def test_opening_only_flat_placements_on_empties(self):
        s = fresh(opening_done=(False, True))
        moves = generate_moves(s)
        self.assertEqual(len(moves), SIZE * SIZE)
        self.assertTrue(all(m == ("place", m[1], FLAT) for m in moves))

    def test_opening_places_opponent_colour_and_advances(self):
        s = fresh(to_move=0, opening_done=(False, False))
        s2 = apply_move(s, ("place", (2, 2), FLAT))
        self.assertEqual(s2.board[(2, 2)], [(1, FLAT)])  # opponent colour
        self.assertTrue(s2.opening_done[0])
        self.assertEqual(s2.to_move, 1)
        self.assertEqual(s2.stones, [21, 21])  # opening doesn't spend a stone


class PlacementTests(unittest.TestCase):
    def test_placement_counts_on_empty_board(self):
        moves = generate_moves(fresh())
        # 25 empties * (flat + wall + cap), no spreads on an empty board
        self.assertEqual(len(moves), SIZE * SIZE * 3)

    def test_no_stones_means_caps_only(self):
        moves = generate_moves(fresh(stones=(0, 0)))
        self.assertTrue(all(m[2] == CAP for m in moves))
        self.assertEqual(len(moves), SIZE * SIZE)

    def test_no_caps_means_no_cap_moves(self):
        moves = generate_moves(fresh(caps=(0, 0)))
        self.assertTrue(all(m[2] in (FLAT, WALL) for m in moves))

    def test_apply_placement_spends_pieces(self):
        s = fresh(stones=(21, 21), caps=(1, 1))
        self.assertEqual(apply_move(s, ("place", (0, 0), FLAT)).stones, [20, 21])
        self.assertEqual(apply_move(s, ("place", (0, 0), CAP)).caps, [0, 1])


class SpreadGenTests(unittest.TestCase):
    def test_simple_two_high_stack(self):
        s = fresh(board={(0, 0): [(0, FLAT), (0, FLAT)]})
        spreads = set((m[2], tuple(m[3])) for m in _spread_moves(s, 0))
        self.assertEqual(spreads, {
            ((1, 0), (1,)), ((0, 1), (1,)),          # carry 1
            ((1, 0), (2,)), ((0, 1), (2,)),          # carry 2, all on first cell
            ((1, 0), (1, 1)), ((0, 1), (1, 1)),      # carry 2, spread over two cells
        })

    def test_cannot_control_opponent_top(self):
        s = fresh(board={(0, 0): [(0, FLAT), (1, FLAT)]})
        self.assertEqual(_spread_moves(s, 0), [])

    def test_carry_limit_is_board_size(self):
        s = fresh(board={(0, 0): [(0, FLAT)] * 7})
        self.assertTrue(_spread_moves(s, 0))
        self.assertTrue(all(sum(m[3]) <= SIZE for m in _spread_moves(s, 0)))


class WallCapTests(unittest.TestCase):
    def test_flat_cannot_drop_on_wall(self):
        s = fresh(board={(0, 0): [(0, FLAT)], (1, 0): [(1, WALL)]})
        toward_wall = [m for m in _spread_moves(s, 0) if m[2] == (1, 0)]
        self.assertEqual(toward_wall, [])

    def test_lone_capstone_flattens_wall(self):
        s = fresh(board={(0, 0): [(0, CAP)], (1, 0): [(1, WALL)]})
        move = ("spread", (0, 0), (1, 0), [1])
        self.assertIn(move, _spread_moves(s, 0))
        s2 = apply_move(s, move)
        self.assertEqual(s2.board[(1, 0)], [(1, FLAT), (0, CAP)])  # wall -> flat, cap on top
        self.assertNotIn((0, 0), s2.board)  # origin emptied

    def test_cannot_drop_on_capstone(self):
        s = fresh(board={(0, 0): [(0, FLAT)], (1, 0): [(1, CAP)]})
        toward_cap = [m for m in _spread_moves(s, 0) if m[2] == (1, 0)]
        self.assertEqual(toward_cap, [])


class ApplySpreadTests(unittest.TestCase):
    def test_three_piece_spread_keeps_order(self):
        s = fresh(board={(0, 0): [(0, FLAT), (1, FLAT), (0, CAP)]})
        s2 = apply_move(s, ("spread", (0, 0), (1, 0), [1, 1, 1]))
        self.assertNotIn((0, 0), s2.board)
        self.assertEqual(s2.board[(1, 0)], [(0, FLAT)])   # bottom dropped first
        self.assertEqual(s2.board[(2, 0)], [(1, FLAT)])
        self.assertEqual(s2.board[(3, 0)], [(0, CAP)])    # original top dropped last
        self.assertEqual(s2.to_move, 1)


if __name__ == "__main__":
    unittest.main()
