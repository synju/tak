import math
from direct.showbase.ShowBase import ShowBase
from engine.camera import Camera

base: ShowBase


class OrbitCamera(Camera):
    """Orbit camera that rotates around a target point - Blender-style controls"""

    def __init__(
        self,
        engine,
        target=(0, 0, 0),
        distance=5.0,
        yaw=180.0,
        pitch=25.0,
        sensitivity=50,
        #min_distance=0.5,
        min_distance=9,
        #max_distance=100.0,
        max_distance=15.0,
        min_pitch=10, # Default -89
        max_pitch=75, # Default 89
        zoom_speed=0.1,
        pan_speed=0.5,
        near_clip=0.1,
        far_clip=10000,
    ):
        super().__init__(engine, (0, 0, 0), (0, 0, 0), near_clip, far_clip)

        self.target = list(target)
        self.distance = distance
        self.yaw = yaw
        self.pitch = pitch
        self.sensitivity = sensitivity

        self.original_target = list(target)
        self.original_distance = distance
        self.original_yaw = yaw
        self.original_pitch = pitch

        self.min_distance = min_distance
        self.max_distance = max_distance
        self.min_pitch = min_pitch
        self.max_pitch = max_pitch
        self.zoom_speed = zoom_speed
        self.pan_speed = pan_speed

        self.orbiting = False
        self.panning = False
        self.input = None

        # Scroll wheel state
        self.scroll_delta = 0

        # Turn-switch yaw animation
        self.animating = False
        self._anim_from_yaw = 0.0
        self._anim_to_yaw = 0.0
        self._anim_elapsed = 0.0
        self._anim_duration = 1.0

        # Register scroll wheel events
        base.accept("wheel_up", self.on_scroll_up)
        base.accept("wheel_down", self.on_scroll_down)

        self.update_position()

    def activate(self):
        """Activate this camera"""
        self.active = True
        self._apply_clip_distances()
        self.update_position()

    def on_scroll_up(self):
        """Handle scroll wheel up (zoom in)"""
        self.scroll_delta = -1

    def on_scroll_down(self):
        """Handle scroll wheel down (zoom out)"""
        self.scroll_delta = 1

    def update_position(self):
        """Calculate camera position from orbit parameters"""
        yaw_rad = math.radians(self.yaw)
        pitch_rad = math.radians(self.pitch)

        # Spherical to cartesian coordinates
        # Camera orbits around target
        x = self.target[0] + self.distance * math.cos(pitch_rad) * math.sin(yaw_rad)
        y = self.target[1] + self.distance * math.cos(pitch_rad) * math.cos(yaw_rad)
        z = self.target[2] + self.distance * math.sin(pitch_rad)

        self.position = [x, y, z]

        # Apply position and look at target
        if self.active:
            base.camera.setPos(x, y, z)
            base.camera.lookAt(self.target[0], self.target[1], self.target[2])

    def rotate_by(self, delta_yaw, duration=1.0):
        """Smoothly rotate yaw by delta_yaw degrees over duration seconds."""
        self._anim_from_yaw = self.yaw
        self._anim_to_yaw = self.yaw + delta_yaw
        self._anim_elapsed = 0.0
        self._anim_duration = max(0.01, duration)
        self.animating = True

    def is_animating(self):
        return self.animating

    def handle_input(self, input_handler):
        """Handle mouse input for orbiting, panning, and zooming"""
        if not self.active or self.animating:
            return

        self.input = input_handler

        shift_held = input_handler.is_key_pressed("shift")
        middle_mouse = input_handler.is_mouse_pressed(2)

        # Middle mouse + Shift = Pan
        if middle_mouse and shift_held:
            if not self.panning:
                input_handler.set_mouse_locked(True)
                self.panning = True
                self.orbiting = False

            dx, dy = input_handler.mouse_delta
            if dx != 0 or dy != 0:
                # Pan in screen space (camera's local right and up)
                actual_pan_speed = self.distance * self.pan_speed
                yaw_rad = math.radians(self.yaw)
                pitch_rad = math.radians(self.pitch)

                # Camera's right vector (always horizontal)
                right_x = -math.cos(yaw_rad)
                right_y = math.sin(yaw_rad)
                right_z = 0

                # Camera's up vector (perpendicular to view, in view plane)
                # This is the cross product of (view direction) x (right), simplified:
                up_x = -math.sin(pitch_rad) * math.sin(yaw_rad)
                up_y = -math.sin(pitch_rad) * math.cos(yaw_rad)
                up_z = math.cos(pitch_rad)

                # Move target in screen space
                self.target[0] -= (right_x * dx + up_x * dy) * actual_pan_speed
                self.target[1] -= (right_y * dx + up_y * dy) * actual_pan_speed
                self.target[2] -= (right_z * dx + up_z * dy) * actual_pan_speed

                self.update_position()

        # Middle mouse (no shift) = Orbit
        elif middle_mouse and not shift_held:
            if not self.orbiting:
                input_handler.set_mouse_locked(True)
                self.orbiting = True
                self.panning = False

            dx, dy = input_handler.mouse_delta
            if dx != 0 or dy != 0:
                # Blender-style: drag right = view rotates right
                self.yaw += dx * self.sensitivity
                self.pitch -= dy * self.sensitivity
                self.pitch = max(self.min_pitch, min(self.max_pitch, self.pitch))
                self.update_position()

        # Release mouse lock when middle mouse released
        else:
            if self.orbiting or self.panning:
                input_handler.set_mouse_locked(False)
                self.orbiting = False
                self.panning = False

    def update(self, dt, imgui_wants_mouse=False):
        """Update camera - handle scroll zoom"""
        if not self.active:
            return

        # Turn-switch yaw animation (smoothstep ease)
        if self.animating:
            self._anim_elapsed += dt
            t = min(1.0, self._anim_elapsed / self._anim_duration)
            s = t * t * (3 - 2 * t)
            self.yaw = self._anim_from_yaw + (self._anim_to_yaw - self._anim_from_yaw) * s
            self.update_position()
            if t >= 1.0:
                self.animating = False

        # Handle scroll wheel zoom (only if UI doesn't want mouse)
        if self.scroll_delta != 0 and not imgui_wants_mouse:
            zoom_factor = 1 + self.scroll_delta * self.zoom_speed
            self.distance *= zoom_factor
            self.distance = max(
                self.min_distance, min(self.max_distance, self.distance)
            )
            self.update_position()

        # Always reset scroll delta
        self.scroll_delta = 0

    def zoom(self, amount):
        """Zoom in/out by amount (positive = zoom out)"""
        self.distance *= 1 + amount * self.zoom_speed
        self.distance = max(self.min_distance, min(self.max_distance, self.distance))
        self.update_position()

    def set_target(self, x, y, z):
        """Set the orbit target point"""
        self.target = [x, y, z]
        self.update_position()

    def frame_object(self, center, size):
        """Frame camera to view an object"""
        self.target = list(center)
        self.distance = size * 2.5
        self.update_position()

    def reset(self):
        """Reset camera to default or specified view"""
        self.target = list(self.original_target)
        self.distance = self.original_distance
        self.yaw = self.original_yaw
        self.pitch = self.original_pitch
        self.update_position()

    def destroy(self):
        """Clean up event handlers"""
        base.ignore("wheel_up")
        base.ignore("wheel_down")