from direct.showbase.ShowBase import ShowBase

from engine.console import Console

# Global created by ShowBase
base: ShowBase

class SceneHandler:
	"""Manages scenes, debug UI, and scene transitions"""

	def __init__(self, engine, grid_size=30):
		self.engine = engine
		self.scenes = {}
		self.current_scene = None
		self.current_scene_name = None

		# Renderer reference (set by engine)
		self.renderer = None
		self.escape_consumed = False

		# Debug elements
		self.grid_size = grid_size
		self.grid = None
		self.debug_ui = None

		# Setup debug elements
		self._setup_debug()

		# Console (always available)
		self.console = Console(engine, toggle_key='`')
		self.console.print("Engine started")

	def _setup_debug(self):
		"""Setup debug grid and UI"""
		from .debug_ui import DebugUI
		from . import colors

		# Create debug grid
		self.grid = self.engine.utils.create_grid(self.grid_size, colors.gray)
		self.grid.reparentTo(base.render)

		# Create debug UI
		self.debug_ui = DebugUI()

	def _update_debug_visibility(self):
		"""Show/hide debug elements based on engine.debug_enabled"""
		if self.grid:
			if self.engine.debug_enabled:
				self.grid.show()
			else:
				self.grid.hide()

		if self.debug_ui:
			self.debug_ui.set_visible(self.engine.debug_enabled)

	# Scene management
	def add_scene(self, name, scene):
		"""Add a scene to the handler"""
		self.scenes[name] = scene
		scene.name = name
		scene.scene_handler = self

	def get_scene(self, name):
		"""Get a scene by name"""
		return self.scenes.get(name)

	def set_scene(self, name):
		"""Switch to a different scene"""
		if name not in self.scenes:
			print(f"Scene '{name}' not found")
			return False

		# Exit current scene
		if self.current_scene:
			self.current_scene.on_exit()

		# Enter new scene
		self.current_scene = self.scenes[name]
		self.current_scene_name = name
		self.current_scene.on_enter()

		return True

	# Event handling
	def handle_input(self, input_handler):
		"""Handle input for current scene"""
		self.escape_consumed = False
		if self.current_scene:
			self.current_scene.handle_input(input_handler)

	def update(self, dt):
		"""Update the current scene"""
		if self.current_scene:
			self.current_scene.update(dt)

		# Update debug UI with camera info
		if self.debug_ui:
			if self.engine.debug_enabled and self.renderer and self.renderer.camera:
				self.debug_ui.update_values(
					self.renderer.camera.position,
					self.renderer.camera.rotation
				)
			self.debug_ui.update()

	def render(self, renderer):
		"""Render the current scene"""
		# Clear any previous frame draws
		renderer.clear()

		# Render current scene
		if self.current_scene:
			self.current_scene.render(renderer)

		# Flip (Panda3D handles this automatically)
		renderer.flip()

	def cleanup(self):
		"""Cleanup all scenes"""
		if self.current_scene:
			self.current_scene.on_exit()

		for scene in self.scenes.values():
			if hasattr(scene, 'destroy'):
				scene.destroy()

		self.scenes.clear()
		self.current_scene = None

		# Clear camera from renderer
		if self.renderer:
			self.renderer.set_camera(None)

		# Cleanup debug elements
		if self.grid:
			self.grid.removeNode()
		if self.debug_ui:
			self.debug_ui.container.destroy()

		# Cleanup console
		if self.console:
			self.console.destroy()