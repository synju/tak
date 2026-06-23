"""A Tak bot: alpha-beta minimax, iterative deepening, transposition table.

Difficulty 1..10 indexes a LADDER of (target depth, beam width, time budget).
Higher levels search deeper and wider with more time, so strength climbs from
trivial to as hard as this pure-Python engine reaches (a strong tactical bot,
not literally unbeatable). The transposition table caches positions reached by
different move orders -- the main lever that lets the search go deep in time.
The opponent is assumed to play its own best reply at every ply.
"""
import random
import time

from area_43.tak_level.tak_rules import generate_moves, apply_move
from area_43.tak_level.win_resolver import check_win_grid, _road_cells, _flat_counts

WIN = 100000
INF = float("inf")

# Transposition-table entry flags (value is exact / a lower bound / an upper bound).
EXACT, LOWER, UPPER = 0, 1, 2
TT_LIMIT = 2_000_000  # cap stored entries to bound memory


class _TimeUp(Exception):
    """Raised to abort a search pass that exceeded its deadline."""


def _reserves_empty(state):
    return any(state.stones[p] == 0 and state.caps[p] == 0 for p in (0, 1))


def _largest_cc(cells):
    """Size of the largest orthogonally-connected group of cells."""
    cells = set(cells)
    seen, best = set(), 0
    for start in cells:
        if start in seen:
            continue
        size, frontier = 0, [start]
        seen.add(start)
        while frontier:
            x, y = frontier.pop()
            size += 1
            for nb in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if nb in cells and nb not in seen:
                    seen.add(nb)
                    frontier.append(nb)
        best = max(best, size)
    return best


def evaluate(state, player):
    """Score `state` from player's view; assumes `player` just moved."""
    outcome = check_win_grid(state.board, state.size, player, _reserves_empty(state))
    if outcome is not None:
        _, winner = outcome
        if winner == player:
            return WIN
        if winner is None:
            return 0
        return -WIN
    flats = _flat_counts(state.board)
    flat_diff = flats[player] - flats[1 - player]
    road = (_largest_cc(_road_cells(state.board, player))
            - _largest_cc(_road_cells(state.board, 1 - player)))
    return flat_diff + 0.5 * road


def _score(state, mover, root, depth):
    """One pass: (value-from-root, is_terminal). Prefers fast wins / slow losses."""
    outcome = check_win_grid(state.board, state.size, mover, _reserves_empty(state))
    if outcome is not None:
        winner = outcome[1]
        if winner is None:
            return 0, True
        return ((WIN + depth) if winner == root else -(WIN + depth)), True
    flats = _flat_counts(state.board)
    road = (_largest_cc(_road_cells(state.board, root))
            - _largest_cc(_road_cells(state.board, 1 - root)))
    return (flats[root] - flats[1 - root]) + 0.5 * road, False


def _order_score(state, mover, root, depth):
    """Cheap (value, is_terminal) for internal-node ordering. Same terminal
    detection as _score, but skips the road flood-fill -- its non-terminal
    value only orders moves, so a flat-diff proxy is enough and far cheaper."""
    outcome = check_win_grid(state.board, state.size, mover, _reserves_empty(state))
    if outcome is not None:
        winner = outcome[1]
        if winner is None:
            return 0, True
        return ((WIN + depth) if winner == root else -(WIN + depth)), True
    flats = _flat_counts(state.board)
    return (flats[root] - flats[1 - root]), False


def _key(state):
    """Canonical hashable key for the transposition table."""
    board = tuple(sorted(
        (cell, tuple(stack)) for cell, stack in state.board.items() if stack))
    return (board, state.to_move, tuple(state.opening_done),
            tuple(state.stones), tuple(state.caps))


def _leaf(state, root):
    """Value of a depth-1 node: best static score over one ply (terminals incl.)."""
    moves = generate_moves(state)
    if not moves:
        return evaluate(state, root)
    maximizing = state.to_move == root
    best = -INF if maximizing else INF
    for move in moves:
        value, _ = _score(apply_move(state, move), state.to_move, root, 1)
        best = max(best, value) if maximizing else min(best, value)
    return best


