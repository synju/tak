"""Headless AlphaZero-style trainer for Tak.

  venv/bin/python -m area_43.train

Phase 1 (bootstrap): the net plays the level-1 bot. Once its win-rate vs
level-1 clears WIN_THRESHOLD it switches to Phase 2 (pure self-play).

Resumable: each save writes a new timestamped area_43/models/model_YYMMDD_HHMMSS.pt
(net + optimizer + iteration + phase + replay buffer + RNG) -- never overwriting.
Re-running resumes from the most recent one; Ctrl-C saves first, so you can stop
and continue any time.

Note: training data is local game state only -- no sensitive information.
"""
import argparse
import concurrent.futures as cf
import glob
import multiprocessing as mp
import os
import pickle
import random
from collections import deque
from datetime import datetime

import numpy as np
import torch
import torch.nn.functional as F

from area_43.ai.encoder import ActionSpace, PLANES
from area_43.ai.net import TakNet
from area_43.ai import selfplay as sp
from area_43.ai import arena

# --- config ----------------------------------------------------------------
SIZE = sp.SIZE
CHANNELS, BLOCKS = 128, 10
SIMS = 400                 # MCTS simulations per move (override with --sims)
GAMES_PER_ITER = 10        # games generated each iteration
TRAIN_STEPS = 40           # gradient steps per iteration
BATCH = 128
BUFFER = 40_000            # replay buffer capacity (samples)
LR = 1e-3
EVAL_EVERY = 5             # iterations between win-rate evals vs level-1
EVAL_GAMES = 20
WIN_THRESHOLD = 0.60       # switch bootstrap -> self-play at this win-rate
SAVE_EVERY = 1             # checkpoint every N iterations
KEEP_CHECKPOINTS = 2       # keep only the newest N; older ones are pruned on save
GATE_GAMES = 100           # challenger-vs-champion match length (fires at >=50% vs level-1)
PROMOTE_WINS = 55          # challenger must win this many of GATE_GAMES to take over
# next to this file (area_43/models), independent of the current directory
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
PROGRESS = os.path.join(MODELS_DIR, "progress.txt")
ARCHIVE_DIR = os.path.join(MODELS_DIR, "archive")  # champion + counter, never pruned
CHAMPION = os.path.join(ARCHIVE_DIR, "nn_lvl_1_bot.pt")  # reigning best (overwritten on promotion)
COUNTER = os.path.join(ARCHIVE_DIR, "counter.txt")       # log of seeds + replacements


def _log(msg):
    """Print to console and append a timestamped copy to progress.txt."""
    print(msg)
    os.makedirs(MODELS_DIR, exist_ok=True)
    with open(PROGRESS, "a") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg.strip()}\n")


def _latest_ckpt():
    """Most recent model_*.pt in MODELS_DIR (by mtime), or None."""
    paths = glob.glob(os.path.join(MODELS_DIR, "model_*.pt"))
    return max(paths, key=os.path.getmtime) if paths else None


def _prune(keep):
    """Delete all but the newest `keep` model_*.pt checkpoints in MODELS_DIR.

    Non-recursive: only checkpoints directly in MODELS_DIR are touched, so
    backups kept elsewhere (e.g. area_43/backups/) are never affected."""
    paths = sorted(glob.glob(os.path.join(MODELS_DIR, "model_*.pt")),
                   key=os.path.getmtime)
    for old in paths[:-keep] if keep > 0 else paths:
        try:
            os.remove(old)
        except OSError:
            pass


def _champion_path():
    """Path to the reigning champion, or None if none has been crowned yet."""
    return CHAMPION if os.path.exists(CHAMPION) else None


def _write_champion(net, it, wr):
    """Save the current net as the champion (play-only: just net + config)."""
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    tmp = CHAMPION + ".tmp"
    torch.save({"net": net.state_dict(),
                "config": {"channels": CHANNELS, "blocks": BLOCKS, "size": SIZE},
                "iteration": it, "win_rate": wr, "label": "lvl_1_bot"}, tmp)
    os.replace(tmp, CHAMPION)


def _count_replacements():
    """How many times the champion has been replaced (from counter.txt)."""
    if not os.path.exists(COUNTER):
        return 0
    with open(COUNTER) as f:
        return sum(1 for line in f if "replacement #" in line)


def _counter_line(msg):
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    with open(COUNTER, "a") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}\n")


