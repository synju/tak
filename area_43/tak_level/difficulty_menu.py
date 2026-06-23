from direct.gui.DirectGui import DirectButton, DirectLabel
from direct.gui import DirectGuiGlobals as DGG


class DifficultyMenu:
    """Pick a bot difficulty as a centered row of numbered buttons.

    Calls on_select(level) with level in 1 (easiest) .. levels (hardest).
    """

    def __init__(self, on_select, levels=10):
        self.buttons = []
        spacing = 0.2
        start_x = -spacing * (levels - 1) / 2  # centre the row
        for i in range(levels):
            level = i + 1
            self.buttons.append(DirectButton(
                text=str(level),
                text_scale=0.06,
                text_pos=(0, -0.02),
                text_fg=(1, 1, 1, 1),
                frameColor=(0.15, 0.15, 0.15, 1),
                frameSize=(-0.09, 0.09, -0.09, 0.09),
                relief=DGG.FLAT,
                pos=(start_x + i * spacing, 0, 0),
                command=on_select,
                extraArgs=[level],
            ))
        self.title = DirectLabel(
            text="SELECT DIFFICULTY",
            text_fg=(1, 1, 1, 1),
            text_scale=0.08,
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.22),
        )
        self.hint = DirectLabel(
            text="1 = EASIEST          10 = HARDEST",
            text_fg=(1, 1, 1, 1),
            text_scale=0.045,
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, -0.22),
        )

    def destroy(self):
        for button in self.buttons:
            button.destroy()
        self.title.destroy()
        self.hint.destroy()
