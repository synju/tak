from direct.showbase.ShowBase import ShowBase
from panda3d.core import WindowProperties, Point3, Point2, TextNode
from area_43.cameras.free_flying_camera import FreeFlyingCamera
from area_43.tak_level.board import Board
from area_43.tak_level.board_block import BoardBlock
from area_43.tak_level.reserve import Reserve
from area_43.tak_level.flat import Flat
from area_43.tak_level.capstone import Capstone
from area_43.tak_level.table import Table
from area_43.tak_level.stack_handler import StackHandler
from area_43.tak_level.placement_handler import PlacementHandler
from area_43.tak_level.win_resolver import check_win
from area_43.tak_level.tps import game_state_text
from area_43.tak_level.win_panel import WinPanel
from area_43.tak_level.start_menu import StartMenu
from area_43.cameras.orbit_camera import OrbitCamera
from engine.light import AmbientLight, DirectionalLight
from engine.renderer import Renderer
from engine.scene import Scene
from engine.skybox import Skybox

base: ShowBase


class TakScene(Scene):
    MENU_SPIN_SPEED = 6.0  # deg/sec the camera drifts around the board on the menu

    def __init__(self, engine):
        super().__init__(engine, "tak_scene")

        # Debugging Mode
        # self.engine.debug_enabled = True
        self.debug = True

        # Disable Grid
        self.engine.scene_handler.grid.hide()

        # Skybox
        self.skybox = None

        # Lighting
        self.ambient_light = None
        self.sun_light = None

        # Free Flying Camera
        self.free_cam = None
        self.use_free_cam = False

        # Orbit Camera
        self.orbit_cam = None

        # Level
        self.board = None
        self.board_labels = []
        self.reserves = []
        self.table = None

        # Stack handler
        self.stack_handler = None

        # Placement handler
        self.placement_handler = None

        # Turn state (0 = Player 1 / black, 1 = Player 2 / white)
        self.current_player = 0
        self.start_player = 0  # who moves first (chosen at the menu)
        self.move_count = 0  # plies played this game (for the TPS move number)

        # Win state
        self.win_panel = None
        self.game_over = False

        # Start menu
        self.start_menu = None

        # Mouse Boolean
        self.right_mouse_down = False

        # Camera Modes
        self.camera_orbit_mode = 0
        self.camera_free_mode = 1
        self.camera_mode = self.camera_orbit_mode

    def on_enter(self):
        super().on_enter()

        # Skybox
        self.setup_skybox()

        # Lighting
        self.setup_lights()

        # Sound
        # self.setup_sound()

        # Cameras
        self.setup_cameras()

        # Scroll wheel for stack selection
        base.accept("wheel_up", self.on_scroll_up)
        base.accept("wheel_down", self.on_scroll_down)

        # Build the game up front, then overlay the start menu. PLAY just hides
        # the menu so there's no load pause when starting.
        self.setup_level()
        self.show_start_menu()

    def setup_skybox(self):
        self.skybox = Skybox(
            self.engine,
            faces={
                "right": (
                    "assets/skydomes/sky_16_2k/sky_16_cubemap_2k/nx.png",
                    0,
                    True,
                ),
                "left": ("assets/skydomes/sky_16_2k/sky_16_cubemap_2k/px.png", 0, True),
                "top": ("assets/skydomes/sky_16_2k/sky_16_cubemap_2k/py.png", 0, True),
                "bottom": (
                    "assets/skydomes/sky_16_2k/sky_16_cubemap_2k/ny.png",
                    0,
                    False,
                ),
                "front": (
                    "assets/skydomes/sky_16_2k/sky_16_cubemap_2k/nz.png",
                    0,
                    False,
                ),
                "back": (
                    "assets/skydomes/sky_16_2k/sky_16_cubemap_2k/pz.png",
                    0,
                    False,
                ),
            },
        )

    def setup_lights(self):
        self.ambient_light = AmbientLight(
            self.engine, "ambient", color=(0.3, 0.3, 0.3), light_enabled=True
        )
        self.sun_light = DirectionalLight(
            self.engine,
            "sun",
            color=(1, 1, 1),
            direction=(-1, 1, -1),
            position=(0, 0, 10),
            light_enabled=True,
        )

    def setup_sound(self):
        # Ambient sound
        self.engine.sound_player.play(
            "wind", "assets/sounds/wind_000.mp3", loop=True, volume=0.2
        )

    def setup_cameras(self):
        # Setup free camera
        self.free_cam = FreeFlyingCamera(
            self.engine, position=(-4, -7, 4), rotation=(-20.76, -31.88)
        )

        # Setup orbit camera (centered on board at 4, 4)
        self.orbit_cam = OrbitCamera(self.engine, target=(4, 4, 0), distance=15.0)

        # Set initial camera based on mode
        if self.camera_mode == self.camera_orbit_mode:
            self.engine.renderer.set_camera(self.orbit_cam)
        else:
            self.engine.renderer.set_camera(self.free_cam)
        self.engine.input_handler.set_mouse_locked(locked=False)

    def setup_level(self):
        # Create table
        self.table = Table(self.engine,width=30,length=20, x=4, y=4, z=-0.5)

        # Create Board
        self.board = Board(self.engine, size=5)

        # Index Board Blocks - flat labels on each position
        if self.debug:
            self.board_labels = []
            for y in range(5):
                for x in range(5):
                    index = y * 5 + x
                    label_text = chr(ord("A") + index)
                    text = TextNode(f"board_label_{label_text}")
                    text.setText(label_text)
                    text.setTextColor(0, 0, 0, 1)
                    text_node = base.render.attachNewNode(text)
                    text_node.setScale(0.5)
                    wx, wy = BoardBlock.board_to_world(x, y)
                    text_node.setPos(wx - 0.2, wy - 0.2, 0.3)
                    text_node.setP(-90)  # Lay flat (facing down toward camera)
                    text_node.flattenLight()
                    self.board_labels.append(text_node)

        # Create stack handler
        self.stack_handler = StackHandler(self.engine)
        self.stack_handler.set_orbit_camera(self.orbit_cam)

        # Player reserves on the table, in a row in front of each player.
        # The lone front-row stone is the OPPONENT's colour (Tak opening swap):
        # each player's first move places that odd piece.
        # Player 1 (BLACK stones, gold capstone) near edge (-y), odd piece white,
        # board is toward +y
        self.reserves.append(
            Reserve(self.engine, Flat.BLACK, Capstone.GOLD, Flat.WHITE,
                    center_x=4, center_y=-3, board_dir=1)
        )
        # Player 2 (WHITE stones, silver capstone) far edge (+y), odd piece black,
        # board is toward -y
        self.reserves.append(
            Reserve(self.engine, Flat.WHITE, Capstone.SILVER, Flat.BLACK,
                    center_x=4, center_y=11, board_dir=-1)
        )

        # Placement handler (pick reserve pieces, place on the board)
        self.placement_handler = PlacementHandler(
            self.engine, self.reserves, board_size=5, on_place=self.on_piece_placed
        )
        self.placement_handler.set_current_player(self.current_player)

    def handle_input(self, input_handler):
        super().handle_input(input_handler)

        # Skip all input if console is open
        if self.engine.scene_handler.console.is_open:
            return

        # Camera switching
        if input_handler.is_key_down("c"):
            # Switch to Free FLying Camera
            if self.camera_mode == self.camera_orbit_mode:
                # Change Camera Mode
                self.camera_mode = self.camera_free_mode

                # Switch Camera
                self.engine.renderer.set_camera(self.free_cam)

            # Switch to Orbit Camera
            else:
                # Change Camera Mode
                self.camera_mode = self.camera_orbit_mode

                # Switch Camera
                self.engine.renderer.set_camera(self.orbit_cam)

        # Quit
        if input_handler.is_key_down("q"):
            self.engine.quit()

        # Dump the board as TPS + reserves to the console
        if input_handler.is_key_down("t"):
            self.print_state()

        # Reset camera position
        if input_handler.is_key_down("r"):
            if self.camera_mode == self.camera_orbit_mode:
                self.orbit_cam.reset()
            elif self.camera_mode == self.camera_free_mode:
                self.free_cam.reset()

        if self.camera_mode == self.camera_orbit_mode:
            self.orbit_cam.handle_input(input_handler)
            if (self.placement_handler and self.start_menu is None
                    and not self.game_over and not self.orbit_cam.is_animating()):
                self.placement_handler.handle_input(input_handler)
        else:
            # Free camera mode
            # IF mouse 3 then
            if input_handler.is_mouse_pressed(3):
                if not self.right_mouse_down:
                    self.right_mouse_down = True
                    self.engine.input_handler.set_mouse_locked(locked=True)
            # ELSE
            else:
                self.right_mouse_down = False
                self.engine.input_handler.set_mouse_locked(locked=False)

            # Send input to free cam
            self.free_cam.handle_input(input_handler)

    def update(self, dt):
        super().update(dt)

        # Physics
        self.engine.physics.doPhysics(dt)

        # Update stack handler
        if self.stack_handler:
            self.stack_handler.update()

        # Update placement handler (orbit mode only; not while the menu is up)
        if (self.placement_handler and self.start_menu is None
                and self.camera_mode == self.camera_orbit_mode):
            self.placement_handler.update(dt)

        # Camera updates - Skip if console is open
        if not self.engine.scene_handler.console.is_open:
            if self.camera_mode == self.camera_orbit_mode:
                self.orbit_cam.update(dt)

                # Slowly spin around the board while the menu is up
                if self.start_menu is not None:
                    self.orbit_cam.yaw += TakScene.MENU_SPIN_SPEED * dt
                    self.orbit_cam.update_position()

                # Print out camera yaw and pitch
                # print(f"Camera Yaw: {self.orbit_cam.yaw} -- Camera Pitch: {self.orbit_cam.pitch}")
            else:
                self.free_cam.update(dt)

    def on_exit(self):
        super().on_exit()
        if self.ambient_light:
            self.ambient_light.destroy()
        if self.sun_light:
            self.sun_light.destroy()
        if self.skybox:
            self.skybox.destroy()
        if self.win_panel:
            self.win_panel.destroy()
            self.win_panel = None
        if self.start_menu:
            self.start_menu.destroy()
            self.start_menu = None
        self._destroy_level()
        if self.free_cam:
            self.free_cam.destroy()
        if self.orbit_cam:
            self.orbit_cam.destroy()

    def on_piece_placed(self):
        # A turn just completed
        self.move_count += 1

        # Resolve the board for the player who just moved before passing the turn
        mover = self.current_player
        reserves_empty = any(len(r.pieces) == 0 for r in self.reserves)
        outcome = check_win(
            self.placement_handler.board_stacks, self.board.size, mover, reserves_empty
        )
        if outcome is not None:
            self.show_win(outcome)
            return

        # Alternate turns and sweep the camera to the other player's side
        self.current_player = 1 - self.current_player
        self.placement_handler.set_current_player(self.current_player)
        self.orbit_cam.rotate_by(180, duration=1.2)

    def print_state(self):
        # TPS move number is the full-move count (increments after both sides move)
        if not self.placement_handler or not self.board:
            return
        move_number = self.move_count // 2 + 1
        print(game_state_text(
            self.placement_handler.board_stacks, self.board.size,
            self.current_player, move_number, self.reserves,
        ))

    def show_win(self, outcome):
        _kind, winner = outcome
        black = (0, 0, 0, 1)
        white = (1, 1, 1, 1)
        if winner == 0:
            message, bg, fg = "BLACK WON", black, white
        elif winner == 1:
            message, bg, fg = "WHITE WON", white, black
        else:
            message, bg, fg = "DRAW", (0.2, 0.2, 0.2, 1), white
        self.game_over = True
        if self.win_panel:
            self.win_panel.destroy()
        self.win_panel = WinPanel(
            message, bg, fg,
            on_play_again=self.restart_game,
            on_quit_to_menu=self.quit_to_menu,
        )

    def show_start_menu(self):
        if self.start_menu:
            self.start_menu.destroy()
        self.start_menu = StartMenu(
            [("PLAY", self.show_color_menu), ("QUIT", self.engine.quit)],
            credit=True,
        )

    def show_color_menu(self):
        # PLAY -> choose which side moves first.
        if self.start_menu:
            self.start_menu.destroy()
        self.start_menu = StartMenu(
            [("START AS BLACK", lambda: self.start_game(0)),
             ("START AS WHITE", lambda: self.start_game(1))],
        )

    def start_game(self, player):
        # Level is already built; set the starting side, face it, drop the menu.
        self.start_player = player
        self.current_player = player
        if self.placement_handler:
            self.placement_handler.set_current_player(player)
        self._face_player(player)
        if self.start_menu:
            self.start_menu.destroy()
            self.start_menu = None

    def _face_player(self, player):
        # Black (0) sits on -y (yaw 180); white (1) on +y (yaw 0).
        self.orbit_cam.yaw = 0.0 if player == 1 else 180.0
        self.orbit_cam.update_position()

    def quit_to_menu(self):
        # Rebuild a fresh board and show the start menu over it.
        self.restart_game()
        self.show_start_menu()

    def restart_game(self):
        if self.win_panel:
            self.win_panel.destroy()
            self.win_panel = None
        self.game_over = False
        self.current_player = self.start_player
        self.move_count = 0
        self._destroy_level()
        self.setup_level()
        self.orbit_cam.reset()
        self._face_player(self.start_player)

    def _destroy_level(self):
        if self.board:
            self.board.destroy()
            self.board = None
        if self.stack_handler:
            self.stack_handler.destroy()
            self.stack_handler = None
        if self.placement_handler:
            self.placement_handler.destroy()
            self.placement_handler = None
        for reserve in self.reserves:
            reserve.destroy()
        self.reserves = []
        for label in self.board_labels:
            label.removeNode()
        self.board_labels = []
        if self.table:
            self.table.destroy()
            self.table = None

    def on_scroll_up(self):
        # Placement consumes scroll when hovering/holding; otherwise it zooms
        if self.placement_handler and self.placement_handler.handle_scroll(1):
            return
        if self.stack_handler:
            self.stack_handler.on_scroll_up()
        elif self.orbit_cam:
            self.orbit_cam.on_scroll_up()

    def on_scroll_down(self):
        if self.placement_handler and self.placement_handler.handle_scroll(-1):
            return
        if self.stack_handler:
            self.stack_handler.on_scroll_down()
        elif self.orbit_cam:
            self.orbit_cam.on_scroll_down()
