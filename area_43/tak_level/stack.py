from panda3d.core import GeomVertexFormat, GeomVertexData, GeomVertexWriter
from panda3d.core import Geom, GeomLines, GeomNode, LColor
from area_43.tak_level.board_block import BoardBlock
from area_43.tak_level.flat import Flat


class Stack:
    def __init__(self, board_x, board_y):
        self.x = board_x * BoardBlock.WIDTH
        self.y = board_y * BoardBlock.LENGTH
        self.flats = []
        self.highlight = None
        self.selected_index = 0

    def push(self, engine, color):
        layer_index = len(self.flats)
        flat = Flat(engine, color=color, x=self.x, y=self.y, layer_index=layer_index)
        self.flats.append(flat)
        self.selected_index = len(self.flats) - 1
        return flat

    def pop(self):
        flat = self.flats.pop()
        flat.destroy()
        if self.selected_index >= len(self.flats):
            self.selected_index = len(self.flats) - 1 if self.flats else 0
        return flat

    def get_top(self):
        return self.flats[-1] if self.flats else None

    def get_selected(self):
        if not self.flats:
            return None
        return self.flats[self.selected_index]

    def height(self):
        return len(self.flats)

    def show_highlight(self):
        if self.highlight:
            self.highlight.show()

    def hide_highlight(self):
        if self.highlight:
            self.highlight.hide()

    def update_highlight(self, engine):
        if not self.flats:
            return

        if self.highlight:
            self.highlight.removeNode()

        from panda3d.core import LineSegs

        lines = LineSegs("highlight")
        lines.setThickness(3.0)
        lines.setColor(1, 1, 0, 1)

        hw = Flat.WIDTH / 2
        hh = Flat.HEIGHT / 2
        hl = Flat.LENGTH / 2

        def draw_box(ox, oy, oz):
            corners = [
                (ox - hw, oy - hl, oz - hh),
                (ox + hw, oy - hl, oz - hh),
                (ox + hw, oy + hl, oz - hh),
                (ox - hw, oy + hl, oz - hh),
                (ox - hw, oy - hl, oz + hh),
                (ox + hw, oy - hl, oz + hh),
                (ox + hw, oy + hl, oz + hh),
                (ox - hw, oy + hl, oz + hh),
            ]
            edges = [
                (0, 1),
                (1, 2),
                (2, 3),
                (3, 0),
                (4, 5),
                (5, 6),
                (6, 7),
                (7, 4),
                (0, 4),
                (1, 5),
                (2, 6),
                (3, 7),
            ]
            for a, b in edges:
                lines.moveTo(*corners[a])
                lines.drawTo(*corners[b])

        for i in range(self.selected_index, len(self.flats)):
            draw_box(
                self.flats[i].position[0],
                self.flats[i].position[1],
                self.flats[i].position[2],
            )

        self.highlight = engine.render.attachNewNode(lines.create())

    def destroy(self):
        for flat in self.flats:
            flat.destroy()
        self.flats = []
        if self.highlight:
            self.highlight.removeNode()
            self.highlight = None
