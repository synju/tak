"""Head-to-head match between two saved models.

Drop exactly two .pt files into area_43/models/duel/, then run:

    python -m area_43.duel --games 100
"""
import argparse
import glob
import os

import numpy as np
import torch

from area_43.ai.encoder import ActionSpace, PLANES
from area_43.ai.net import TakNet
from area_43.ai import selfplay as sp
from area_43.tak_level.tak_rules import generate_moves, apply_move
from area_43.tak_level.win_resolver import check_win_grid
from area_43.tak_level.tak_bot import _reserves_empty

DUEL_DIR = os.path.join(os.path.dirname(__file__), "models", "duel")
SIZE = 5


def _load_net(path, action_space, device):
    blob = torch.load(path, map_location=device, weights_only=False)
    cfg = blob.get("config", {})
    channels = cfg.get("channels", 128)
    blocks   = cfg.get("blocks",   10)
    net = TakNet(PLANES, SIZE, len(action_space), channels, blocks).to(device)
    net.load_state_dict(blob["net"])
    net.eval()
    return net


def _winner(state, mover):
    outcome = check_win_grid(state.board, state.size, mover, _reserves_empty(state))
    return None if outcome is None else outcome[1]


def _play_game(nets, action_space, device, rng, open_random=2, max_plies=400):
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
            move = sp.policy_move(nets[state.to_move], state, action_space,
                                  device, sp.MAX_FLATS)
            if move is None:
                break
        mover = state.to_move
        state = apply_move(state, move)
    return None if mover is None else _winner(state, mover)


def main():
    ap = argparse.ArgumentParser(description="Duel two models from models/duel/")
    ap.add_argument("--games", type=int, default=100,
                    help="number of games to play (default 100)")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(DUEL_DIR, "*.pt")))
    if len(files) != 2:
        print(f"Error: expected exactly 2 .pt files in {DUEL_DIR}, found {len(files)}.")
        return

    device = "cuda" if torch.cuda.is_available() else "cpu"
    action_space = ActionSpace(SIZE)
    rng = np.random.default_rng()

    name_a = os.path.basename(files[0])
    name_b = os.path.basename(files[1])

    print(f"Loading models...")
    print(f"  A: {name_a}")
    print(f"  B: {name_b}")
    net_a = _load_net(files[0], action_space, device)
    net_b = _load_net(files[1], action_space, device)

    wins_a = wins_b = draws = 0
    print(f"\nPlaying {args.games} games: ", end="", flush=True)
    for g in range(args.games):
        if g % 2 == 0:
            nets = (net_a, net_b)
            w = _play_game(nets, action_space, device, rng)
            if w == 0:   wins_a += 1
            elif w == 1: wins_b += 1
            else:        draws  += 1
        else:
            nets = (net_b, net_a)
            w = _play_game(nets, action_space, device, rng)
            if w == 0:   wins_b += 1
            elif w == 1: wins_a += 1
            else:        draws  += 1
        if (g + 1) % 10 == 0:
            print(".", end="", flush=True)
    print()

    print(f"\nResults ({args.games} games):")
    print(f"  {name_a}: {wins_a} wins")
    print(f"  {name_b}: {wins_b} wins")
    print(f"  Draws   : {draws}")

    if wins_a > wins_b:
        print(f"\nChampion: {name_a}")
    elif wins_b > wins_a:
        print(f"\nChampion: {name_b}")
    else:
        print(f"\nDraw — no champion (tied at {wins_a} each)")


if __name__ == "__main__":
    main()
