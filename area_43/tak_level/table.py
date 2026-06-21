from engine.mesh_object import MeshObject
from engine.geometry import make_box_node


class Table:
    WOOD = (0.6, 0.4, 0.2, 1.0)

    def __init__(self, engine,width=12, length=12, x=0, y=0, z=0):
        self.engine = engine
        self.position = (x, y, z)
        self.mesh = MeshObject(engine, "Table")
        self.mesh_node = None
        self._build_mesh(width,length)

    def _build_mesh(self, width=12, length=12):
        if self.mesh_node:
            self.mesh_node.removeNode()

        node = make_box_node(
            width, 1.0, length, self.WOOD, self.position, "table",
        )
        self.mesh_node = self.mesh.node.attachNewNode(node)

    def set_position(self, x, y, z):
        self.position = (x, y, z)
        self._build_mesh()

    def show(self):
        if self.mesh_node:
            self.mesh_node.show()

    def hide(self):
        if self.mesh_node:
            self.mesh_node.hide()

    def destroy(self):
        if self.mesh_node:
            self.mesh_node.removeNode()
            self.mesh_node = None
        self.mesh.destroy()
