import os

from engine.mesh_object import MeshObject
from engine.geometry import make_wire_box_node
from panda3d.bullet import BulletBoxShape, BulletRigidBodyNode
from panda3d.core import Filename


class Flat:
    BLACK = (0.1, 0.1, 0.1, 1.0)
    WHITE = (0.9, 0.9, 0.9, 1.0)
    WIDTH = 1.5
    HEIGHT = 0.5
    LENGTH = 1.5

    # 3D stone model (Light=white, Dark=black). Tune these to taste.
    MODEL_DIR = os.path.join(os.path.dirname(__file__), "..",
                             "entities", "models", "tak")
    MODEL_SCALE = 0.5                  # stone is 3x3x1 in model units
    MODEL_OFFSET = (0.0, 0.0, -0.25)   # base sits on the box bottom

    HIGHLIGHT = (1.0, 1.0, 0.0, 1.0)  # yellow when selecting/building a selection

    _TEMPLATES = {}  # path -> loaded model, shared by all stones (flat + wall)

    @classmethod
    def _model_file(cls, color):
        return "Light.gltf" if color == cls.WHITE else "Dark.gltf"

    @classmethod
    def _template(cls, engine, color):
        """Load each colour's model once; instance it for every stone."""
        key = cls._model_file(color)
        tmpl = Flat._TEMPLATES.get(key)
        if tmpl is None:
            # Absolute Panda path (forward slashes) so loadModel works on Windows too.
            path = os.path.abspath(os.path.join(cls.MODEL_DIR, key))
            tmpl = engine.loader.loadModel(Filename.fromOsSpecific(path))
            Flat._TEMPLATES[key] = tmpl
        return tmpl

    def __init__(self, engine, color=WHITE, x=0, y=0, layer_index=0):
        self.engine = engine
        self.color = color
        self.layer_index = layer_index
        z = (layer_index + 1) * Flat.HEIGHT
        self.position = (x, y, z)
        self.mesh = MeshObject(engine, "Flat")
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

        self.mesh_node = self.mesh.node.attachNewNode("flat_model")
        Flat._template(self.engine, self.color).instanceTo(self.mesh_node)
        ox, oy, oz = Flat.MODEL_OFFSET
        px, py, pz = self.position
        self.mesh_node.setPos(px + ox, py + oy, pz + oz)
        self.mesh_node.setScale(Flat.MODEL_SCALE)

        outline = make_wire_box_node(
            Flat.WIDTH, Flat.HEIGHT, Flat.LENGTH,
            position=self.position, name="flat_outline",
        )
        self.outline_np = self.mesh.node.attachNewNode(outline)
        self.set_highlight(self._highlighted)

    def set_highlight(self, on):
        self._highlighted = on
        if not self.outline_np:
            return
        if on:
            self.outline_np.setColor(*Flat.HIGHLIGHT, 1)
            self.outline_np.show()
        else:
            self.outline_np.hide()

    def _create_collision(self):
        if self.body:
            self.engine.physics.removeRigidBody(self.body)
            self.body_np.removeNode()

        shape = BulletBoxShape((Flat.WIDTH / 2, Flat.LENGTH / 2, Flat.HEIGHT / 2))
        self.body = BulletRigidBodyNode("flat_collision")
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
