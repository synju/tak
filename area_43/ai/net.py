"""Dual-head convolutional ResNet: shared trunk -> policy logits + value.

Input:  (batch, PLANES, size, size)
Policy: (batch, action_size) raw logits (mask before softmax)
Value:  (batch,) in [-1, 1] (tanh), position value for the side to move.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F


class _ResBlock(nn.Module):
    def __init__(self, ch):
        super().__init__()
        self.c1 = nn.Conv2d(ch, ch, 3, padding=1, bias=False)
        self.b1 = nn.BatchNorm2d(ch)
        self.c2 = nn.Conv2d(ch, ch, 3, padding=1, bias=False)
        self.b2 = nn.BatchNorm2d(ch)

    def forward(self, x):
        y = F.relu(self.b1(self.c1(x)))
        y = self.b2(self.c2(y))
        return F.relu(x + y)


class TakNet(nn.Module):
    def __init__(self, planes, size, action_size, channels=64, blocks=5):
        super().__init__()
        self.size = size
        self.stem = nn.Sequential(
            nn.Conv2d(planes, channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(channels), nn.ReLU())
        self.res = nn.Sequential(*[_ResBlock(channels) for _ in range(blocks)])
        # policy head
        self.p_conv = nn.Sequential(
            nn.Conv2d(channels, 32, 1, bias=False), nn.BatchNorm2d(32), nn.ReLU())
        self.p_fc = nn.Linear(32 * size * size, action_size)
        # value head
        self.v_conv = nn.Sequential(
            nn.Conv2d(channels, 32, 1, bias=False), nn.BatchNorm2d(32), nn.ReLU())
        self.v_fc = nn.Sequential(
            nn.Linear(32 * size * size, 256), nn.ReLU(), nn.Linear(256, 1), nn.Tanh())

    def forward(self, x):
        x = self.res(self.stem(x))
        p = self.p_fc(self.p_conv(x).flatten(1))
        v = self.v_fc(self.v_conv(x).flatten(1)).squeeze(1)
        return p, v
