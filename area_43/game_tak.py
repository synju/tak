import argparse

from engine.peach_engine import PeachEngine
from area_43.scenes.tak_scene import TakScene

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description="Tak")
    ap.add_argument("--turn-time", type=float, default=2.0,
                    help="seconds each NN waits before moving in NN vs NN (default 2)")
    args = ap.parse_args()

    engine = PeachEngine(
        width=1280,
        height=720,
        title="Tak",
        fps=60,
    )
    engine.debug_enabled = False

    engine.scene_handler.add_scene(
        'tak_scene', TakScene(engine, turn_time=args.turn_time))
    engine.scene_handler.set_scene('tak_scene')

    engine.run()
