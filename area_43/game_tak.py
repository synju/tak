from engine.peach_engine import PeachEngine
from area_43.scenes.tak_scene import TakScene

if __name__ == '__main__':
    engine = PeachEngine(
        width=1280,
        height=720,
        title="Tak",
        fps=60,
    )
    engine.debug_enabled = False

    engine.scene_handler.add_scene('tak_scene', TakScene(engine))
    engine.scene_handler.set_scene('tak_scene')

    engine.run()
