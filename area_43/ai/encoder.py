"""Encode a Tak State into NN tensor planes, and map moves <-> a fixed action
space. Both are built for one board size (default 5). Planes are written from
the side-to-move's perspective so the net is colour-agnostic.

Planes (C = 11, each size x size):
  0  my top flat        3  opp top flat
  1  my top wall        4  opp top wall
  2  my top cap         5  opp top cap
  6  stack height / size
  7  my reserve flats / max_flats      8  my reserve caps (0/1)
  9  opp reserve flats / max_flats    10  opp reserve caps (0/1)
"""
import numpy as np

from area_43.tak_level.tps import FLAT, WALL, CAP
from area_43.tak_level.tak_rules import DIRS, _compositions

PLANES = 11
KINDS = (FLAT, WALL, CAP)


class ActionSpace:
    """Fixed enumeration of every conceivable move on a `size` board, so the
    policy head has a constant width. Illegal moves are masked each turn."""

    def __init__(self, size=5):
        self.size = size
        moves = []
        for x in range(size):
            for y in range(size):
                for kind in KINDS:
                    moves.append(("place", (x, y), kind))
        for x in range(size):
            for y in range(size):
                for d in DIRS:
                    for take in range(1, size + 1):
                        for counts in _compositions(take, take):
                            moves.append(("spread", (x, y), d, tuple(counts)))
        self.moves = moves
        self.index = {self._key(m): i for i, m in enumerate(moves)}

    def __len__(self):
        return len(self.moves)

    @staticmethod
    def _key(move):
        # normalise lists/tuples so generated and enumerated moves match
        if move[0] == "place":
            return ("place", tuple(move[1]), move[2])
        return ("spread", tuple(move[1]), tuple(move[2]), tuple(move[3]))

    def move_index(self, move):
        return self.index[self._key(move)]

    def legal_mask(self, legal_moves):
        """Boolean mask (len = action space) marking the given legal moves."""
        mask = np.zeros(len(self.moves), dtype=bool)
        for m in legal_moves:
            mask[self.index[self._key(m)]] = True
        return mask


def encode(state, max_flats):
    """State -> float32 array (PLANES, size, size), side-to-move perspective."""
    size = state.size
    me = state.to_move
    planes = np.zeros((PLANES, size, size), dtype=np.float32)
    for (x, y), stack in state.board.items():
        if not stack:
            continue
        owner, kind = stack[-1]
        mine = owner == me
        base = 0 if mine else 3
        planes[base + KINDS.index(kind), x, y] = 1.0
        planes[6, x, y] = min(len(stack), size) / size
    planes[7].fill(state.stones[me] / max_flats)
    planes[8].fill(float(state.caps[me] > 0))
    planes[9].fill(state.stones[1 - me] / max_flats)
    planes[10].fill(float(state.caps[1 - me] > 0))
    return planes