def _minimax(state, depth, alpha, beta, root, deadline, tt, beam):
    if time.monotonic() >= deadline:
        raise _TimeUp
    if depth == 1:
        return _leaf(state, root)

    alpha_orig, beta_orig = alpha, beta
    key = _key(state)
    entry = tt.get(key)
    tt_move = None
    if entry is not None:
        e_depth, e_val, e_flag, tt_move = entry
        if e_depth >= depth:
            if e_flag == EXACT:
                return e_val
            if e_flag == LOWER:
                alpha = max(alpha, e_val)
            else:  # UPPER
                beta = min(beta, e_val)
            if alpha >= beta:
                return e_val

    moves = generate_moves(state)
    if not moves:
        return evaluate(state, root)
    maximizing = state.to_move == root

    # Apply + statically score every child; order best-first (the cached best
    # move first) so alpha-beta prunes hard, then search the top `beam`.
    children = []
    for move in moves:
        child = apply_move(state, move)
        value, terminal = _order_score(child, state.to_move, root, depth)
        children.append((value, terminal, child, move))
    children.sort(key=lambda c: c[0], reverse=maximizing)
    if tt_move is not None:
        for i in range(len(children)):
            if children[i][3] == tt_move:
                children.insert(0, children.pop(i))
                break

    best = -INF if maximizing else INF
    best_move = children[0][3]
    for value, terminal, child, move in children[:beam]:
        if not terminal:
            value = _minimax(child, depth - 1, alpha, beta, root, deadline, tt, beam)
        if maximizing:
            if value > best:
                best, best_move = value, move
            alpha = max(alpha, best)
        else:
            if value < best:
                best, best_move = value, move
            beta = min(beta, best)
        if alpha >= beta:
            break

    if len(tt) < TT_LIMIT:
        if best <= alpha_orig:
            flag = UPPER
        elif best >= beta_orig:
            flag = LOWER
        else:
            flag = EXACT
        tt[key] = (depth, best, flag, best_move)
    return best


# Difficulty ladder: (target depth in plies, beam width, time budget seconds).
# Calibrated so strength climbs smoothly to the hardest this engine reaches.
LADDER = [
    (2, 4, 0.5),    # 1  trivial
    (3, 4, 1.0),    # 2  depth 3
    (3, 6, 2.0),    # 3  depth 3, wider
    (4, 6, 4.0),    # 4  depth 4
    (4, 8, 7.0),    # 5  depth 4, wider
    (5, 6, 11.0),   # 6  depth 5
    (5, 8, 16.0),   # 7  depth 5, wider
    (6, 6, 22.0),   # 8  depth 6
    (6, 8, 27.0),   # 9  depth 6, wider
    (7, 6, 30.0),   # 10 depth 7 -- hardest this engine reaches in time
]

# Adaptive early-exit: stop deepening once the answer is clear, so easy
# positions resolve fast and only hard ones spend the full budget (moderate).
EASY_MIN_DEPTH = 3   # search at least this deep before any early exit
EASY_MARGIN = 2.0    # best must lead 2nd-best by this (eval units) to bail


def choose_move(state, level, rng=None, time_budget=None):
    """Pick a move for state.to_move. Difficulty (1..10) selects from LADDER.

    Iterative-deepening alpha-beta over all root moves, capped by the level's
    time budget. The transposition table is shared across passes so deeper
    iterations reuse earlier work. Search exits early on trivial positions
    (one move / an immediate win) and on a stable, dominant best move.
    """
    rng = rng or random
    moves = generate_moves(state)
    if not moves:
        return None
    if len(moves) == 1:
        return moves[0]
    root = state.to_move
    target_depth, beam, budget = LADDER[max(1, min(level, len(LADDER))) - 1]
    if time_budget is not None:
        budget = time_budget

    deadline = time.monotonic() + budget
    tt = {}
    # Order root moves by a 1-ply score (improves pruning); reordered each pass.
    scored = [[evaluate(apply_move(state, m), root), m] for m in moves]
    scored.sort(key=lambda sm: sm[0], reverse=True)
    if scored[0][0] >= WIN:  # a move wins outright -- take it, skip deepening
        return rng.choice([m for value, m in scored if value >= WIN])

    best_move = scored[0][1]
    prev_best = None
    for depth in range(2, target_depth + 1):
        try:
            # Full window per root move so each gets its EXACT value (not an
            # alpha-beta bound); subtrees still prune internally.
            for entry in scored:
                move = entry[1]
                child = apply_move(state, move)
                value, terminal = _order_score(child, root, root, depth)
                entry[0] = value if terminal else _minimax(
                    child, depth - 1, -INF, INF, root, deadline, tt, beam)
        except _TimeUp:
            break  # incomplete pass: keep best_move from the last full depth
        scored.sort(key=lambda sm: sm[0], reverse=True)
        best = scored[0][0]
        best_move = rng.choice([m for value, m in scored if value == best])
        if best >= WIN:
            break  # forced win found -- no deeper search can improve on it
        second = scored[1][0] if len(scored) > 1 else -INF
        stable = best_move == prev_best  # same choice two depths running
        prev_best = best_move
        if depth >= EASY_MIN_DEPTH and stable and (best - second) >= EASY_MARGIN:
            break  # easy move: stable and clearly ahead, deeper search won't help
        if time.monotonic() >= deadline:
            break
    return best_move