def _save(net, opt, it, phase, buffer):
    """Write a new timestamped checkpoint (never overwrites). Returns its path."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    blob = {
        "net": net.state_dict(),
        "opt": opt.state_dict(),
        "iteration": it,
        "phase": phase,
        "buffer": pickle.dumps(list(buffer)),
        "rng_py": random.getstate(),
        "rng_np": np.random.get_state(),
        "rng_torch": torch.get_rng_state(),
        "config": {"channels": CHANNELS, "blocks": BLOCKS, "size": SIZE},
    }
    path = os.path.join(MODELS_DIR, datetime.now().strftime("model_%y%m%d_%H%M%S.pt"))
    tmp = path + ".tmp"
    torch.save(blob, tmp)
    os.replace(tmp, path)  # atomic: a crash mid-save can't corrupt the checkpoint
    _prune(KEEP_CHECKPOINTS)
    return path


def _load(path, net, opt):
    blob = torch.load(path, map_location="cpu", weights_only=False)
    net.load_state_dict(blob["net"])
    opt.load_state_dict(blob["opt"])
    random.setstate(blob["rng_py"])
    np.random.set_state(blob["rng_np"])
    torch.set_rng_state(blob["rng_torch"])
    buffer = deque(pickle.loads(blob["buffer"]), maxlen=BUFFER)
    return blob["iteration"], blob["phase"], buffer


def _train_steps(net, opt, buffer, device):
    if len(buffer) < BATCH:
        return None
    net.train()
    last = 0.0
    for _ in range(TRAIN_STEPS):
        batch = random.sample(buffer, BATCH)
        planes = torch.from_numpy(np.stack([b[0] for b in batch])).to(device)
        pi = torch.from_numpy(np.stack([b[1] for b in batch])).to(device)
        z = torch.from_numpy(np.stack([b[2] for b in batch])).to(device)
        logits, v = net(planes)
        p_loss = -(pi * F.log_softmax(logits, dim=1)).sum(1).mean()
        v_loss = F.mse_loss(v, z)
        loss = p_loss + v_loss
        opt.zero_grad()
        loss.backward()
        opt.step()
        last = float(loss.item())
    net.eval()
    return last


def _evaluate(net, action_space, device, rng, bot_rng, games):
    """Win-rate of the net vs the level-1 bot over `games` (no MCTS noise)."""
    wins = 0.0
    for g in range(games):
        net_player = g % 2  # alternate colours
        _, winner = sp.play_game(net, action_space, SIMS, device, rng, bot_rng,
                                 vs_bot=True, bot_level=1, net_player=net_player)
        if winner == net_player:
            wins += 1.0
        elif winner is None:
            wins += 0.5
    return wins / games


def _str2bool(v):
    s = str(v).strip().lower()
    if s in ("true", "1", "yes", "y", "t"):
        return True
    if s in ("false", "0", "no", "n", "f"):
        return False
    raise argparse.ArgumentTypeError("expected True/False")


# --- parallel self-play workers --------------------------------------------
# Each worker is a game GENERATOR only: it holds a copy of the net, is handed
# fresh weights each iteration, plays games, and returns samples. The single
# trainer owns all learning + checkpointing. Net arch comes via initargs (not
# module globals) so it is correct under 'spawn', which re-imports this module.
_WK = {}


def _worker_setup(size, planes, channels, blocks):
    # 1 torch thread per worker: parallelism comes from the processes, not from
    # intra-op threads -- otherwise N workers x all-cores thrash the CPU.
    torch.set_num_threads(1)
    a = ActionSpace(size)
    net = TakNet(planes, size, len(a), channels, blocks)
    net.eval()
    _WK["a"], _WK["net"] = a, net


def _worker_play_one(args):
    """Play ONE game with the given weights; return its samples."""
    weights, phase, sims, seed, net_player = args
    net, a = _WK["net"], _WK["a"]
    net.load_state_dict(weights)
    rng = np.random.default_rng(seed)
    bot_rng = random.Random(seed)
    if phase == "bootstrap":
        samples, _ = sp.play_game(net, a, sims, "cpu", rng, bot_rng,
                                  vs_bot=True, bot_level=1, net_player=net_player)
    else:
        samples, _ = sp.play_game(net, a, sims, "cpu", rng, bot_rng)
    return samples


def _gen_parallel(executor, net, games, phase, rng):
    """Generate `games` games (one task each) across the pool; tick per game."""
    weights = {k: v.detach().cpu() for k, v in net.state_dict().items()}
    futs = [executor.submit(_worker_play_one,
                            (weights, phase, SIMS, int(rng.integers(1 << 31)), g % 2))
            for g in range(games)]
    samples = []
    for fut in cf.as_completed(futs):
        samples.extend(fut.result())
        print(".", end="", flush=True)  # one dot per finished game (console only)
    return samples


def main():
    global SIMS
    ap = argparse.ArgumentParser(description="Headless Tak self-play trainer")
    ap.add_argument("--games", type=int, default=GAMES_PER_ITER,
                    help=f"games per iteration (default {GAMES_PER_ITER})")
    ap.add_argument("--iterations", type=int, default=None,
                    help="iterations to run this invocation (default: until Ctrl-C)")
    ap.add_argument("--selfplay", type=_str2bool, default=None, metavar="True/False",
                    help="force self-play (True) or bootstrap vs level-1 (False); "
                         "omit for automatic bootstrap->self-play")
    ap.add_argument("--eval", type=_str2bool, default=True, metavar="True/False",
                    help="run periodic win-rate eval vs level-1 (default True)")
    ap.add_argument("--parallel", type=_str2bool, default=False, metavar="True/False",
                    help="generate self-play games in parallel worker processes")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1),
                    help="worker processes when --parallel True")
    ap.add_argument("--sims", type=int, default=SIMS,
                    help=f"MCTS simulations per move (default {SIMS})")
    args = ap.parse_args()
    games_per_iter = args.games
    SIMS = args.sims

    device = "cuda" if torch.cuda.is_available() else "cpu"
    action_space = ActionSpace(SIZE)
    net = TakNet(PLANES, SIZE, len(action_space), CHANNELS, BLOCKS).to(device)
    opt = torch.optim.Adam(net.parameters(), lr=LR, weight_decay=1e-4)

    ckpt = _latest_ckpt()
    if ckpt:
        it, phase, buffer = _load(ckpt, net, opt)
        _log(f"resumed from {os.path.basename(ckpt)}: iter {it}, phase {phase}, "
             f"{len(buffer)} samples")
    else:
        it, phase, buffer = 0, "bootstrap", deque(maxlen=BUFFER)
        _log(f"fresh start on {device}, action space {len(action_space)}")

    # --selfplay forces the phase for this run and disables the auto-switch
    auto_switch = args.selfplay is None
    if args.selfplay is not None:
        phase = "selfplay" if args.selfplay else "bootstrap"
        _log(f"phase forced to {phase} (--selfplay {args.selfplay})")

    rng = np.random.default_rng()
    bot_rng = random.Random()
    net.eval()

    executor = None
    if args.parallel:
        executor = cf.ProcessPoolExecutor(
            max_workers=args.workers, mp_context=mp.get_context("spawn"),
            initializer=_worker_setup, initargs=(SIZE, PLANES, CHANNELS, BLOCKS))
        _log(f"parallel self-play: {args.workers} workers")

    remaining = args.iterations  # None => run until interrupted
    try:
        while remaining is None or remaining > 0:
            it += 1
            if remaining is not None:
                remaining -= 1
            # live feedback during the (slow) game-generation phase (console only)
            where = f" on {args.workers} workers" if executor else ""
            print(f"iter {it} generating {games_per_iter} games{where}: ",
                  end="", flush=True)
            if executor is not None:
                samples = _gen_parallel(executor, net, games_per_iter, phase, rng)
                buffer.extend(samples)
                new = len(samples)
            else:
                new = 0
                for g in range(games_per_iter):
                    if phase == "bootstrap":
                        samples, _ = sp.play_game(
                            net, action_space, SIMS, device, rng, bot_rng,
                            vs_bot=True, bot_level=1, net_player=g % 2)
                    else:
                        samples, _ = sp.play_game(
                            net, action_space, SIMS, device, rng, bot_rng)
                    buffer.extend(samples)
                    new += len(samples)
                    print(".", end="", flush=True)  # one dot per finished game
            print()  # end the dots line
            loss = _train_steps(net, opt, buffer, device)
            _log(f"iter {it} [{phase}]  +{new} samples  buffer {len(buffer)}  "
                 f"loss {loss if loss is None else round(loss, 3)}")

            if args.eval and it % EVAL_EVERY == 0:
                wr = _evaluate(net, action_space, device, rng, bot_rng, EVAL_GAMES)
                _log(f"  eval vs level-1: {wr:.0%}")
                if wr >= 0.50:  # good enough to seed / challenge the champion
                    champ = _champion_path()
                    if champ is None:
                        _write_champion(net, it, wr)
                        _counter_line(f"seeded champion at iter {it} "
                                      f"(vs level-1 {wr:.0%})")
                        _log(f"  >>> seeded champion (iter {it}, vs level-1 {wr:.0%})")
                    else:
                        wins, draws = arena.gate(net, champ, action_space, SIMS,
                                                 device, sp.MAX_FLATS, rng, GATE_GAMES)
                        if wins >= PROMOTE_WINS:
                            n = _count_replacements() + 1
                            _write_champion(net, it, wr)
                            _counter_line(f"replacement #{n}: challenger won "
                                          f"{wins}/{GATE_GAMES} (draws {draws}) "
                                          f"at iter {it}")
                            _log(f"  >>> NEW CHAMPION #{n}: won {wins}/{GATE_GAMES} "
                                 f"(draws {draws})")
                        else:
                            _log(f"  >>> champion kept: challenger won "
                                 f"{wins}/{GATE_GAMES} (draws {draws})")
                if auto_switch and phase == "bootstrap" and wr >= WIN_THRESHOLD:
                    phase = "selfplay"
                    _log(f"  >>> reached {wr:.0%} -- switching to self-play")

            if it % SAVE_EVERY == 0:
                _save(net, opt, it, phase, buffer)
        # bounded run finished normally
        path = _save(net, opt, it, phase, buffer)
        _log(f"done: ran {args.iterations} iterations (total iter {it}, "
             f"phase {phase}). saved {os.path.basename(path)}. re-run to continue.")
    except KeyboardInterrupt:
        _log("interrupted -- saving checkpoint...")
        path = _save(net, opt, it, phase, buffer)
        _log(f"saved {os.path.basename(path)} (iter {it}, phase {phase}). "
             f"re-run to resume.")
    finally:
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)


if __name__ == "__main__":
    main()
