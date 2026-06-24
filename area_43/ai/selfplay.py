"""Generate training games. Two modes share one loop:
  - self-play: the net (with MCTS) plays both sides; every position is a sample.
  - vs-bot:    the net plays one side, the level-1 bot the other; only the
               net's own positions become samples.

A sample is (planes, pi, player): the encoded position, the MCTS visit-count
policy over the action space, and who moved. Values are filled in at game end
from each sample's mover's perspective.
"""
import numpy as np
import torch

from area_43.tak_level.tak_rules import State, generate_moves, apply_move
from area_43.tak_level.win_resolver import check_win_grid
from area_43.tak_level.tak_bot import _reserves_empty, choose_move as bot_move
from area_43.ai import mcts
from area_43.ai.encoder import encode

SIZE = 5
STONES = 21
CAPS = 1
MAX_FLATS = STONES
TEMP_MOVES = 12   # sample proportional to visits for the first N plies, then argmax


def new_game():
    return State({}, SIZE, 0, (False, False), [STONES, STONES], [CAPS, CAPS])


def _terminal_winner(state, mover):
    outcome = check_win_grid(state.board, SIZE, mover, _reserves_empty(state))
    return None if outcome is None else outcome[1]  # winner id, or None for draw/none


def _select(counts, ply, rng):
    """Pick an action index from visit counts (sampled early, greedy later)."""
    if ply < TEMP_MOVES and counts.sum() > 0:
        probs = counts / counts.sum()
        return int(rng.choice(len(counts), p=probs))
    return int(counts.argmax())


def _finish(samples, winner):
    """Attach value targets: +1/-1 from each sample-mover's perspective, 0 draw."""
    out = []
    for planes, pi, player in samples:
        z = 0.0 if winner is None else (1.0 if winner == player else -1.0)
        out.append((planes, pi, np.float32(z)))
    return out


def policy_move(net, state, action_space, device, max_flats):
    """Greedy move straight from the policy head: one forward pass, no search.
    This is how the net plays at deploy time (instant), so eval/gating use it."""
    moves = generate_moves(state)
    if not moves:
        return None
    x = torch.from_numpy(encode(state, max_flats)).unsqueeze(0).to(device)
    with torch.no_grad():
        logits, _ = net(x)
    logits = logits[0].cpu().numpy()
    idx = np.array([action_space.move_index(m) for m in moves])
    return moves[int(np.argmax(logits[idx]))]


def play_game(net, action_space, sims, device, rng, bot_rng=None,
              vs_bot=False, bot_level=1, net_player=0, max_plies=400,
              net_search=True, open_random=0):
    """Play one game; return (samples, winner). In vs_bot mode samples come only
    from the net's moves and `net_player` is the side the net controls.

    `net_search=False` makes the net move from its bare policy head (no MCTS) --
    used for eval, which measures deploy-time strength. `open_random` plies are
    random placements for variety (needed when search/noise is off).

    `rng` is a NumPy Generator (MCTS/self-play); `bot_rng` is a random.Random
    used only for the bot's tie-breaking in vs_bot mode."""
    state = new_game()
    samples = []
    mover = None
    for ply in range(max_plies):
        if mover is not None and _terminal_winner(state, mover) is not None or \
                not generate_moves(state):
            break
        if ply < open_random:                  # random opening plies for variety
            moves = generate_moves(state)
            move = moves[int(rng.integers(len(moves)))]
        else:
            net_turn = (not vs_bot) or state.to_move == net_player
            if net_turn and net_search:
                counts = mcts.run(state, net, encode, action_space, sims, device,
                                  MAX_FLATS, rng, add_noise=True)
                if counts.sum() == 0:
                    break
                samples.append((encode(state, MAX_FLATS),
                                counts / counts.sum(), state.to_move))
                move = action_space.moves[_select(counts, ply, rng)]
            elif net_turn:                     # no search: bare policy head
                move = policy_move(net, state, action_space, device, MAX_FLATS)
                if move is None:
                    break
            else:
                move = bot_move(state, bot_level, bot_rng)
                if move is None:
                    break
        mover = state.to_move
        state = apply_move(state, move)

    winner = None if mover is None else _terminal_winner(state, mover)
    return _finish(samples, winner), winner
