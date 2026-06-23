from area_43.tak_level.tps import board_grid, FLAT, WALL, CAP


def _road_cells(grid, player):
    """Cells whose top piece counts toward a road for player (flats + capstones;
    walls do not form roads)."""
    cells = set()
    for cell, stack in grid.items():
        if not stack:
            continue
        owner, kind = stack[-1]
        if kind == WALL:
            continue
        if owner == player:
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


def _road_winner(grid, size, mover):
    """Winner by road, preferring the player who just moved on a double road."""
    roads = [p for p in (0, 1) if _has_road(_road_cells(grid, p), size)]
    if not roads:
        return None
    return mover if mover in roads else roads[0]


def _flat_counts(grid):
    counts = [0, 0]
    for stack in grid.values():
        if not stack:
            continue
        owner, kind = stack[-1]
        if kind == FLAT:  # only flat stones count; walls/capstones don't
            counts[owner] += 1
    return counts


def check_win_grid(grid, size, mover, reserves_empty):
    """Resolve a board given as an (owner, kind) grid.

    Returns ("road", winner) or ("flat", winner) where winner is 0, 1, or None
    (a flat-count tie), or None if the game continues.
    """
    winner = _road_winner(grid, size, mover)
    if winner is not None:
        return ("road", winner)

    occupied = sum(1 for s in grid.values() if s)
    if occupied >= size * size or reserves_empty:
        c0, c1 = _flat_counts(grid)
        if c0 > c1:
            return ("flat", 0)
        if c1 > c0:
            return ("flat", 1)
        return ("flat", None)  # draw
    return None


def check_win(board_stacks, size, mover, reserves_empty):
    """Live entry point: resolve from the scene's board_stacks of piece objects."""
    return check_win_grid(board_grid(board_stacks), size, mover, reserves_empty)
