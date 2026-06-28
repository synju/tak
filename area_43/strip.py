"""Strip a full training checkpoint down to weights-only (deploy-ready).

Full checkpoints include the replay buffer, optimizer state, and RNG state,
which accounts for most of the ~600MB file size. This extracts just the net
weights + config and writes a lean copy to area_43/output/.

Usage:
    python -m area_43.strip --target path/to/model.pt
"""
import argparse
import os

import torch

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def strip(target_path):
    if not os.path.exists(target_path):
        print(f"Error: file not found: {target_path}")
        return

    print(f"Loading {target_path} ...")
    blob = torch.load(target_path, map_location="cpu", weights_only=False)

    if "net" not in blob:
        print("Error: file does not contain a 'net' key — may not be a valid checkpoint.")
        return

    stripped = {
        "net":    blob["net"],
        "config": blob.get("config", {}),
    }
    if "iteration" in blob:
        stripped["iteration"] = blob["iteration"]
    if "phase" in blob:
        stripped["phase"] = blob["phase"]

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = os.path.basename(target_path)
    out_path = os.path.join(OUTPUT_DIR, filename)

    tmp = out_path + ".tmp"
    torch.save(stripped, tmp)
    os.replace(tmp, out_path)

    original_mb = os.path.getsize(target_path) / 1_048_576
    stripped_mb = os.path.getsize(out_path) / 1_048_576
    print(f"Done.")
    print(f"  Original : {original_mb:.1f} MB")
    print(f"  Stripped : {stripped_mb:.1f} MB")
    print(f"  Saved to : {out_path}")


def main():
    ap = argparse.ArgumentParser(description="Strip a training checkpoint to weights-only")
    ap.add_argument("--target", required=True, help="path to the checkpoint to strip")
    args = ap.parse_args()
    strip(args.target)


if __name__ == "__main__":
    main()
