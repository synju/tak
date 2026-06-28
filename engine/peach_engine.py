from direct.showbase.ShowBase import ShowBase
from panda3d.bullet import BulletWorld
from panda3d.core import loadPrcFileData
import sys

from engine.gui.gui_handler import GUIHandler

# Configure Panda3D before creating ShowBase
loadPrcFileData('', 'window-title Peach Engine')

# Global created by ShowBase
base: ShowBase

class PeachEngine(ShowBase):
	"""Main game engine - controls everything"""

	def __init__(self, width=1280, height=720, title="Peach Engine", fps=60, fullscreen=False):
		ShowBase.__init__(self)

		self.title = title
		self.fps = fps
		self.fps_unlimited = False
		self.running = True
		self._debug_enabled = True

		# Import after ShowBase is created (so 'base' exists)
		from .input_handler import InputHandler
		from .renderer import Renderer
		from .sound_player import SoundPlayer
		from .utils import Utils
		from .scene_handler import SceneHandler

		# Core components
		self.input_handler = InputHandler()
		self.renderer = Renderer(width, height, title, fullscreen)
		self.sound_player = SoundPlayer()
		self.utils = Utils(self)
		self.scene_handler = SceneHandler(self)
		self.gui_handler = GUIHandler(self)

		# Give scene_handler reference to renderer
		self.scene_handler.renderer = self.renderer

		# Delta time
		self.dt = 0

		# Register main loop
		self.taskMgr.add(self._main_loop, 'main_loop')

		# Apply initial debug visibility
		self.scene_handler._update_debug_visibility()

		self.physics = BulletWorld()
		self.physics.setGravity(0, 0, -9.81)

		# Welcome message
		print(f"Peach Engine initialized - {width}x{height}")

	@property
	def debug_enabled(self):
		return self._debug_enabled

	@debug_enabled.setter
	def debug_enabled(self, value):
		self._debug_enabled = value
		self.scene_handler._update_debug_visibility()

	def _main_loop(self, task):
		"""Main game loop"""
		if not self.running:
			self.quit()
			return task.done

		# Calculate delta time
		self.dt = globalClock.getDt()

		# Cap dt to prevent huge jumps
		if self.dt > 0.1:
			self.dt = 0.1

		# Main loop steps
		self._handle_input()
		self._update(self.dt)
		self._render()

		return task.cont

	def _handle_input(self):
		"""Process input events"""
		self.input_handler.update()

		# Pass input to scene handler first so scenes can intercept escape
		self.scene_handler.handle_input(self.input_handler)

		# Quit only if the scene didn't consume escape
		if self.input_handler.is_key_down('escape') and not self.scene_handler.escape_consumed:
			self.running = False

	def _update(self, dt):
		"""Update current scene"""
		self.scene_handler.update(dt)

	def _render(self):
		"""Render current scene"""
		self.scene_handler.render(self.renderer)

	def run(self):
		"""Start the main game loop"""
		try:
			ShowBase.run(self)
		except SystemExit:
			pass

	def quit(self):
		"""Clean shutdown"""
		print("Peach Engine shutting down...")

		# Cleanup scene handler
		if self.scene_handler:
			self.scene_handler.cleanup()

		# Cleanup sound
		if self.sound_player:
			self.sound_player.cleanup()

		sys.exit(0)