import unittest

import numpy as np

from area_43.tak_level.tps import FLAT, WALL, CAP
from area_43.tak_level.tak_rules import State, generate_moves
from area_43.ai.encoder import ActionSpace, encode, PLANES

SIZE = 5
MAX_FLATS = 21


def state(board, to_move=0, opening=(True, True), stones=(21, 21), caps=(1, 1)):
    return State(board, SIZE, to_move, opening, stones, caps)


class ActionSpaceTests(unittest.TestCase):
    def setUp(self):
        self.A = ActionSpace(SIZE)

    def test_size_is_placements_plus_spreads(self):
        # 25 cells * 3 kinds + 25 cells * 4 dirs * (2^0+2^1+..+2^4) patterns
        self.assertEqual(len(self.A), 25 * 3 + 25 * 4 * 31)

    def test_every_generated_move_has_a_unique_index(self):
        # spread-heavy mid-game position
        s = state({(2, 2): [(0, FLAT), (0, FLAT), (1, FLAT)],
                   (1, 1): [(0, CAP)], (3, 3): [(1, WALL)]})
        moves = generate_moves(s)
        idxs = [self.A.move_index(m) for m in moves]
        self.assertEqual(len(idxs), len(set(idxs)))         # all distinct
        self.assertTrue(all(0 <= i < len(self.A) for i in idxs))

    def test_legal_mask_matches_generated_moves(self):
        s = state({(2, 2): [(0, FLAT)]})
        moves = generate_moves(s)
        mask = self.A.legal_mask(moves)
        self.assertEqual(int(mask.sum()), len(moves))
        for m in moves:
            self.assertTrue(mask[self.A.move_index(m)])


class EncodeTests(unittest.TestCase):
    def test_shape_and_perspective(self):
        s = state({(0, 0): [(0, FLAT)], (4, 4): [(1, CAP)]}, to_move=0)
        p = encode(s, MAX_FLATS)
        self.assertEqual(p.shape, (PLANES, SIZE, SIZE))
        self.assertEqual(p[0, 0, 0], 1.0)   # my (p0) flat at (0,0)
        self.assertEqual(p[5, 4, 4], 1.0)   # opp (p1) cap at (4,4)

    def test_perspective_flips_with_side_to_move(self):
        board = {(0, 0): [(0, FLAT)]}
        as_p0 = encode(state(board, to_move=0), MAX_FLATS)
        as_p1 = encode(state(board, to_move=1), MAX_FLATS)
        self.assertEqual(as_p0[0, 0, 0], 1.0)   # p0's piece is "mine" for p0
        self.assertEqual(as_p1[3, 0, 0], 1.0)   # ...and "opponent's" for p1

    def test_reserve_planes_normalised(self):
        p = encode(state({}, stones=(21, 10), caps=(1, 0), to_move=0), MAX_FLATS)
        self.assertAlmostEqual(p[7, 0, 0], 1.0)        # my flats 21/21
        self.assertAlmostEqual(p[9, 0, 0], 10 / 21)    # opp flats 10/21
        self.assertEqual(p[8, 0, 0], 1.0)              # my caps > 0
        self.assertEqual(p[10, 0, 0], 0.0)             # opp caps == 0


if __name__ == "__main__":
    unittest.main()
