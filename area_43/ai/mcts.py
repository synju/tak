"""PUCT Monte-Carlo tree search guided by the net (AlphaZero-style).

run() returns the root's visit-count distribution over the full action space,
which serves both as the policy training target and as the move-selection
policy. The net evaluates leaves; terminals use the true game result.
"""
import math
import numpy as np
import torch

from area_43.tak_level.tak_rules import generate_moves, apply_move
from area_43.tak_level.win_resolver import check_win_grid
from area_43.tak_level.tak_bot import _reserves_empty

C_PUCT = 1.5
DIRICHLET_ALPHA = 0.3
DIRICHLET_EPS = 0.25


class _Node:
    __slots__ = ("state", "to_move", "P", "N", "W", "children", "moves", "terminal")

    def __init__(self, state):
        self.state = state
        self.to_move = state.to_move
        self.P = None          # prior over legal moves (np array)
        self.N = None          # visit counts per legal move
        self.W = None          # total value per legal move
        self.children = None   # child _Node per legal move (lazy)
        self.moves = None      # legal move list (index-aligned with P/N/W)
        self.terminal = None   # (value, winner) once known, else None


def _winner_value(state, mover):
    """Outcome from `mover`'s perspective if terminal, else None."""
    outcome = check_win_grid(state.board, state.size, mover, _reserves_empty(state))
    if outcome is None:
        return None
    winner = outcome[1]
    if winner is None:
        return 0.0
    return 1.0 if winner == mover else -1.0


def _evaluate(node, net, encoder_fn, action_space, device, max_flats):
    """Expand node: net gives priors over its legal moves + a value estimate."""
    moves = generate_moves(node.state)
    node.moves = moves
    planes = encoder_fn(node.state, max_flats)
    x = torch.from_numpy(planes).unsqueeze(0).to(device)
    with torch.no_grad():
        logits, value = net(x)
    logits = logits[0].cpu().numpy()
    idx = np.array([action_space.move_index(m) for m in moves])
    masked = logits[idx]
    masked -= masked.max()
    priors = np.exp(masked)
    priors /= priors.sum()
    node.P = priors
    node.N = np.zeros(len(moves), dtype=np.float32)
    node.W = np.zeros(len(moves), dtype=np.float32)
    node.children = [None] * len(moves)
    return float(value.item())


def run(root_state, net, encoder_fn, action_space, sims, device,
        max_flats, rng, add_noise=True):
    """Run `sims` MCTS simulations; return visit counts over the action space."""
    root = _Node(root_state)
    root_value = _evaluate(root, net, encoder_fn, action_space, device, max_flats)
    if not root.moves:
        return np.zeros(len(action_space), dtype=np.float32)
    if add_noise:
        noise = rng.dirichlet([DIRICHLET_ALPHA] * len(root.moves))
        root.P = (1 - DIRICHLET_EPS) * root.P + DIRICHLET_EPS * noise

    for _ in range(sims):
        _simulate(root, net, encoder_fn, action_space, device, max_flats)

    counts = np.zeros(len(action_space), dtype=np.float32)
    for move, n in zip(root.moves, root.N):
        counts[action_space.move_index(move)] = n
    return counts


def _simulate(node, net, encoder_fn, action_space, device, max_flats):
    """One selection->expansion->backup pass; returns value for node.to_move."""
    # terminal check
    if node.terminal is None:
        node.terminal = _winner_value(node.state, node.to_move)
    if node.terminal is not None:
        return node.terminal

    total = node.N.sum()
    sqrt_total = math.sqrt(total) + 1e-8
    q = np.where(node.N > 0, node.W / np.maximum(node.N, 1), 0.0)
    u = C_PUCT * node.P * sqrt_total / (1.0 + node.N)
    a = int(np.argmax(q + u))

    child = node.children[a]
    if child is None:
        child = _Node(apply_move(node.state, node.moves[a]))
        node.children[a] = child
        child.terminal = _winner_value(child.state, child.to_move)
        if child.terminal is not None:
            value_child = child.terminal
        else:
            value_child = _evaluate(child, net, encoder_fn, action_space,
                                    device, max_flats)
    else:
        value_child = _simulate(child, net, encoder_fn, action_space,
                                device, max_flats)

    # child value is from the child's mover; node's mover is the opponent
    value = -value_child
    node.N[a] += 1
    node.W[a] += value
    return value
