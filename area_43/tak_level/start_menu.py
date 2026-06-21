from direct.showbase.ShowBase import ShowBase
from direct.gui.DirectGui import DirectButton, DirectLabel
from direct.gui import DirectGuiGlobals as DGG

base: ShowBase


class StartMenu:
    """Pre-game menu: centered PLAY / QUIT buttons + a credit line.

    Clicks are polled from the engine's mouse (see WinPanel) rather than relying
    on DirectGui's command dispatch, so the buttons are visuals only.
    """

    def __init__(self, on_play, on_quit):
        self.buttons = []
        self._zones = []
        z = 0.15
        for text, callback in (("PLAY", on_play), ("QUIT", on_quit)):
            button = DirectButton(
                text=text,
                text_scale=0.07,
                text_pos=(0, -0.021),
                text_fg=(1, 1, 1, 1),
                frameColor=(0.15, 0.15, 0.15, 1),
                frameSize=(-0.3, 0.3, -0.08, 0.08),
                relief=DGG.FLAT,
                pos=(0, 0, z),
                command=None,  # visual only; clicks handled by handle_click
            )
            self.buttons.append(button)
            self._zones.append((button, callback))
            z -= 0.22
        self.credit = DirectLabel(
            text="MADE BY CHARL DU PLESSIS",
            text_fg=(1, 1, 1, 1),
            text_scale=0.05,
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, -0.9),
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
            px, _, pz = button.getPos()
            left, right, bottom, top = button["frameSize"]
            if px + left <= ax <= px + right and pz + bottom <= az <= pz + top:
                callback()
                return True
        return False

    def destroy(self):
        for button in self.buttons:
            button.destroy()
        self.credit.destroy()
