"""Match the model in models/test_nn/ against the alpha-beta bot at a given level.

Usage:
    python -m area_43.compare --bot 1 --games 100
"""
import argparse
import glob
import os
import random

import numpy as np
import torch

from area_43.ai.encoder import ActionSpace, PLANES
from area_43.ai.net import TakNet
from area_43.ai import selfplay as sp

TEST_NN_DIR = os.path.join(os.path.dirname(__file__), "models", "test_nn")
SIZE = 5


def _load_net(path, action_space, device):
    blob = torch.load(path, map_location=device, weights_only=False)
    cfg = blob.get("config", {})
    net = TakNet(PLANES, SIZE, len(action_space),
                 cfg.get("channels", 128), cfg.get("blocks", 10)).to(device)
    net.load_state_dict(blob["net"])
    net.eval()
    return net


def main():
    ap = argparse.ArgumentParser(description="NN (test_nn/) vs alpha-beta bot")
    ap.add_argument("--bot", type=int, default=1,
                    help="bot difficulty level 1-10 (default 1)")
    ap.add_argument("--games", type=int, default=100,
                    help="number of games to play (default 100)")
    args = ap.parse_args()

    files = glob.glob(os.path.join(TEST_NN_DIR, "*.pt"))
    if not files:
        print(f"Error: no .pt file found in {TEST_NN_DIR}")
        return
    if len(files) > 1:
        print(f"Warning: multiple .pt files found, using {os.path.basename(files[0])}")
    model_path = files[0]
    model_name = os.path.basename(model_path)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    action_space = ActionSpace(SIZE)
    rng = np.random.default_rng()
    bot_rng = random.Random()

    print(f"Model  : {model_name}")
    print(f"Bot    : level {args.bot}")
    print(f"Games  : {args.games}")
    print(f"Playing: ", end="", flush=True)

    net = _load_net(model_path, action_space, device)

    wins = draws = losses = 0
    for g in range(args.games):
        net_player = g % 2
        _, winner = sp.play_game(net, action_space, 0, device, rng, bot_rng,
                                 vs_bot=True, bot_level=args.bot,
                                 net_player=net_player, net_search=False,
                                 open_random=2)
        if winner == net_player:
            wins += 1
        elif winner is None:
            draws += 1
        else:
            losses += 1
        if (g + 1) % 10 == 0:
            print(".", end="", flush=True)
    print()

    total = args.games
    print(f"\nResults vs level-{args.bot} bot ({total} games):")
    print(f"  {model_name}")
    print(f"  Wins   : {wins}  ({wins/total:.0%})")
    print(f"  Losses : {losses}  ({losses/total:.0%})")
    print(f"  Draws  : {draws}  ({draws/total:.0%})")


if __name__ == "__main__":
    main()
