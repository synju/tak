import os

from engine.mesh_object import MeshObject
from engine.geometry import make_wire_box_node
from area_43.tak_level.flat import Flat
from panda3d.bullet import BulletBoxShape, BulletRigidBodyNode
from panda3d.core import Filename


class Capstone:
    # Player 1 (BLACK) -> gold, Player 2 (WHITE) -> silver
    GOLD = (0.83, 0.69, 0.22, 1.0)
    SILVER = (0.75, 0.75, 0.78, 1.0)
    WIDTH = 1.0
    HEIGHT = 0.9
    LENGTH = 1.0

    # 3D pyramid model. Gold capstone (dark-stone player) -> dark pyramid,
    # silver capstone (light-stone player) -> light pyramid. Tune to taste.
    MODEL_DIR = Flat.MODEL_DIR
    MODEL_SCALE = 0.45                  # pyramid is ~2.2 wide x 1.94 tall in model units
    MODEL_OFFSET = (0.0, 0.0, -0.45)    # base sits on the box bottom

    BOARD_TOP = 0.25  # board surface height (where a layer-0 piece rests)

    _TEMPLATES = {}  # path -> loaded model, shared by all capstones

    @classmethod
    def _model_file(cls, color):
        return "light_pyramid.gltf" if color == cls.SILVER else "dark_pyramid.gltf"

    @classmethod
    def _template(cls, engine, color):
        """Load each pyramid once; instance it for every capstone."""
        key = cls._model_file(color)
        tmpl = Capstone._TEMPLATES.get(key)
        if tmpl is None:
            path = os.path.abspath(os.path.join(cls.MODEL_DIR, key))
            tmpl = engine.loader.loadModel(Filename.fromOsSpecific(path))
            Capstone._TEMPLATES[key] = tmpl
        return tmpl

    def __init__(self, engine, color=GOLD, x=0, y=0, layer_index=0):
        self.engine = engine
        self.color = color
        self.layer_index = layer_index
        bottom = Capstone.BOARD_TOP + layer_index * Flat.HEIGHT
        z = bottom + Capstone.HEIGHT / 2
        self.position = (x, y, z)
        self.mesh = MeshObject(engine, "Capstone")
        self.mesh_node = None
        self.outline_np = None
        self._highlighted = False
        self.body = None
        self.body_np = None
        self._build_mesh()
        self._create_collision()

    def _build_mesh(self):
        if self.mesh_node:
            self.mesh_node.removeNode()
        if self.outline_np:
            self.outline_np.removeNode()

        self.mesh_node = self.mesh.node.attachNewNode("capstone_model")
        Capstone._template(self.engine, self.color).instanceTo(self.mesh_node)
        ox, oy, oz = Capstone.MODEL_OFFSET
        px, py, pz = self.position
        self.mesh_node.setPos(px + ox, py + oy, pz + oz)
        self.mesh_node.setScale(Capstone.MODEL_SCALE)

        # Outline only appears (yellow) on highlight.
        outline = make_wire_box_node(
            Capstone.WIDTH, Capstone.HEIGHT, Capstone.LENGTH,
            color=Flat.HIGHLIGHT, position=self.position, name="capstone_outline",
        )
        self.outline_np = self.mesh.node.attachNewNode(outline)
        self.set_highlight(self._highlighted)

    def set_highlight(self, on):
        self._highlighted = on
        if not self.outline_np:
            return
        if on:
            self.outline_np.show()
        else:
            self.outline_np.hide()

    def _create_collision(self):
        if self.body:
            self.engine.physics.removeRigidBody(self.body)
            self.body_np.removeNode()

        shape = BulletBoxShape((Capstone.WIDTH / 2, Capstone.LENGTH / 2, Capstone.HEIGHT / 2))
        self.body = BulletRigidBodyNode("capstone_collision")
        self.body.addShape(shape)
        self.body_np = self.engine.render.attachNewNode(self.body)
        self.body_np.setPos(*self.position)
        self.engine.physics.attachRigidBody(self.body)

    def set_position(self, x, y, z):
        self.position = (x, y, z)
        self._build_mesh()
        if self.body_np:
            self.body_np.setPos(x, y, z)

    def show(self):
        if self.mesh_node:
            self.mesh_node.show()

    def hide(self):
        if self.mesh_node:
            self.mesh_node.hide()

    def destroy(self):
        if self.body:
            self.engine.physics.removeRigidBody(self.body)
            self.body_np.removeNode()
            self.body = None
            self.body_np = None
        if self.outline_np:
            self.outline_np.removeNode()
            self.outline_np = None
        if self.mesh_node:
            self.mesh_node.removeNode()
            self.mesh_node = None
        self.mesh.destroy()
