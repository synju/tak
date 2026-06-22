import unittest

from area_43.tak_level.tps import (
    FLAT, WALL, CAP, _digit, square_tps, board_tps, to_tps,
    count_pieces, format_state,
)

SIZE = 5


class DigitTests(unittest.TestCase):
    def test_owner_to_tps_player(self):
        self.assertEqual(_digit(1), "1")  # white -> 1
        self.assertEqual(_digit(0), "2")  # black -> 2


class SquareTests(unittest.TestCase):
    def test_empty_is_none(self):
        self.assertIsNone(square_tps([]))

    def test_single_flat(self):
        self.assertEqual(square_tps([(1, FLAT)]), "1")
        self.assertEqual(square_tps([(0, FLAT)]), "2")

    def test_wall_and_cap_suffix_on_top_only(self):
        self.assertEqual(square_tps([(0, WALL)]), "2S")
        self.assertEqual(square_tps([(1, CAP)]), "1C")

    def test_stack_bottom_to_top_with_top_suffix(self):
        # white flat (bottom), black wall (top)
        self.assertEqual(square_tps([(1, FLAT), (0, WALL)]), "12S")
        # black, white, black capstone on top
        self.assertEqual(square_tps([(0, FLAT), (1, FLAT), (0, CAP)]), "212C")


class BoardTests(unittest.TestCase):
    def test_empty_board(self):
        self.assertEqual(board_tps({}, SIZE), "x5/x5/x5/x5/x5")

    def test_bottom_left_flat_is_last_row_first_column(self):
        # (0,0) is the near-left corner -> last row, first column
        self.assertEqual(board_tps({(0, 0): [(1, FLAT)]}, SIZE),
                         "x5/x5/x5/x5/1,x4")

    def test_far_row_written_first(self):
        # (0,4) is the far-left corner -> first row
        self.assertEqual(board_tps({(0, 4): [(0, FLAT)]}, SIZE),
                         "2,x4/x5/x5/x5/x5")

    def test_empty_run_compression_mid_row(self):
        grid = {(0, 0): [(1, FLAT)], (4, 0): [(0, FLAT)]}
        self.assertEqual(board_tps(grid, SIZE), "x5/x5/x5/x5/1,x3,2")

    def test_mixed_row_with_stack_and_suffix(self):
        # matches the shape of the documented example: x3,<stack>,x
        grid = {(3, 4): [(1, FLAT), (0, WALL)]}
        self.assertEqual(board_tps(grid, SIZE).split("/")[0], "x3,12S,x")


class FullTpsTests(unittest.TestCase):
    def test_empty_game_start(self):
        self.assertEqual(to_tps({}, SIZE, 1, 1), '[TPS "x5/x5/x5/x5/x5 1 1"]')

    def test_side_to_move_and_move_number(self):
        self.assertEqual(to_tps({}, SIZE, 0, 7), '[TPS "x5/x5/x5/x5/x5 2 7"]')


class CountTests(unittest.TestCase):
    def test_counts_by_owner_and_kind(self):
        cells = [(1, FLAT)] * 18 + [(1, CAP)] + [(0, FLAT)] * 19 + [(0, CAP)]
        self.assertEqual(count_pieces(cells), {0: (19, 1), 1: (18, 1)})

    def test_empty_counts(self):
        self.assertEqual(count_pieces([]), {0: (0, 0), 1: (0, 0)})


class FormatStateTests(unittest.TestCase):
    def test_full_text_state(self):
        reserve = [(1, FLAT)] * 18 + [(1, CAP)] + [(0, FLAT)] * 19 + [(0, CAP)]
        text = format_state({(0, 0): [(1, FLAT)]}, SIZE, 0, 3, reserve)
        self.assertEqual(
            text,
            '[TPS "x5/x5/x5/x5/1,x4 2 3"]\n'
            'reserves: 1=18/1 2=19/1',
        )


if __name__ == "__main__":
    unittest.main()
