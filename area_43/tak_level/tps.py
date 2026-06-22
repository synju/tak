"""Tak Positional System (TPS) serialisation of the board + game state.

The canonical intermediate is a *grid*: a dict mapping board cell (x, y) to a
stack of (owner, kind) tuples, bottom -> top. owner is 0 (black) or 1 (white);
kind is "flat", "wall" or "cap". Pure formatting works on that grid so it stays
testable without Panda3D; thin adapters convert the live piece objects into it.

TPS numbers players 1 (white) and 2 (black). The board is written rows-first
from the far edge (y = size-1) down, columns left to right.
"""

FLAT, WALL, CAP = "flat", "wall", "cap"


def _digit(owner):
    # our owner: 0 black, 1 white -> TPS: 1 white, 2 black
    return "1" if owner == 1 else "2"


def square_tps(stack):
    """TPS for one square's stack, or None if empty."""
    if not stack:
        return None
    s = "".join(_digit(owner) for owner, _ in stack)
    kind = stack[-1][1]  # only the top piece carries a type suffix
    if kind == WALL:
        s += "S"
    elif kind == CAP:
        s += "C"
    return s


def board_tps(grid, size):
    """Board portion of TPS: rows from y = size-1 down, columns left to right."""
    rows = []
    for y in range(size - 1, -1, -1):
        cells, empties = [], 0
        for x in range(size):
            sq = square_tps(grid.get((x, y)))
            if sq is None:
                empties += 1
                continue
            if empties:
                cells.append("x" if empties == 1 else f"x{empties}")
                empties = 0
            cells.append(sq)
        if empties:
            cells.append("x" if empties == 1 else f"x{empties}")
        rows.append(",".join(cells))
    return "/".join(rows)


def to_tps(grid, size, to_move, move_number):
    """Full bracketed TPS string."""
    return f'[TPS "{board_tps(grid, size)} {_digit(to_move)} {move_number}"]'


def count_pieces(cells):
    """Per-player reserve counts from (owner, kind) cells -> {owner: (flats, caps)}."""
    counts = {0: [0, 0], 1: [0, 0]}
    for owner, kind in cells:
        counts[owner][1 if kind == CAP else 0] += 1
    return {p: (c[0], c[1]) for p, c in counts.items()}


def format_state(grid, size, to_move, move_number, reserve_cells):
    """Full text state: the TPS line plus a reserve line (flats/caps per player)."""
    counts = count_pieces(reserve_cells)
    f1, c1 = counts[1]  # white = TPS player 1
    f2, c2 = counts[0]  # black = TPS player 2
    return (f"{to_tps(grid, size, to_move, move_number)}\n"
            f"reserves: 1={f1}/{c1} 2={f2}/{c2}")


# --- live game adapters (import the piece classes lazily so the pure formatter
#     above stays importable without Panda3D) ---------------------------------

def piece_cell(piece):
    """(owner, kind) for a live piece object."""
    from area_43.tak_level.wall import Wall
    from area_43.tak_level.capstone import Capstone
    from area_43.tak_level.win_resolver import _owner
    if isinstance(piece, Wall):
        kind = WALL
    elif isinstance(piece, Capstone):
        kind = CAP
    else:
        kind = FLAT
    return (_owner(piece), kind)


def board_grid(board_stacks):
    """Live board_stacks -> grid of (owner, kind) stacks (empty cells dropped)."""
    return {cell: [piece_cell(p) for p in stack]
            for cell, stack in board_stacks.items() if stack}


def reserve_cells(reserves):
    """Flatten the reserves' pieces into (owner, kind) cells."""
    return [piece_cell(p) for reserve in reserves for p in reserve.pieces]


def game_state_text(board_stacks, size, to_move, move_number, reserves):
    """Full text state straight from the live game objects."""
    return format_state(board_grid(board_stacks), size, to_move, move_number,
                        reserve_cells(reserves))
