from direct.showbase.ShowBase import ShowBase
from panda3d.core import WindowProperties, Point3, Point2, TextNode
from area_43.cameras.free_flying_camera import FreeFlyingCamera
from area_43.tak_level.board import Board
from area_43.tak_level.board_block import BoardBlock
from area_43.tak_level.flat import Flat
from area_43.tak_level.table import Table
from area_43.tak_level.stack import Stack
from area_43.tak_level.stack_handler import StackHandler
from area_43.cameras.orbit_camera import OrbitCamera
from engine.light import AmbientLight, DirectionalLight
from engine.renderer import Renderer
from engine.scene import Scene
from engine.skybox import Skybox

base: ShowBase


class TakScene(Scene):
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
        self.board_blocks = []
        self.board_labels = []
        self.flats = []
        self.table = None

        # Stack handler
        self.stack_handler = None

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

        # Level
        self.setup_level()

        # Scroll wheel for stack selection
        base.accept("wheel_up", self.on_scroll_up)
        base.accept("wheel_down", self.on_scroll_down)

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
        self.orbit_cam = OrbitCamera(self.engine, target=(4, 4, 0), distance=14.0)

        # Set initial camera based on mode
        if self.camera_mode == self.camera_orbit_mode:
            self.engine.renderer.set_camera(self.orbit_cam)
        else:
            self.engine.renderer.set_camera(self.free_cam)
        self.engine.input_handler.set_mouse_locked(locked=False)

    def setup_level(self):
        # Create table
        self.table = Table(self.engine,width=30,length=14, x=4, y=4, z=-0.5)

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
                    text_node.setPos((x * 2) - 0.2, (y * 2) - 0.2, 0.3)
                    text_node.setP(-90)  # Lay flat (facing down toward camera)
                    text_node.flattenLight()
                    self.board_labels.append(text_node)

        # Create stack handler
        self.stack_handler = StackHandler(self.engine)
        self.stack_handler.set_orbit_camera(self.orbit_cam)

        # Create a stack of 4 flats on top of first board block
        layer_index = 0
        colors = [Flat.BLACK, Flat.WHITE]
        for color in colors:
            flat = Flat(self.engine, color, x=0, y=0, layer_index=layer_index)
            self.flats.append(flat)
            layer_index += 1

        # Place a stack at 1,2
        stack = Stack(board_x=1, board_y=2)
        stack.push(self.engine, Flat.BLACK)
        stack.push(self.engine, Flat.BLACK)
        stack.push(self.engine, Flat.BLACK)
        stack.push(self.engine, Flat.BLACK)
        stack.push(self.engine, Flat.BLACK)
        stack.push(self.engine, Flat.BLACK)
        stack.push(self.engine, Flat.BLACK)
        stack.push(self.engine, Flat.BLACK)
        self.stack_handler.add_stack(stack)

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

        # Reset camera position
        if input_handler.is_key_down("r"):
            if self.camera_mode == self.camera_orbit_mode:
                self.orbit_cam.reset()
            elif self.camera_mode == self.camera_free_mode:
                self.free_cam.reset()

        if self.camera_mode == self.camera_orbit_mode:
            self.orbit_cam.handle_input(input_handler)
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

        # Camera updates - Skip if console is open
        if not self.engine.scene_handler.console.is_open:
            if self.camera_mode == self.camera_orbit_mode:
                self.orbit_cam.update(dt)

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
        for block in self.board_blocks:
            block.destroy()
        for flat in self.flats:
            flat.destroy()
        for label in self.board_labels:
            label.removeNode()
        if self.table:
            self.table.destroy()
        if self.free_cam:
            self.free_cam.destroy()
        if self.orbit_cam:
            self.orbit_cam.destroy()

    def on_scroll_up(self):
        if self.stack_handler:
            self.stack_handler.on_scroll_up()
        elif self.orbit_cam:
            self.orbit_cam.on_scroll_up()

    def on_scroll_down(self):
        if self.stack_handler:
            self.stack_handler.on_scroll_down()
        elif self.orbit_cam:
            self.orbit_cam.on_scroll_down()
