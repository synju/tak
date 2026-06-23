"""Pure Tak rules over a plain data state (no Panda3D): legal move generation
and move application. Used by the bot to think, and as the canonical rules.

State.board: dict (x, y) -> [(owner, kind), ...] bottom..top (empty cells absent).
Moves:
  ("place", (x, y), kind)            kind in FLAT/WALL/CAP; owner is implicit
  ("spread", (x, y), (dx, dy), counts)  counts[i] pieces dropped on the i-th cell
"""
from area_43.tak_level.tps import FLAT, WALL, CAP

DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class State:
    def __init__(self, board, size, to_move, opening_done, stones, caps):
        self.board = board
        self.size = size
        self.to_move = to_move
        self.opening_done = list(opening_done)  # [bool, bool]
        self.stones = list(stones)              # own-colour flats left [p0, p1]
        self.caps = list(caps)                  # capstones left [p0, p1]

    def copy(self):
        return State(
            {cell: list(stack) for cell, stack in self.board.items()},
            self.size, self.to_move, self.opening_done, self.stones, self.caps,
        )


def empty_cells(state):
    occupied = {cell for cell, stack in state.board.items() if stack}
    return [(x, y) for x in range(state.size) for y in range(state.size)
            if (x, y) not in occupied]


def _compositions(n, max_parts):
    """All ordered positive compositions of n with 1..max_parts parts."""
    out = []

    def rec(remaining, current):
        if remaining == 0:
            out.append(list(current))
            return
        if len(current) == max_parts:
            return
        for first in range(1, remaining + 1):
            current.append(first)
            rec(remaining - first, current)
            current.pop()

    rec(n, [])
    return out


def _legal_spread(state, hand, cells, counts):
    """Can `hand` (bottom..top) be dropped as `counts` over `cells`?"""
    idx, last = 0, len(counts) - 1
    for i, (cell, cnt) in enumerate(zip(cells, counts)):
        stack = state.board.get(cell)
        top = stack[-1] if stack else None
        dropped = hand[idx:idx + cnt]
        if top is not None:
            kind = top[1]
            if kind == CAP:
                return False
            if kind == WALL:
                # only a lone capstone, as the final drop, flattens a wall
                if not (i == last and cnt == 1 and dropped[-1][1] == CAP):
                    return False
        idx += cnt
    return True


def _spread_moves(state, player):
    moves = []
    carry_limit = state.size
    for cell, stack in state.board.items():
        if not stack or stack[-1][0] != player:
            continue
        max_take = min(len(stack), carry_limit)
        for take in range(1, max_take + 1):
            hand = stack[-take:]  # bottom..top of carried subset
            for d in DIRS:
                line = []
                cx, cy = cell
                for _ in range(take):  # at most one piece per cell
                    cx, cy = cx + d[0], cy + d[1]
                    if not (0 <= cx < state.size and 0 <= cy < state.size):
                        break
                    line.append((cx, cy))
                for counts in _compositions(take, len(line)):
                    if _legal_spread(state, hand, line[:len(counts)], counts):
                        moves.append(("spread", cell, d, counts))
    return moves


def generate_moves(state):
    p = state.to_move
    if not state.opening_done[p]:
        # opening: place the odd (opponent) flat on any empty cell
        return [("place", cell, FLAT) for cell in empty_cells(state)]

    moves = []
    for cell in empty_cells(state):
        if state.stones[p] > 0:
            moves.append(("place", cell, FLAT))
            moves.append(("place", cell, WALL))
        if state.caps[p] > 0:
            moves.append(("place", cell, CAP))
    moves.extend(_spread_moves(state, p))
    return moves


def apply_move(state, move):
    s = state.copy()
    p = s.to_move
    if move[0] == "place":
        _, cell, kind = move
        if not s.opening_done[p]:
            s.board.setdefault(cell, []).append((1 - p, FLAT))  # opponent-coloured
            s.opening_done[p] = True
        else:
            s.board.setdefault(cell, []).append((p, kind))
            if kind == CAP:
                s.caps[p] -= 1
            else:
                s.stones[p] -= 1
    else:
        _, origin, d, counts = move
        take = sum(counts)
        stack = s.board[origin]
        hand = stack[-take:]
        del stack[-take:]
        if not stack:
            del s.board[origin]
        idx = 0
        cx, cy = origin
        for cnt in counts:
            cx, cy = cx + d[0], cy + d[1]
            dest = s.board.setdefault((cx, cy), [])
            for owner, kind in hand[idx:idx + cnt]:
                if dest and dest[-1][1] == WALL and kind == CAP:
                    dest[-1] = (dest[-1][0], FLAT)  # capstone flattens wall
                dest.append((owner, kind))
            idx += cnt
    s.to_move = 1 - p
    return s
