import os
from panda3d.core import Filename
from area_43.tak_level.flat import Flat

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
_cache = {}


def texture_for(engine, color):
    """Loaded texture for a piece color: black -> dark.jpg, white -> light.jpg (cached)."""
    name = "dark.jpg" if tuple(color) == Flat.BLACK else "light.jpg"
    if name not in _cache:
        path = Filename.fromOsSpecific(os.path.join(_ASSETS, name))
        _cache[name] = engine.loader.loadTexture(path)
    return _cache[name]
