from direct.showbase.ShowBase import ShowBase
from direct.gui.DirectGui import DirectFrame, DirectButton, DirectLabel
from direct.gui import DirectGuiGlobals as DGG

base: ShowBase


class WinPanel:
    """Centered result panel + PLAY AGAIN / EXAMINE BOARD buttons.

    Clicks are detected by polling the engine's mouse (DirectGui's own command
    dispatch is unreliable in this render path), so the buttons are visuals only.
    EXAMINE BOARD hides the panel and moves PLAY AGAIN to the top-left so the
    finished board can be rotated and examined.
    """

    def __init__(self, message, bg, fg, on_play_again):
        self._on_play_again = on_play_again
        self.frame = DirectFrame(
            frameColor=bg,
            frameSize=(-0.6, 0.6, -0.35, 0.35),
            pos=(0, 0, 0),
        )
        # z offset of -0.35*scale drops the baseline so the line is centered.
        self.label = DirectLabel(
            parent=self.frame,
            text=message,
            text_fg=fg,
            text_scale=0.13,
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, -0.045),
        )
        size = (-0.2, 0.2, -0.05, 0.05)
        self.play_again = self._button("PLAY AGAIN", size, (-0.25, 0, -0.85))
        self.examine = self._button("EXAMINE BOARD", size, (0.25, 0, -0.85))

        # (button, callback) hot zones, hit-tested in aspect2d coords
        self._zones = [
            (self.play_again, self._on_play_again),
            (self.examine, self._examine),
        ]

    def _button(self, text, size, pos):
        return DirectButton(
            text=text,
            text_scale=0.04,
            text_pos=(0, -0.012),
            text_fg=(1, 1, 1, 1),
            frameColor=(0.15, 0.15, 0.15, 1),
            frameSize=size,
            relief=DGG.FLAT,
            pos=pos,
            command=None,  # visual only; clicks handled by handle_click
        )

    def handle_click(self, input_handler):
        """Fire a button if the mouse was just clicked on it. Returns True if so."""
        if not input_handler.is_mouse_down(1):
            return False
        if not base.mouseWatcherNode.hasMouse():
            return False
        ax = base.mouseWatcherNode.getMouseX() * base.getAspectRatio()
        az = base.mouseWatcherNode.getMouseY()
        for button, callback in self._zones:
            if button.isHidden():
                continue
            px, _, pz = button.getPos()
            left, right, bottom, top = button["frameSize"]
            if px + left <= ax <= px + right and pz + bottom <= az <= pz + top:
                callback()
                return True
        return False

    def _examine(self):
        # Hide the result (frame hides its child label) and the examine button,
        # then tuck PLAY AGAIN near the top-left corner.
        self.frame.hide()
        self.examine.hide()
        self.play_again.setPos(-1.05, 0, 0.88)

    def destroy(self):
        self.play_again.destroy()
        self.examine.destroy()
        self.frame.destroy()
