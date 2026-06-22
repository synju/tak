from direct.gui.DirectGui import DirectFrame, DirectButton, DirectLabel
from direct.gui import DirectGuiGlobals as DGG


class WinPanel:
    """Centered result panel + a bottom row of buttons.

    bg/fg colour the panel by winner. The bottom row holds QUIT TO MENU,
    EXAMINE BOARD and PLAY AGAIN (evenly spaced, centered). EXAMINE BOARD hides
    the result rect + text and removes itself, leaving QUIT TO MENU / PLAY AGAIN
    centered as a pair so the finished board can be rotated and examined.
    """

    BTN_Z = -0.85

    def __init__(self, message, bg, fg, on_play_again, on_quit_to_menu):
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
        z = WinPanel.BTN_Z
        self.quit = self._button("QUIT TO MENU", (-0.5, 0, z), on_quit_to_menu)
        self.examine = self._button("EXAMINE BOARD", (0, 0, z), self._examine)
        self.play_again = self._button("PLAY AGAIN", (0.5, 0, z), on_play_again)

    def _button(self, text, pos, command):
        return DirectButton(
            text=text,
            text_scale=0.04,
            text_pos=(0, -0.012),
            text_fg=(1, 1, 1, 1),
            frameColor=(0.15, 0.15, 0.15, 1),
            frameSize=(-0.22, 0.22, -0.05, 0.05),
            relief=DGG.FLAT,
            pos=pos,
            command=command,
        )

    def _examine(self):
        # Hide the result (frame hides its child label) and the spent examine
        # button, then re-center the remaining pair at the bottom.
        self.frame.hide()
        self.examine.hide()
        self.quit.setPos(-0.25, 0, WinPanel.BTN_Z)
        self.play_again.setPos(0.25, 0, WinPanel.BTN_Z)

    def destroy(self):
        self.quit.destroy()
        self.examine.destroy()
        self.play_again.destroy()
        self.frame.destroy()
