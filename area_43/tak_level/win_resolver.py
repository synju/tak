from area_43.tak_level.flat import Flat
from area_43.tak_level.wall import Wall
from area_43.tak_level.capstone import Capstone


def _owner(piece):
    """0 = black/gold, 1 = white/silver."""
    c = tuple(piece.color)
    if c in (Flat.BLACK, Capstone.GOLD):
        return 0
    if c in (Flat.WHITE, Capstone.SILVER):
        return 1
    return None


def _road_cells(board_stacks, player):
    """Cells whose top piece counts toward a road for player (flats + capstones;
    walls do not form roads)."""
    cells = set()
    for cell, stack in board_stacks.items():
        if not stack:
            continue
        top = stack[-1]
        if isinstance(top, Wall):
            continue
        if _owner(top) == player:
            cells.add(cell)
    return cells


def _has_road(cells, size):
    """True if cells form an unbroken orthogonal path between opposite edges."""
    for horizontal in (True, False):
        starts = [c for c in cells if (c[0] == 0 if horizontal else c[1] == 0)]
        seen = set(starts)
        frontier = list(starts)
        while frontier:
            x, y = frontier.pop()
            if (x == size - 1) if horizontal else (y == size - 1):
                return True
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) in cells and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    frontier.append((nx, ny))
    return False


def _road_winner(board_stacks, size, mover):
    """Winner by road, preferring the player who just moved on a double road."""
    roads = [p for p in (0, 1) if _has_road(_road_cells(board_stacks, p), size)]
    if not roads:
        return None
    return mover if mover in roads else roads[0]


def _flat_counts(board_stacks):
    counts = [0, 0]
    for stack in board_stacks.values():
        if not stack:
            continue
        top = stack[-1]
        if isinstance(top, Flat):  # only flat stones count; walls/capstones don't
            counts[_owner(top)] += 1
    return counts


def check_win(board_stacks, size, mover, reserves_empty):
    """Resolve the board after a move.

    Returns ("road", winner) or ("flat", winner) where winner is 0, 1, or None
    (a flat-count tie), or None if the game continues.
    """
    winner = _road_winner(board_stacks, size, mover)
    if winner is not None:
        return ("road", winner)

    occupied = sum(1 for s in board_stacks.values() if s)
    if occupied >= size * size or reserves_empty:
        c0, c1 = _flat_counts(board_stacks)
        if c0 > c1:
            return ("flat", 0)
        if c1 > c0:
            return ("flat", 1)
        return ("flat", None)  # draw
    return None
