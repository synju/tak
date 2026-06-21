from area_43.tak_level.flat import Flat
from area_43.tak_level.capstone import Capstone


class Reserve:
    """A player's piece supply on the table: mini stacks of stones + a capstone."""

    TABLE_TOP = 0.0  # table surface (reserve pieces rest here, not on the board)
    COLS = 5
    STACK_HEIGHT = 4
    SPACING = 2.0
    ROW_SPACING = 2.0

    def __init__(self, engine, stone_color, capstone_color, odd_color,
                 center_x, center_y, board_dir=1):
        self.engine = engine
        self.pieces = []
        # The lone stone belongs to the opponent (Tak opening swap):
        # this player's first move must place this piece.
        self.odd_color = odd_color

        # Two rows on a 5-column grid centered on (center_x, center_y).
        # board_dir is the y-direction toward the board: the stacks sit on the
        # board side, the lone stone + capstone on the player side.
        #   board side:   4  4  4  4  4   (stacks of 4)
        #   player side:  1  cap
        offset = (Reserve.COLS - 1) / 2
        xs = [center_x + (i - offset) * Reserve.SPACING for i in range(Reserve.COLS)]
        y_stacks = center_y + board_dir * Reserve.ROW_SPACING / 2
        y_oddcap = center_y - board_dir * Reserve.ROW_SPACING / 2

        # Board side: 5 stacks of 4
        for sx in xs:
            for layer in range(Reserve.STACK_HEIGHT):
                self._add_flat(stone_color, sx, y_stacks, layer)

        # Player side: lone opponent stone (opening piece) + capstone. Place them
        # on the player's left in both seats: facing -y mirrors x, so use the
        # high-x columns there.
        odd_x, cap_x = (xs[0], xs[1]) if board_dir >= 0 else (xs[-1], xs[-2])
        self._add_flat(odd_color, odd_x, y_oddcap, 0)
        cap = Capstone(engine, capstone_color, x=cap_x, y=y_oddcap)
        cap.set_position(cap_x, y_oddcap, Reserve.TABLE_TOP + Capstone.HEIGHT / 2)
        self.pieces.append(cap)

    def _add_flat(self, color, x, y, layer):
        flat = Flat(self.engine, color, x=x, y=y, layer_index=layer)
        flat.set_position(x, y, Reserve.TABLE_TOP + layer * Flat.HEIGHT + Flat.HEIGHT / 2)
        self.pieces.append(flat)

    def destroy(self):
        for piece in self.pieces:
            piece.destroy()
        self.pieces = []
