import os
import queue
import random
import threading

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
from area_43.tak_level.difficulty_menu import DifficultyMenu
from area_43.ai.play import load_opponent
from area_43.cameras.orbit_camera import OrbitCamera
from engine.light import AmbientLight, DirectionalLight
from engine.renderer import Renderer
from engine.scene import Scene
from engine.skybox import Skybox

base: ShowBase


NN_DIR = os.path.join(os.path.dirname(__file__), "..", "test_nn")  # one .pt to play vs


class TakScene(Scene):
    MENU_SPIN_SPEED = 6.0  # deg/sec the camera drifts around the board on the menu
    BOT_DELAY = 0.6        # seconds the bot "thinks" before moving
    NN_REPLAY_SECONDS = 5.0  # countdown after a result before the next NN vs NN match

    def __init__(self, engine, turn_time=2.0):
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

        # Bot opponent config (set via the PLAY BOT menu; bot brain not built yet)
        self.vs_bot = False
        self.bot_player = None  # which side the bot plays
        self.bot_level = None   # difficulty 1 (easiest) .. 10 (hardest)
        self.bot_pending = False
        self.bot_timer = 0.0
        self.bot_thread = None   # worker computing the bot's move (off main thread)
        self.bot_queue = None
        self.nn_opponent = None  # set for a PLAY NN game; reuses the bot turn pipeline

        # NN vs NN watch mode
        self.nn_vs_nn = False
        self.nn_turn_time = turn_time   # seconds per NN move (CLI --turn-time)
        self.menu_button = None         # top-left BACK TO MENU button
        self.nn_result = None           # result + countdown overlay
        self.nn_countdown_label = None
        self.replay_pending = False
        self.replay_timer = 0.0

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
                    and not self.game_over and not self.orbit_cam.is_animating()
                    and not (self.vs_bot and self.current_player == self.bot_player)):
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
                and not self.nn_vs_nn  # watch mode: no human placement
                and self.camera_mode == self.camera_orbit_mode):
            self.placement_handler.update(dt)

        # Bot's turn: brief delay, then think on a worker thread (so the game
        # doesn't freeze), then apply the move back on the main thread.
        if self.start_menu is None and not self.game_over:
            if self.bot_pending and not self.orbit_cam.is_animating():
                self.bot_timer -= dt
                if self.bot_timer <= 0.0:
                    self.bot_pending = False
                    self._start_bot_thinking()
            elif self.bot_thread is not None and not self.bot_thread.is_alive():
                self._finish_bot_move()

        # NN vs NN: after a result, count down, then auto-start the next match.
        if self.nn_vs_nn and self.game_over and self.replay_pending:
            self.replay_timer -= dt
            secs = max(0, int(self.replay_timer) + 1)
            if self.nn_countdown_label:
                self.nn_countdown_label["text"] = f"next match in {secs}..."
            if self.replay_timer <= 0.0:
                self.replay_pending = False
                self._restart_nn_match()

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
        if self.menu_button:
            self.menu_button.destroy()
            self.menu_button = None
        if self.nn_result:
            self.nn_result.destroy()
            self.nn_result = None
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

        # Alternate turns
        self.current_player = 1 - self.current_player
        self.placement_handler.set_current_player(self.current_player)

        if self.nn_vs_nn:
            # Both sides are the NN; queue the next move after the turn delay.
            self.bot_pending = True
            self.bot_timer = self.nn_turn_time
        elif self.vs_bot:
            # Camera stays on the human's side; queue the bot if it's its turn.
            if self.current_player == self.bot_player:
                self.bot_pending = True
                self.bot_timer = TakScene.BOT_DELAY
        else:
            # Hotseat: sweep the camera to the other player's side.
            self.orbit_cam.rotate_by(180, duration=1.2)

    def _start_bot_thinking(self):
        # Snapshot the position on the main thread (reads live pieces), then run
        # the pure search on a worker; build_state copies into plain data.
        state = self.placement_handler.build_state()
        if self.nn_vs_nn:
            think = lambda: self._nn_vs_nn_move(state)
        elif self.nn_opponent is not None:
            think = lambda: self.nn_opponent.policy_move(state)
        else:
            from area_43.tak_level.tak_bot import choose_move
            level = self.bot_level
            think = lambda: choose_move(state, level)
        self.bot_queue = queue.Queue(maxsize=1)
        self.bot_thread = threading.Thread(
            target=lambda: self.bot_queue.put(think()),
            daemon=True,
        )
        self.bot_thread.start()

    def _finish_bot_move(self):
        move = self.bot_queue.get()
        self.bot_thread = None
        self.bot_queue = None
        if move is not None:
            self.placement_handler.apply_move(move)

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
        if self.nn_vs_nn:
            self._show_nn_result(message, bg, fg)  # result + countdown, auto-replays
            return
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
            [("PLAY", self.show_color_menu),
             ("PLAY BOT", self.show_bot_color_menu),
             ("PLAY NN", self.show_nn_color_menu),
             ("NN vs NN", self.show_nn_vs_nn_menu),
             ("QUIT", self.engine.quit)],
            credit=True,
        )

    def show_color_menu(self):
        # PLAY -> choose which side moves first (two human players).
        if self.start_menu:
            self.start_menu.destroy()
        self.start_menu = StartMenu(
            [("START AS BLACK", lambda: self.start_game(0)),
             ("START AS WHITE", lambda: self.start_game(1))],
        )

    def show_bot_color_menu(self):
        # PLAY BOT -> choose the human's side, then difficulty.
        if self.start_menu:
            self.start_menu.destroy()
        self.start_menu = StartMenu(
            [("START AS BLACK", lambda: self.show_difficulty_menu(0)),
             ("START AS WHITE", lambda: self.show_difficulty_menu(1))],
        )

    def show_difficulty_menu(self, human_player):
        if self.start_menu:
            self.start_menu.destroy()
        self.start_menu = DifficultyMenu(
            on_select=lambda level: self.start_bot_game(human_player, level)
        )

    def show_nn_color_menu(self):
        # PLAY NN -> choose the human's side; the NN takes the other.
        if self.start_menu:
            self.start_menu.destroy()
        self.start_menu = StartMenu(
            [("START AS BLACK", lambda: self.start_nn_game(0)),
             ("START AS WHITE", lambda: self.start_nn_game(1))],
        )

    def start_nn_game(self, human_player):
        # Load the single model in test_nn/; bail back to the menu if none is there.
        opponent = load_opponent(NN_DIR)
        if opponent is None:
            print(f"[PLAY NN] no .pt model found in {os.path.normpath(NN_DIR)}")
            self.show_start_menu()
            return
        print(f"[PLAY NN] loaded {opponent.name} on {opponent.device}")
        self.start_game(human_player)        # clears flags + nn_opponent, faces side
        self.vs_bot = True                   # reuse the bot turn pipeline
        self.bot_player = 1 - human_player
        self.nn_opponent = opponent

    def show_nn_vs_nn_menu(self):
        # NN vs NN -> pick how long each NN waits per move, then start.
        if self.start_menu:
            self.start_menu.destroy()
        options = [("0.5 SECONDS", 0.5), ("1 SECOND", 1.0), ("2 SECONDS", 2.0),
                   ("3 SECONDS", 3.0), ("5 SECONDS", 5.0)]
        self.start_menu = StartMenu(
            [(label, lambda t=t: self.start_nn_vs_nn(t)) for label, t in options],
        )

    def start_nn_vs_nn(self, turn_time=None):
        # Watch the test_nn model play itself, match after match (no search).
        if turn_time is not None:
            self.nn_turn_time = turn_time
        opponent = load_opponent(NN_DIR)
        if opponent is None:
            print(f"[NN vs NN] no .pt model found in {os.path.normpath(NN_DIR)}")
            self.show_start_menu()
            return
        print(f"[NN vs NN] loaded {opponent.name} on {opponent.device}")
        self.start_game(0)            # fresh board, black first; clears flags
        self.nn_vs_nn = True
        self.nn_opponent = opponent
        self._show_menu_button()
        self.bot_pending = True       # kick off the first move
        self.bot_timer = self.nn_turn_time

    def _nn_vs_nn_move(self, state):
        # First move of each side is a random flat; afterwards the bare policy head.
        if not state.opening_done[state.to_move]:
            from area_43.tak_level.tak_rules import generate_moves
            return random.choice(generate_moves(state))
        return self.nn_opponent.policy_move(state)

    def _show_nn_result(self, message, bg, fg):
        from direct.gui.DirectGui import DirectFrame, DirectLabel
        if self.nn_result:
            self.nn_result.destroy()
        self.nn_result = DirectFrame(
            frameColor=bg, frameSize=(-0.6, 0.6, -0.3, 0.3), pos=(0, 0, 0))
        DirectLabel(parent=self.nn_result, text=message, text_fg=fg,
                    text_scale=0.13, frameColor=(0, 0, 0, 0), pos=(0, 0, 0.05))
        self.nn_countdown_label = DirectLabel(
            parent=self.nn_result, text="", text_fg=fg, text_scale=0.05,
            frameColor=(0, 0, 0, 0), pos=(0, 0, -0.12))
        self.replay_pending = True
        self.replay_timer = TakScene.NN_REPLAY_SECONDS

    def _restart_nn_match(self):
        if self.nn_result:
            self.nn_result.destroy()
            self.nn_result = None
        self.nn_countdown_label = None
        self.restart_game(reset_camera=False)  # keep the camera where you left it
        self.bot_pending = True       # kick off the next match's first move
        self.bot_timer = self.nn_turn_time

    def _show_menu_button(self):
        from direct.gui.DirectGui import DirectButton
        from direct.gui import DirectGuiGlobals as DGG
        if self.menu_button:
            return
        self.menu_button = DirectButton(
            parent=base.a2dTopLeft, text="BACK TO MENU",
            text_scale=0.045, text_pos=(0, -0.013), text_fg=(1, 1, 1, 1),
            frameColor=(0.15, 0.15, 0.15, 1), frameSize=(-0.18, 0.18, -0.05, 0.05),
            relief=DGG.FLAT, pos=(0.22, 0, -0.1), command=self._nn_vs_nn_to_menu)

    def _nn_vs_nn_to_menu(self):
        self.nn_vs_nn = False
        self.replay_pending = False
        self.bot_pending = False
        self.bot_thread = None        # abandon any in-flight move worker
        if self.menu_button:
            self.menu_button.destroy()
            self.menu_button = None
        if self.nn_result:
            self.nn_result.destroy()
            self.nn_result = None
        self.nn_countdown_label = None
        self.restart_game()           # fresh board under the menu
        self.show_start_menu()

    def start_bot_game(self, human_player, level):
        # Human plays human_player; bot takes the other side.
        self.start_game(human_player)
        self.vs_bot = True
        self.bot_player = 1 - human_player
        self.bot_level = level

    def start_game(self, player):
        # Level is already built; set the starting side, face it, drop the menu.
        self.vs_bot = False
        self.nn_opponent = None  # cleared here; set afterwards only for a PLAY NN game
        self.bot_pending = False
        self.bot_thread = None  # abandon any in-flight worker from a prior game
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

    def restart_game(self, reset_camera=True):
        if self.win_panel:
            self.win_panel.destroy()
            self.win_panel = None
        self.game_over = False
        self.bot_pending = False
        self.bot_thread = None  # abandon any in-flight worker from a prior game
        self.current_player = self.start_player
        self.move_count = 0
        self._destroy_level()
        self.setup_level()
        if reset_camera:  # NN vs NN keeps wherever you left the camera
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
