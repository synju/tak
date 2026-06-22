from direct.gui.DirectGui import DirectButton, DirectLabel
from direct.gui import DirectGuiGlobals as DGG


class StartMenu:
    """A centered vertical button menu (used for the main menu and the
    start-as-colour choice). Optionally shows the author credit at the bottom.

    buttons: list of (label, callback) pairs, top to bottom.
    """

    def __init__(self, buttons, credit=False):
        self.buttons = []
        z = 0.15
        for label, callback in buttons:
            self.buttons.append(DirectButton(
                text=label,
                text_scale=0.07,
                text_pos=(0, -0.021),
                text_fg=(1, 1, 1, 1),
                frameColor=(0.15, 0.15, 0.15, 1),
                frameSize=(-0.35, 0.35, -0.08, 0.08),
                relief=DGG.FLAT,
                pos=(0, 0, z),
                command=callback,
            ))
            z -= 0.22
        self.credit = None
        if credit:
            self.credit = DirectLabel(
                text="MADE BY CHARL DU PLESSIS",
                text_fg=(1, 1, 1, 1),
                text_scale=0.05,
                frameColor=(0, 0, 0, 0),
                pos=(0, 0, -0.9),
            )

    def destroy(self):
        for button in self.buttons:
            button.destroy()
        if self.credit:
            self.credit.destroy()
