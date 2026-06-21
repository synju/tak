from panda3d.core import Point3
from direct.showbase.ShowBase import ShowBase

base: ShowBase


class StackHandler:
    def __init__(self, engine):
        self.engine = engine
        self.stacks = []
        self.hovered_stack = None
        self._scroll_delta = 0
        self._is_hovering_stack = False
        self._orbit_cam = None

    def set_orbit_camera(self, orbit_cam):
        self._orbit_cam = orbit_cam

    def add_stack(self, stack):
        self.stacks.append(stack)

    def update(self):
        self._update_stack_hover()

        if self.hovered_stack and self.hovered_stack.height() > 1:
            if self._scroll_delta != 0:
                new_index = self.hovered_stack.selected_index + self._scroll_delta
                new_index = max(0, min(new_index, len(self.hovered_stack.flats) - 1))
                if new_index != self.hovered_stack.selected_index:
                    self.hovered_stack.selected_index = new_index
                    self.hovered_stack.update_highlight(self.engine)
                self._scroll_delta = 0

    def _update_stack_hover(self):
        if not base.mouseWatcherNode.hasMouse():
            return

        mpos = base.mouseWatcherNode.getMouse()
        lens = base.camLens

        near_point = Point3()
        far_point = Point3()
        lens.extrude(mpos, near_point, far_point)

        from_pos = base.render.getRelativePoint(base.camera, near_point)
        to_pos = base.render.getRelativePoint(base.camera, far_point)

        result = self.engine.physics.rayTestClosest(from_pos, to_pos)

        new_hovered = None
        if result.hasHit():
            hit_node = result.getNode()
            for stack in self.stacks:
                for flat in stack.flats:
                    if flat.body == hit_node:
                        new_hovered = stack
                        break
                if new_hovered:
                    break

        if new_hovered != self.hovered_stack:
            if self.hovered_stack:
                self.hovered_stack.hide_highlight()
            if new_hovered:
                new_hovered.selected_index = len(new_hovered.flats) - 1
                new_hovered.update_highlight(self.engine)
                new_hovered.show_highlight()
            self.hovered_stack = new_hovered
            self._is_hovering_stack = new_hovered is not None

    def on_scroll_up(self):
        if self._is_hovering_stack:
            self._scroll_delta = -1
        elif self._orbit_cam:
            self._orbit_cam.on_scroll_up()

    def on_scroll_down(self):
        if self._is_hovering_stack:
            self._scroll_delta = 1
        elif self._orbit_cam:
            self._orbit_cam.on_scroll_down()
