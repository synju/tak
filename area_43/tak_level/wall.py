import os

from engine.mesh_object import MeshObject
from engine.geometry import make_wire_box_node
from area_43.tak_level.flat import Flat
from panda3d.bullet import BulletBoxShape, BulletRigidBodyNode


class Wall:
    BLACK = (0.1, 0.1, 0.1, 1.0)
    WHITE = (0.9, 0.9, 0.9, 1.0)
    # Same stone as a Flat, stood up on its edge: a 1.5 face goes vertical,
    # the 0.5 thickness becomes the depth.
    WIDTH = Flat.WIDTH    # 1.5
    HEIGHT = Flat.LENGTH  # 1.5 -> now vertical
    LENGTH = Flat.HEIGHT  # 0.5 -> thin depth

    # 3D stone model, stood on its edge. Tune these to taste.
    MODEL_SCALE = 0.5
    MODEL_OFFSET = (0.0, 0.25, 0.0)   # nudge to centre on the square
    MODEL_HPR = (0.0, 90.0, 0.0)     # pitch the stone up onto its edge

    BOARD_TOP = 0.25  # board surface height (where a layer-0 piece rests)

    def __init__(self, engine, color=BLACK, x=0, y=0, layer_index=0):
        self.engine = engine
        self.color = color
        self.layer_index = layer_index
        bottom = Wall.BOARD_TOP + layer_index * Flat.HEIGHT
        z = bottom + Wall.HEIGHT / 2
        self.position = (x, y, z)
        self.mesh = MeshObject(engine, "Wall")
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

        self.mesh_node = self.mesh.node.attachNewNode("wall_model")
        Flat._template(self.engine, self.color).instanceTo(self.mesh_node)
        ox, oy, oz = Wall.MODEL_OFFSET
        px, py, pz = self.position
        self.mesh_node.setPos(px + ox, py + oy, pz + oz)
        self.mesh_node.setHpr(*Wall.MODEL_HPR)
        self.mesh_node.setScale(Wall.MODEL_SCALE)

        outline = make_wire_box_node(
            Wall.WIDTH, Wall.HEIGHT, Wall.LENGTH,
            position=self.position, name="wall_outline",
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

        shape = BulletBoxShape((Wall.WIDTH / 2, Wall.LENGTH / 2, Wall.HEIGHT / 2))
        self.body = BulletRigidBodyNode("wall_collision")
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
