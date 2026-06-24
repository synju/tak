"""Champion gating: a challenger net must beat the stored champion head-to-head
before it replaces it. train.py runs this whenever the net clears 50% vs level-1.

Each game randomizes the opening placements for variety, then both nets play
greedily (argmax visit counts, no noise) so the result reflects pure strength.
"""
import torch

from area_43.tak_level.tak_rules import generate_moves, apply_move
from area_43.tak_level.win_resolver import check_win_grid
from area_43.tak_level.tak_bot import _reserves_empty
from area_43.ai.encoder import encode, PLANES
from area_43.ai.net import TakNet
from area_43.ai import mcts
from area_43.ai import selfplay as sp


def _winner(state, mover):
    outcome = check_win_grid(state.board, state.size, mover, _reserves_empty(state))
    return None if outcome is None else outcome[1]


def play_match_game(nets, action_space, sims, device, max_flats, rng,
                    open_random=2, max_plies=400):
    """One game; nets[p] plays player p. The first `open_random` plies are random
    placements (variety); the rest are each net's greedy move. Returns winner id."""
    state = sp.new_game()
    mover = None
    for ply in range(max_plies):
        if mover is not None and _winner(state, mover) is not None:
            break
        moves = generate_moves(state)
        if not moves:
            break
        if ply < open_random:
            move = moves[int(rng.integers(len(moves)))]
        else:
            counts = mcts.run(state, nets[state.to_move], encode, action_space,
                              sims, device, max_flats, rng, add_noise=False)
            if counts.sum() == 0:
                break
            move = action_space.moves[int(counts.argmax())]
        mover = state.to_move
        state = apply_move(state, move)
    return None if mover is None else _winner(state, mover)


def _load_net(path, action_space, device):
    blob = torch.load(path, map_location=device, weights_only=False)
    cfg = blob["config"]
    net = TakNet(PLANES, cfg["size"], len(action_space),
                 cfg["channels"], cfg["blocks"]).to(device)
    net.load_state_dict(blob["net"])
    net.eval()
    return net


def gate(challenger, champion_path, action_space, sims, device, max_flats, rng,
         games=100):
    """Play `games` between challenger and the saved champion, alternating colors
    so first-move advantage cancels. Returns (challenger_wins, draws)."""
    champion = _load_net(champion_path, action_space, device)
    challenger.eval()
    wins = draws = 0
    print("  gating vs champion: ", end="", flush=True)
    for g in range(games):
        if g % 2 == 0:
            nets, chal = (challenger, champion), 0  # challenger plays black
        else:
            nets, chal = (champion, challenger), 1  # challenger plays white
        w = play_match_game(nets, action_space, sims, device, max_flats, rng)
        if w is None:
            draws += 1
        elif w == chal:
            wins += 1
        if (g + 1) % 10 == 0:
            print(".", end="", flush=True)
    print()
    return wins, draws
