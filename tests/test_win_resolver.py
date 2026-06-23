import unittest

from area_43.tak_level.tps import FLAT, WALL, CAP
from area_43.tak_level.win_resolver import check_win_grid

SIZE = 5


def flats_row(player, y):
    return {(x, y): [(player, FLAT)] for x in range(SIZE)}


def flats_col(player, x):
    return {(x, y): [(player, FLAT)] for y in range(SIZE)}


class RoadTests(unittest.TestCase):
    def test_horizontal_road(self):
        grid = flats_col(0, 0)  # column x=0 spans y... no — need left-right span
        # a horizontal road spans x=0..4 on some row
        grid = {(x, 2): [(0, FLAT)] for x in range(SIZE)}
        self.assertEqual(check_win_grid(grid, SIZE, 0, False), ("road", 0))

    def test_vertical_road(self):
        grid = {(2, y): [(1, FLAT)] for y in range(SIZE)}
        self.assertEqual(check_win_grid(grid, SIZE, 1, False), ("road", 1))

    def test_capstone_completes_road(self):
        grid = {(x, 0): [(0, FLAT)] for x in range(SIZE - 1)}
        grid[(SIZE - 1, 0)] = [(0, CAP)]
        self.assertEqual(check_win_grid(grid, SIZE, 0, False), ("road", 0))

    def test_wall_does_not_complete_road(self):
        grid = {(x, 0): [(0, FLAT)] for x in range(SIZE - 1)}
        grid[(SIZE - 1, 0)] = [(0, WALL)]  # wall breaks the road
        self.assertIsNone(check_win_grid(grid, SIZE, 0, False))

    def test_double_road_prefers_mover(self):
        # two parallel roads (no shared cell): both players have a road
        grid = {(x, 0): [(0, FLAT)] for x in range(SIZE)}
        grid.update({(x, SIZE - 1): [(1, FLAT)] for x in range(SIZE)})
        self.assertEqual(check_win_grid(grid, SIZE, 1, False), ("road", 1))
        self.assertEqual(check_win_grid(grid, SIZE, 0, False), ("road", 0))


class FlatWinTests(unittest.TestCase):
    def test_no_win_while_space_and_reserves_remain(self):
        grid = {(0, 0): [(0, FLAT)], (1, 0): [(1, FLAT)]}
        self.assertIsNone(check_win_grid(grid, SIZE, 0, False))

    def test_flat_win_when_reserves_empty(self):
        grid = {(0, 0): [(0, FLAT)], (1, 0): [(0, FLAT)], (2, 0): [(1, FLAT)]}
        self.assertEqual(check_win_grid(grid, SIZE, 1, True), ("flat", 0))

    def test_full_board_draw(self):
        grid = {}
        for i in range(SIZE * SIZE):
            x, y = i % SIZE, i // SIZE
            grid[(x, y)] = [(i % 2, FLAT)]  # but this makes a road... use checker
        # checkerboard avoids a road; equal flats -> draw
        grid = {(x, y): [((x + y) % 2, FLAT)] for x in range(SIZE) for y in range(SIZE)}
        # 5x5 checkerboard: 13 vs 12 -> majority wins, not a draw
        self.assertEqual(check_win_grid(grid, SIZE, 0, False), ("flat", 0))

    def test_walls_dont_count_for_flat_win(self):
        # board full, one player's tops are all walls -> other wins on flats
        grid = {}
        for x in range(SIZE):
            for y in range(SIZE):
                grid[(x, y)] = [(0, WALL)] if (x + y) % 2 == 0 else [(1, FLAT)]
        self.assertEqual(check_win_grid(grid, SIZE, 0, False), ("flat", 1))


if __name__ == "__main__":
    unittest.main()
