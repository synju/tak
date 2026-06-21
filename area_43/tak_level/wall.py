from engine.mesh_object import MeshObject
from engine.geometry import make_box_node_uv, make_wire_box_node
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

        node = make_box_node_uv(
            Wall.WIDTH, Wall.HEIGHT, Wall.LENGTH, self.position, "wall",
        )
        self.mesh_node = self.mesh.node.attachNewNode(node)
        from area_43.tak_level.piece_texture import texture_for
        self.mesh_node.setTexture(texture_for(self.engine, self.color))

        outline = make_wire_box_node(
            Wall.WIDTH, Wall.HEIGHT, Wall.LENGTH,
            position=self.position, name="wall_outline",
        )
        self.outline_np = self.mesh.node.attachNewNode(outline)
        self.set_highlight(self._highlighted)

    def set_highlight(self, on):
        self._highlighted = on
        if self.outline_np:
            self.outline_np.setColor(*(Flat.HIGHLIGHT if on else Flat.OUTLINE), 1)

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
