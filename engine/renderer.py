from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
	NodePath, CardMaker, TextNode, WindowProperties,
	GeomVertexFormat, GeomVertexData, GeomVertexWriter,
	Geom, GeomLines, GeomTriangles, GeomNode,
	Vec4, LColor, GraphicsOutput, Texture, Filename, PNMImage
)
import simplepbr
import sys

# Global created by ShowBase
base: ShowBase

class Renderer:
	"""Handles window and all rendering"""

	def __init__(self, width=1280, height=720, title="Peach Engine", fullscreen=False):
		self._title = title
		self._fullscreen = fullscreen
		self.background_color = (0, 0, 0, 1)

		# Current camera (set by scene handler)
		self.camera = None

		# Setup window
		self._setup_window(width, height, title, fullscreen)

		# Setup camera defaults
		self._setup_camera()

		# Debug drawing node (for immediate mode style drawing)
		self._debug_node = NodePath('debug_draw')
		self._debug_node.reparentTo(base.render)
		self._frame_draws = []

	def _setup_window(self, width, height, title, fullscreen):
		"""Setup window properties"""
		props = WindowProperties()
		props.setTitle(title)

		if fullscreen:
			props.setFullscreen(True)
			props.setSize(base.pipe.getDisplayWidth(), base.pipe.getDisplayHeight())
		else:
			props.setSize(width, height)

		base.win.requestProperties(props)
		base.setBackgroundColor(*self.background_color)

		# Maximize window after a short delay
		base.taskMgr.doMethodLater(0.1, self._maximize_window, 'maximize')

	def _maximize_window(self, task):
		"""Maximize window using OS-specific API"""
		if sys.platform == 'win32':
			try:
				import ctypes
				hwnd = ctypes.windll.user32.FindWindowW(None, self._title)
				if hwnd:
					SW_MAXIMIZE = 3
					ctypes.windll.user32.ShowWindow(hwnd, SW_MAXIMIZE)
			except:
				pass
		elif sys.platform == 'linux':
			try:
				import subprocess
				subprocess.run(['wmctrl', '-r', self._title, '-b', 'add,maximized_vert,maximized_horz'],
											 capture_output=True)
			except:
				pass

		return task.done

	def _setup_depth_texture(self):
		"""Get depth texture from renderer (simplepbr's buffer)"""
		self._depth_tex = self.engine.renderer.depth_tex

	def set_environment_map(self, cubemap_dir):
		"""Use a 6-face cube map as the PBR reflection/IBL source.

		Expects px/nx/py/ny/pz/nz .png faces in cubemap_dir. Without this,
		metallic materials have nothing to reflect and render flat/dark.
		"""
		faces = ["px", "nx", "py", "ny", "pz", "nz"]  # +X,-X,+Y,-Y,+Z,-Z
		imgs = []
		for f in faces:
			img = PNMImage()
			if not img.read(Filename(f"{cubemap_dir}/{f}.png")):
				print(f"Renderer: env map face missing: {cubemap_dir}/{f}.png")
				return
			imgs.append(img)

		cube = Texture("env_cubemap")
		cube.setupCubeMap(imgs[0].getXSize(), Texture.TUnsignedByte, Texture.FRgb)
		for i, img in enumerate(imgs):
			cube.load(img, i, 0)

		self.pipeline.env_map = simplepbr.EnvMap(cube, blocking_prepare=True)

	def _setup_camera(self):
		"""Setup camera defaults"""
		base.camLens.setFov(90)
		base.disableMouse()

		self.pipeline = simplepbr.init(enable_fog=True)

		if self.pipeline._filtermgr:
			buf = self.pipeline._filtermgr.buffers[0]

			# Add depth texture
			self.depth_tex = Texture("simplepbr_depth")
			buf.addRenderTexture(self.depth_tex, GraphicsOutput.RTMBindOrCopy, GraphicsOutput.RTPDepth)

			# Add color texture
			self.color_tex = Texture("simplepbr_color")
			buf.addRenderTexture(self.color_tex, GraphicsOutput.RTMBindOrCopy, GraphicsOutput.RTPColor)

	# Window properties
	@property
	def width(self):
		"""Get window width"""
		return base.win.getXSize()

	@property
	def height(self):
		"""Get window height"""
		return base.win.getYSize()

	def get_width(self):
		"""Get window width"""
		return self.width

	def get_height(self):
		"""Get window height"""
		return self.height

	def get_size(self):
		"""Get window size as tuple"""
		return (self.width, self.height)

	def set_title(self, title):
		"""Set window title"""
		self._title = title
		props = WindowProperties()
		props.setTitle(title)
		base.win.requestProperties(props)

	def set_fullscreen(self, fullscreen):
		"""Set fullscreen mode"""
		self._fullscreen = fullscreen
		props = WindowProperties()
		if fullscreen:
			props.setFullscreen(True)
			props.setSize(base.pipe.getDisplayWidth(), base.pipe.getDisplayHeight())
		else:
			props.setFullscreen(False)
		base.win.requestProperties(props)

	def is_fullscreen(self):
		"""Check if window is fullscreen"""
		return self._fullscreen

	def set_background_color(self, r, g, b, a=1):
		"""Set the background/clear color"""
		self.background_color = (r, g, b, a)
		base.setBackgroundColor(r, g, b, a)

	def set_camera(self, camera):
		"""Set the active camera for rendering"""
		# Deactivate old camera
		if self.camera:
			self.camera.deactivate()

		self.camera = camera

		# Activate new camera
		if camera:
			camera.activate()

	def get_camera(self):
		"""Get the active camera"""
		return self.camera

	def clear(self):
		"""Clear frame debug draws"""
		for node in self._frame_draws:
			node.removeNode()
		self._frame_draws.clear()

	def flip(self):
		"""Called after rendering (Panda3D handles this automatically)"""
		pass

	# 3D Drawing functions
	def draw_line_3d(self, start, end, color=(1, 1, 1, 1), thickness=1):
		"""Draw a 3D line"""
		format = GeomVertexFormat.get_v3c4()
		vdata = GeomVertexData('line', format, Geom.UHStatic)
		vdata.setNumRows(2)

		vertex = GeomVertexWriter(vdata, 'vertex')
		color_writer = GeomVertexWriter(vdata, 'color')

		vertex.addData3(*start)
		vertex.addData3(*end)
		color_writer.addData4(*color)
		color_writer.addData4(*color)

		lines = GeomLines(Geom.UHStatic)
		lines.addVertices(0, 1)
		lines.closePrimitive()

		geom = Geom(vdata)
		geom.addPrimitive(lines)

		node = GeomNode('line')
		node.addGeom(geom)

		np = self._debug_node.attachNewNode(node)
		np.setRenderModeThickness(thickness)
		self._frame_draws.append(np)
		return np

	def draw_box_3d(self, center, size, color=(1, 1, 1, 1)):
		"""Draw a 3D wireframe box"""
		x, y, z = center
		sx, sy, sz = size if isinstance(size, (list, tuple)) else (size, size, size)
		hsx, hsy, hsz = sx / 2, sy / 2, sz / 2

		# 8 corners
		corners = [
			(x - hsx, y - hsy, z - hsz),
			(x + hsx, y - hsy, z - hsz),
			(x + hsx, y + hsy, z - hsz),
			(x - hsx, y + hsy, z - hsz),
			(x - hsx, y - hsy, z + hsz),
			(x + hsx, y - hsy, z + hsz),
			(x + hsx, y + hsy, z + hsz),
			(x - hsx, y + hsy, z + hsz),
		]

		# 12 edges
		edges = [
			(0, 1), (1, 2), (2, 3), (3, 0),  # bottom
			(4, 5), (5, 6), (6, 7), (7, 4),  # top
			(0, 4), (1, 5), (2, 6), (3, 7),  # vertical
		]

		for i, j in edges:
			self.draw_line_3d(corners[i], corners[j], color)

	def draw_sphere_3d(self, center, radius, color=(1, 1, 1, 1), segments=16):
		"""Draw a 3D wireframe sphere (circles on 3 axes)"""
		import math
		x, y, z = center

		# Draw 3 circles for each axis
		for axis in range(3):
			points = []
			for i in range(segments + 1):
				angle = 2 * math.pi * i / segments
				if axis == 0:  # YZ plane
					px, py, pz = x, y + radius * math.cos(angle), z + radius * math.sin(angle)
				elif axis == 1:  # XZ plane
					px, py, pz = x + radius * math.cos(angle), y, z + radius * math.sin(angle)
				else:  # XY plane
					px, py, pz = x + radius * math.cos(angle), y + radius * math.sin(angle), z
				points.append((px, py, pz))

			for i in range(len(points) - 1):
				self.draw_line_3d(points[i], points[i + 1], color)

	def draw_grid(self, size=30, color=(0.5, 0.5, 0.5, 1)):
		"""Draw a grid on the XY plane"""
		half = size // 2

		for i in range(-half, half + 1):
			# Lines along X
			self.draw_line_3d((i, -half, 0), (i, half, 0), color)
			# Lines along Y
			self.draw_line_3d((-half, i, 0), (half, i, 0), color)

	def draw_axes(self, origin=(0, 0, 0), length=5):
		"""Draw XYZ axes at origin"""
		x, y, z = origin
		self.draw_line_3d(origin, (x + length, y, z), (1, 0, 0, 1))  # X = red
		self.draw_line_3d(origin, (x, y + length, z), (0, 1, 0, 1))  # Y = green
		self.draw_line_3d(origin, (x, y, z + length), (0, 0, 1, 1))  # Z = blue

	# 2D Drawing functions (for UI/HUD)
	def draw_rect_2d(self, x, y, width, height, color=(1, 1, 1, 1), filled=True):
		"""Draw a 2D rectangle on screen"""
		cm = CardMaker('rect')
		cm.setFrame(0, width, -height, 0)

		if filled:
			cm.setColor(*color)

		np = base.pixel2d.attachNewNode(cm.generate())
		np.setPos(x, 0, -y)

		if not filled:
			np.setTransparency(1)
			np.setColorScale(*color)

		self._frame_draws.append(np)
		return np

	def draw_text_2d(self, text, x, y, color=(1, 1, 1, 1), size=16, align='left'):
		"""Draw 2D text on screen"""
		text_node = TextNode('text')
		text_node.setText(text)
		text_node.setTextColor(*color)

		if align == 'center':
			text_node.setAlign(TextNode.ACenter)
		elif align == 'right':
			text_node.setAlign(TextNode.ARight)
		else:
			text_node.setAlign(TextNode.ALeft)

		np = base.pixel2d.attachNewNode(text_node)
		np.setScale(size)
		np.setPos(x, 0, -y)

		self._frame_draws.append(np)
		return np