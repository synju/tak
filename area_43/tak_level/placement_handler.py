from panda3d.core import Point3, LineSegs
from direct.showbase.ShowBase import ShowBase
from area_43.tak_level.board_block import BoardBlock
from area_43.tak_level.flat import Flat
from area_43.tak_level.wall import Wall
from area_43.tak_level.capstone import Capstone

base: ShowBase


class PlacementHandler:
    """Pick pieces from a reserve or a board stack and place/move them.

    Reserve pick: a single piece (flat/wall toggle on scroll), placed on any legal cell.
    Board pick:   carry the top N pieces (scroll sets N, max 5), spread one-per-click
                  along a straight line (Tak movement), right-click cancels exactly."""

    RAISE = 0.6          # how far a picked piece lifts above its resting spot
    BOARD_TOP = 0.25     # board surface (a layer-0 piece rests here)
    CELL = BoardBlock.WIDTH
    MAX_CARRY = 5

    def __init__(self, engine, reserves, board_size=5, on_place=None):
        self.engine = engine
        self.reserves = reserves
        self.board_size = board_size
        self.on_place = on_place
        self.current_player = 0

        # Tak opening: each player's first move must place the odd (opponent)
        # piece in their reserve. Nothing else is grabbable until they have.
        self.opening_done = [False, False]
        self.carry_is_opening = False

        # Placed pieces per cell -> ordered list (bottom..top)
        self.board_stacks = {}

        # Carry state
        self.carrying = False
        self.carry_source = None   # 'reserve' | 'board'
        self.carry = []            # pieces not yet dropped (bottom..top)
        # reserve-specific
        self.is_capstone = False
        self.is_wall = False
        self.color = None
        self.origin_reserve = None
        self.origin_pos = None
        # board-specific
        self.origin_cell = None
        self.max_carry = 1
        self.drops = []            # (cell, piece) in drop order
        self.dir = None            # chosen line direction (dx, dy)
        self.last_cell = None      # most recent drop cell

        self.target_cell = None
        self.hovered_key = None

        # Hover selection (idle) and placement preview
        self.preview = None
        self.hover_pieces = []     # pieces whose outline is currently highlighted
        self.hover_is_board = False
        self.hover_cell = None
        self.hover_count = 1       # how many board pieces are pre-selected
        self.hover_max = 1

    # --- geometry / piece helpers -----------------------------------------

    @staticmethod
    def _piece_dims(piece):
        if isinstance(piece, Capstone):
            return Capstone.WIDTH, Capstone.HEIGHT, Capstone.LENGTH
        if isinstance(piece, Wall):
            return Wall.WIDTH, Wall.HEIGHT, Wall.LENGTH
        return Flat.WIDTH, Flat.HEIGHT, Flat.LENGTH

    @staticmethod
    def _piece_height(piece):
        if isinstance(piece, Capstone):
            return Capstone.HEIGHT
        if isinstance(piece, Wall):
            return Wall.HEIGHT
        return Flat.HEIGHT

    def _owner(self, piece):
        c = piece.color
        if c in (Flat.BLACK, Capstone.GOLD):
            return 0
        if c in (Flat.WHITE, Capstone.SILVER):
            return 1
        return None

    def _layer_z(self, layer, height):
        return PlacementHandler.BOARD_TOP + layer * Flat.HEIGHT + height / 2

    # --- wireframe box -----------------------------------------------------

    def _make_box(self, width, height, length):
        lines = LineSegs("placement_box")
        lines.setThickness(2.0)
        lines.setColor(1, 1, 0, 1)
        hw, hh, hl = width / 2, height / 2, length / 2
        corners = [
            (-hw, -hl, -hh), (hw, -hl, -hh), (hw, hl, -hh), (-hw, hl, -hh),
            (-hw, -hl, hh), (hw, -hl, hh), (hw, hl, hh), (-hw, hl, hh),
        ]
        edges = [
            (0, 1), (1, 2), (2, 3), (3, 0),
            (4, 5), (5, 6), (6, 7), (7, 4),
            (0, 4), (1, 5), (2, 6), (3, 7),
        ]
        for a, b in edges:
            lines.moveTo(*corners[a])
            lines.drawTo(*corners[b])
        return self.engine.render.attachNewNode(lines.create())

    def _rebuild_preview_for(self, piece):
        if self.preview:
            self.preview.removeNode()
        self.preview = self._make_box(*self._piece_dims(piece))
        self.preview.hide()

    # --- mouse ray helpers -------------------------------------------------

    def _mouse_ray(self):
        if not base.mouseWatcherNode.hasMouse():
            return None
        mpos = base.mouseWatcherNode.getMouse()
        near, far = Point3(), Point3()
        base.camLens.extrude(mpos, near, far)
        a = base.render.getRelativePoint(base.camera, near)
        b = base.render.getRelativePoint(base.camera, far)
        return a, b

    def _ray_plane_z(self, target_z):
        ray = self._mouse_ray()
        if not ray:
            return None
        a, b = ray
        d = b - a
        if abs(d.z) < 1e-6:
            return None
        t = (target_z - a.z) / d.z
        if t < 0:
            return None
        return a + d * t

    def _cell_under_cursor(self):
        point = self._ray_plane_z(PlacementHandler.BOARD_TOP)
        if point is None:
            return None
        cx = round(point.x / PlacementHandler.CELL)
        cy = round(point.y / BoardBlock.LENGTH)
        if 0 <= cx < self.board_size and 0 <= cy < self.board_size:
            return cx, cy
        return None

    def _find_board_cell(self, hit_node):
        for cell, stack in self.board_stacks.items():
            for piece in stack:
                if piece.body == hit_node:
                    return cell
        return None

    @staticmethod
    def _is_top(reserve, piece):
        px, py, pz = piece.position
        for other in reserve.pieces:
            if other is piece:
                continue
            ox, oy, oz = other.position
            if abs(ox - px) < 0.5 and abs(oy - py) < 0.5 and oz > pz:
                return False
        return True

    def _grabbable_under_cursor(self):
        """Returns ('reserve', reserve, piece) | ('board', cell, top_piece) | None."""
        ray = self._mouse_ray()
        if not ray:
            return None
        result = self.engine.physics.rayTestClosest(*ray)
        if not result.hasHit():
            return None
        hit_node = result.getNode()
        opening = not self.opening_done[self.current_player]

        # Own reserve (top of a column only). During the opening move, only the
        # odd opponent-coloured piece may be grabbed.
        reserve = self.reserves[self.current_player]
        for piece in reserve.pieces:
            if piece.body == hit_node:
                if not self._is_top(reserve, piece):
                    return None
                if opening and piece.color != reserve.odd_color:
                    return None
                return ("reserve", reserve, piece)

        # During the opening move, board stacks cannot be moved yet.
        if opening:
            return None

        # Own board stack (engage from the top)
        cell = self._find_board_cell(hit_node)
        if cell is not None and self.board_stacks[cell]:
            top = self.board_stacks[cell][-1]
            if self._owner(top) == self.current_player:
                return ("board", cell, top)
        return None

    def set_current_player(self, index):
        self.current_player = index
        self._clear_hover()

    def is_holding(self):
        return self.carrying

    # --- placement legality ------------------------------------------------

    def _can_drop_on(self, cell, piece):
        """Reserve placement: empty only; a capstone may flatten a wall. No stacking on
        flats/capstones (stacks are formed by moving, not placing)."""
        stack = self.board_stacks.get(cell, [])
        top = stack[-1] if stack else None
        if top is None:
            return True
        if isinstance(top, Wall):
            return isinstance(piece, Capstone)
        return False

    @staticmethod
    def _orth_neighbor(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1

    def _cell_in_line(self, cell):
        """Tak straight-line constraint (plus origin re-drop)."""
        if self.dir is None:
            return cell == self.origin_cell or self._orth_neighbor(cell, self.origin_cell)
        nxt = (self.last_cell[0] + self.dir[0], self.last_cell[1] + self.dir[1])
        return cell == self.last_cell or cell == nxt

    def _legal_board_drop(self, cell, piece):
        if not self._cell_in_line(cell):
            return False
        stack = self.board_stacks.get(cell, [])
        top = stack[-1] if stack else None
        if isinstance(top, Capstone):
            return False
        if isinstance(top, Wall):
            # A capstone may flatten a wall only moving alone (last carried piece)
            return isinstance(piece, Capstone) and len(self.carry) == 1
        return True

    def _can_drop_now(self, cell, piece):
        if self.carry_source == "reserve":
            return self._can_drop_on(cell, piece)
        return self._legal_board_drop(cell, piece)

    # --- input / update ----------------------------------------------------

    def handle_input(self, input_handler):
        if self.carrying and input_handler.is_mouse_down(3):
            self.cancel()
            return
        if not input_handler.is_mouse_down(1):
            return
        if not self.carrying:
            self._try_pick()
        else:
            self._try_drop()

    def handle_scroll(self, delta):
        """Returns True if the scroll was consumed (so the scene won't zoom)."""
        if self.carrying:
            self.scroll(delta)
            return True
        # Idle: grow/shrink the pre-pickup selection on a hovered board stack
        if self.hover_is_board:
            new = max(1, min(self.hover_max, self.hover_count + (1 if delta > 0 else -1)))
            if new != self.hover_count:
                self.hover_count = new
                self._rebuild_highlight()
            return True
        return False

    def scroll(self, delta):
        if not self.carrying:
            return
        if self.carry_source == "reserve":
            self.toggle_orientation()  # any scroll flips flat<->wall
        else:
            if self.drops:
                return  # carry count locks once dropping starts
            if delta > 0:
                self._carry_more()
            else:
                self._carry_less()

    FOLLOW_RATE = 12.0   # how quickly the carried remainder eases to its anchor

    def update(self, dt=0.0):
        if not self.carrying:
            self._update_hover()
            return
        if not self.carry:
            return

        if self.carry_source == "board":
            self._animate_carry(dt)

        self.target_cell = self._cell_under_cursor()
        piece = self.carry[0]
        if (self.target_cell is not None and self.preview is not None
                and self._can_drop_now(self.target_cell, piece)):
            wx, wy = BoardBlock.board_to_world(*self.target_cell)
            layer = len(self.board_stacks.get(self.target_cell, []))
            self.preview.setPos(wx, wy, self._layer_z(layer, self._piece_height(piece)))
            self.preview.show()
        elif self.preview is not None:
            self.preview.hide()

    def _update_hover(self):
        desc = self._grabbable_under_cursor()
        if desc is None:
            key = None
        elif desc[0] == "reserve":
            key = id(desc[2])
        else:
            key = desc[1]
        if key == self.hovered_key:
            return
        self.hovered_key = key
        self._clear_highlight()
        self.hover_is_board = False
        self.hover_cell = None
        if desc is None:
            return
        if desc[0] == "reserve":
            piece = desc[2]
            piece.set_highlight(True)
            self.hover_pieces.append(piece)
        else:
            self.hover_is_board = True
            self.hover_cell = desc[1]
            self.hover_max = min(len(self.board_stacks[desc[1]]), PlacementHandler.MAX_CARRY)
            self.hover_count = 1
            self._rebuild_highlight()

    def _rebuild_highlight(self):
        """Highlight (yellow) the top N pieces of the hovered board stack."""
        self._clear_highlight()
        stack = self.board_stacks.get(self.hover_cell, [])
        for piece in stack[-self.hover_count:]:
            piece.set_highlight(True)
            self.hover_pieces.append(piece)

    def _clear_highlight(self):
        for piece in self.hover_pieces:
            piece.set_highlight(False)
        self.hover_pieces = []

    def _clear_hover(self):
        self.hovered_key = None
        self.hover_is_board = False
        self.hover_cell = None
        self.hover_count = 1
        self._clear_highlight()

    # --- pick --------------------------------------------------------------

    def _try_pick(self):
        desc = self._grabbable_under_cursor()
        if desc is None:
            return
        if desc[0] == "reserve":
            self._clear_hover()
            self._start_reserve_carry(desc[1], desc[2])
        else:
            count = self.hover_count if (self.hover_is_board and desc[1] == self.hover_cell) else 1
            self._clear_hover()
            self._start_board_carry(desc[1], count)

    def _start_reserve_carry(self, reserve, piece):
        reserve.pieces.remove(piece)
        self.carrying = True
        self.carry_source = "reserve"
        self.carry = [piece]
        self.is_capstone = isinstance(piece, Capstone)
        self.is_wall = False
        self.color = piece.color
        self.origin_reserve = reserve
        self.origin_pos = tuple(piece.position)
        self.carry_is_opening = piece.color == reserve.odd_color
        self._reposition_carry()
        self._rebuild_preview_for(piece)

    def _start_board_carry(self, cell, count=1):
        stack = self.board_stacks.get(cell, [])
        if not stack or self._owner(stack[-1]) != self.current_player:
            return
        self.carrying = True
        self.carry_source = "board"
        self.origin_cell = cell
        self.max_carry = min(len(stack), PlacementHandler.MAX_CARRY)
        count = max(1, min(count, self.max_carry))
        taken = [stack.pop() for _ in range(count)]
        taken.reverse()  # restore bottom..top order
        self.carry = taken
        self.drops = []
        self.dir = None
        self.last_cell = None
        self._reposition_carry()
        self._rebuild_preview_for(self.carry[0])

    def _carry_more(self):
        src = self.board_stacks.get(self.origin_cell, [])
        if len(self.carry) >= self.max_carry or not src:
            return
        self.carry.insert(0, src.pop())
        self._reposition_carry()
        self._rebuild_preview_for(self.carry[0])

    def _carry_less(self):
        if len(self.carry) <= 1:
            return
        piece = self.carry.pop(0)
        self._stack_piece(piece, self.origin_cell)  # back onto source top
        self._reposition_carry()
        self._rebuild_preview_for(self.carry[0])

    def _reposition_carry(self):
        if self.carry_source == "reserve":
            ox, oy, oz = self.origin_pos
            self.carry[0].set_position(ox, oy, oz + PlacementHandler.RAISE)
            return
        wx, wy = BoardBlock.board_to_world(*self.origin_cell)
        base_z = (PlacementHandler.BOARD_TOP
                  + len(self.board_stacks.get(self.origin_cell, [])) * Flat.HEIGHT
                  + PlacementHandler.RAISE)
        for i, piece in enumerate(self.carry):
            h = self._piece_height(piece)
            piece.set_position(wx, wy, base_z + i * Flat.HEIGHT + h / 2)

    def _carry_anchor(self):
        """Where the carried remainder floats: above the last-dropped cell (or origin)."""
        cell = self.last_cell if self.last_cell is not None else self.origin_cell
        wx, wy = BoardBlock.board_to_world(*cell)
        base_z = (PlacementHandler.BOARD_TOP
                  + len(self.board_stacks.get(cell, [])) * Flat.HEIGHT
                  + PlacementHandler.RAISE)
        return wx, wy, base_z

    def _animate_carry(self, dt):
        ax, ay, base_z = self._carry_anchor()
        f = min(1.0, PlacementHandler.FOLLOW_RATE * dt)
        for i, piece in enumerate(self.carry):
            h = self._piece_height(piece)
            tx, ty, tz = ax, ay, base_z + i * Flat.HEIGHT + h / 2
            cx, cy, cz = piece.position
            piece.set_position(cx + (tx - cx) * f, cy + (ty - cy) * f, cz + (tz - cz) * f)

    def toggle_orientation(self):
        # Opening move must be a flat stone: no wall toggle.
        if (not self.carrying or self.carry_source != "reserve"
                or self.is_capstone or self.carry_is_opening):
            return
        piece = self.carry[0]
        lx, ly, lz = piece.position
        piece.destroy()
        self.is_wall = not self.is_wall
        if self.is_wall:
            new = Wall(self.engine, self.color, x=lx, y=ly)
        else:
            new = Flat(self.engine, self.color, x=lx, y=ly)
        new.set_position(lx, ly, lz)
        self.carry = [new]
        self._rebuild_preview_for(new)

    # --- drop / place ------------------------------------------------------

    def _stack_piece(self, piece, cell):
        """Drop a piece onto a cell, flattening a wall if the piece is a capstone."""
        stack = self.board_stacks.setdefault(cell, [])
        top = stack[-1] if stack else None
        if isinstance(top, Wall) and isinstance(piece, Capstone):
            layer = len(stack) - 1
            wx, wy, _ = top.position
            color = top.color
            top.destroy()
            flat = Flat(self.engine, color, x=wx, y=wy)
            flat.set_position(wx, wy, self._layer_z(layer, Flat.HEIGHT))
            stack[layer] = flat
        layer = len(stack)
        wx, wy = BoardBlock.board_to_world(*cell)
        piece.set_position(wx, wy, self._layer_z(layer, self._piece_height(piece)))
        stack.append(piece)

    def _try_drop(self):
        cell = self.target_cell
        if cell is None:
            return
        piece = self.carry[0]
        if not self._can_drop_now(cell, piece):
            return

        self._stack_piece(piece, cell)
        self.carry.pop(0)

        if self.carry_source == "reserve":
            self._resolve()
            return

        self.drops.append((cell, piece))
        if cell != self.origin_cell:
            if self.dir is None:
                self.dir = (cell[0] - self.origin_cell[0], cell[1] - self.origin_cell[1])
            self.last_cell = cell
        else:
            self.last_cell = self.origin_cell

        if not self.carry:
            self._resolve()
        else:
            # Preview now reflects the next piece to drop (e.g. a wall on top).
            self._rebuild_preview_for(self.carry[0])
        # the remaining carry eases to the new anchor via _animate_carry()

    def cancel(self):
        """Right-click: revert the whole in-progress move to its starting state."""
        if not self.carrying:
            return
        if self.carry_source == "reserve":
            for piece in self.carry:
                piece.destroy()
            ox, oy, oz = self.origin_pos
            if self.is_capstone:
                restored = Capstone(self.engine, self.color, x=ox, y=oy)
            else:
                restored = Flat(self.engine, self.color, x=ox, y=oy)  # collapse wall -> flat
            restored.set_position(ox, oy, oz)
            self.origin_reserve.pieces.append(restored)
        else:
            # All picked-up pieces in original order: dropped (in order) then still-carried
            full = [p for (_, p) in self.drops] + list(self.carry)
            for cell, piece in self.drops:
                stack = self.board_stacks.get(cell, [])
                if piece in stack:
                    stack.remove(piece)
            for piece in full:
                self._stack_piece(piece, self.origin_cell)
        self._end_carry()

    def _resolve(self):
        changed = True
        if self.carry_source == "board":
            changed = any(cell != self.origin_cell for cell, _ in self.drops)
        elif self.carry_is_opening:
            self.opening_done[self.current_player] = True
        self._end_carry()
        if changed and self.on_place:
            self.on_place()

    def _end_carry(self):
        self.carrying = False
        self.carry_source = None
        self.carry = []
        self.is_capstone = False
        self.is_wall = False
        self.color = None
        self.carry_is_opening = False
        self.origin_reserve = None
        self.origin_pos = None
        self.origin_cell = None
        self.drops = []
        self.dir = None
        self.last_cell = None
        self.target_cell = None
        if self.preview:
            self.preview.removeNode()
            self.preview = None

    # --- cleanup -----------------------------------------------------------

    def destroy(self):
        for piece in self.carry:
            piece.destroy()
        self.carry = []
        for stack in self.board_stacks.values():
            for piece in stack:
                piece.destroy()
        self.board_stacks = {}
        if self.preview:
            self.preview.removeNode()
            self.preview = None
        self._clear_highlight()
