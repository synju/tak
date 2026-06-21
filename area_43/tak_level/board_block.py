from engine.mesh_object import MeshObject
from engine.geometry import make_box_node


class BoardBlock:
    BLACK = (0.1, 0.1, 0.1, 1.0)
    WHITE = (0.9, 0.9, 0.9, 1.0)

    WIDTH = 2.0
    HEIGHT = 0.25
    LENGTH = 2.0

    @staticmethod
    def board_to_world(board_x, board_y):
        """Convert board cell coords to world (x, y)."""
        return board_x * BoardBlock.WIDTH, board_y * BoardBlock.LENGTH

    def __init__(self, engine, color=WHITE, x=0, y=0, z=0):
        self.engine = engine
        self.color = color
        self.position = (x, y, z)
        self.mesh = MeshObject(engine, "BoardBlock")
        self.mesh_node = None
        self._build_mesh()

    def _build_mesh(self):
        if self.mesh_node:
            self.mesh_node.removeNode()

        node = make_box_node(
            BoardBlock.WIDTH, BoardBlock.HEIGHT, BoardBlock.LENGTH,
            self.color, self.position, "board_block",
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
