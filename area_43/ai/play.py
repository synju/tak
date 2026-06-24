"""Load a trained net from a folder and use it as a live opponent (MCTS, no noise)."""
import glob
import os

import numpy as np
import torch

from area_43.ai.encoder import ActionSpace, encode, PLANES
from area_43.ai.net import TakNet
from area_43.ai import mcts
from area_43.ai.selfplay import MAX_FLATS

PLAY_SIMS = 200  # MCTS sims per move when playing a human


class NNOpponent:
    """A loaded net that picks moves for a live game via MCTS."""

    def __init__(self, path):
        blob = torch.load(path, map_location="cpu", weights_only=False)
        cfg = blob["config"]
        self.size = cfg["size"]
        self.action_space = ActionSpace(self.size)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.net = TakNet(PLANES, self.size, len(self.action_space),
                          cfg["channels"], cfg["blocks"]).to(self.device)
        self.net.load_state_dict(blob["net"])
        self.net.eval()
        self.rng = np.random.default_rng()
        self.name = os.path.basename(path)

    def choose_move(self, state):
        """Greedy on visit counts; no Dirichlet noise (that's for self-play only)."""
        counts = mcts.run(state, self.net, encode, self.action_space, PLAY_SIMS,
                          self.device, MAX_FLATS, self.rng, add_noise=False)
        if counts.sum() == 0:
            return None
        return self.action_space.moves[int(counts.argmax())]

    def policy_move(self, state):
        """Bare policy-head move: one forward pass, no MCTS (instant play)."""
        from area_43.ai import selfplay as sp
        return sp.policy_move(self.net, state, self.action_space, self.device,
                              MAX_FLATS)


def load_opponent(folder):
    """Load the .pt model in `folder` (newest wins if several). None if empty."""
    paths = sorted(glob.glob(os.path.join(folder, "*.pt")), key=os.path.getmtime)
    return NNOpponent(paths[-1]) if paths else None
