from panda3d.core import GeomVertexFormat, GeomVertexData, GeomVertexWriter
from panda3d.core import Geom, GeomTriangles, GeomNode, Vec3, LineSegs


def _box_faces(hw, hh, hl, ox, oy, oz):
	"""The 6 faces (verts + normals) of a box centered at (ox, oy, oz)."""
	return [
		# face 0: -X (left)
		{
			"verts": [
				(ox - hw, oy - hl, oz - hh),
				(ox - hw, oy + hl, oz - hh),
				(ox - hw, oy + hl, oz + hh),
				(ox - hw, oy - hl, oz + hh),
			],
			"norms": [(-1, 0, 0)] * 4,
		},
		# face 1: +X (right)
		{
			"verts": [
				(ox + hw, oy - hl, oz + hh),
				(ox + hw, oy + hl, oz + hh),
				(ox + hw, oy + hl, oz - hh),
				(ox + hw, oy - hl, oz - hh),
			],
			"norms": [(1, 0, 0)] * 4,
		},
		# face 2: -Y (back)
		{
			"verts": [
				(ox + hw, oy - hl, oz - hh),
				(ox + hw, oy - hl, oz + hh),
				(ox - hw, oy - hl, oz + hh),
				(ox - hw, oy - hl, oz - hh),
			],
			"norms": [(0, -1, 0)] * 4,
		},
		# face 3: +Y (front)
		{
			"verts": [
				(ox - hw, oy + hl, oz - hh),
				(ox - hw, oy + hl, oz + hh),
				(ox + hw, oy + hl, oz + hh),
				(ox + hw, oy + hl, oz - hh),
			],
			"norms": [(0, 1, 0)] * 4,
		},
		# face 4: -Z (bottom)
		{
			"verts": [
				(ox - hw, oy - hl, oz - hh),
				(ox + hw, oy - hl, oz - hh),
				(ox + hw, oy + hl, oz - hh),
				(ox - hw, oy + hl, oz - hh),
			],
			"norms": [(0, 0, -1)] * 4,
		},
		# face 5: +Z (top)
		{
			"verts": [
				(ox - hw, oy - hl, oz + hh),
				(ox - hw, oy + hl, oz + hh),
				(ox + hw, oy + hl, oz + hh),
				(ox + hw, oy - hl, oz + hh),
			],
			"norms": [(0, 0, 1)] * 4,
		},
	]


# Triangle winding is flipped for these faces
_FLIP_FACES = (0, 1, 4, 5)


def make_box_node(width, height, length, color, position=(0, 0, 0), name="box"):
	"""Build a solid-colored box GeomNode centered at position (v3n3c4)."""
	fmt = GeomVertexFormat.get_v3n3c4()
	vdata = GeomVertexData(f"{name}_verts", fmt, Geom.UHStatic)

	vertex = GeomVertexWriter(vdata, "vertex")
	normal = GeomVertexWriter(vdata, "normal")
	color_writer = GeomVertexWriter(vdata, "color")

	tris = GeomTriangles(Geom.UHStatic)
	vertex_index = 0

	hw, hh, hl = width / 2, height / 2, length / 2
	ox, oy, oz = position

	faces = _box_faces(hw, hh, hl, ox, oy, oz)

	for i, face in enumerate(faces):
		verts = face["verts"]
		norms = face["norms"]

		for j, v in enumerate(verts):
			vertex.addData3(*v)
			normal.addData3(*norms[j])
			color_writer.addData4(*color)

		# Flip winding for faces that need it
		if i in _FLIP_FACES:
			tris.addVertices(vertex_index, vertex_index + 2, vertex_index + 1)
			tris.addVertices(vertex_index, vertex_index + 3, vertex_index + 2)
		else:
			tris.addVertices(vertex_index, vertex_index + 1, vertex_index + 2)
			tris.addVertices(vertex_index, vertex_index + 2, vertex_index + 3)
		tris.closePrimitive()
		vertex_index += 4

	vdata.setNumRows(vertex_index)
	geom = Geom(vdata)
	geom.addPrimitive(tris)

	node = GeomNode(name)
	node.addGeom(geom)
	return node


def make_pyramid_node(width, height, length, color, position=(0, 0, 0), name="pyramid"):
	"""Build a solid-colored square pyramid GeomNode centered at position (v3n3c4).

	The base sits at the bottom of the bounding box and the apex at the top, so
	`position` is the box center -- same convention as make_box_node.
	"""
	fmt = GeomVertexFormat.get_v3n3c4()
	vdata = GeomVertexData(f"{name}_verts", fmt, Geom.UHStatic)

	vertex = GeomVertexWriter(vdata, "vertex")
	normal = GeomVertexWriter(vdata, "normal")
	color_writer = GeomVertexWriter(vdata, "color")

	tris = GeomTriangles(Geom.UHStatic)
	vertex_index = 0

	hw, hh, hl = width / 2, height / 2, length / 2
	ox, oy, oz = position
	center = Vec3(ox, oy, oz)

	# Base corners (bottom) + apex (top center)
	v0 = (ox - hw, oy - hl, oz - hh)
	v1 = (ox + hw, oy - hl, oz - hh)
	v2 = (ox + hw, oy + hl, oz - hh)
	v3 = (ox - hw, oy + hl, oz - hh)
	apex = (ox, oy, oz + hh)

	# 4 sides + 2 base triangles
	triangles = [
		(v0, v1, apex),
		(v1, v2, apex),
		(v2, v3, apex),
		(v3, v0, apex),
		(v0, v2, v1),
		(v0, v3, v2),
	]

	for a, b, c in triangles:
		va, vb, vc = Vec3(*a), Vec3(*b), Vec3(*c)
		n = (vb - va).cross(vc - va)
		n.normalize()

		# Ensure the normal points away from the pyramid center; flip winding if not
		centroid = (va + vb + vc) / 3.0
		if n.dot(centroid - center) < 0:
			vb, vc = vc, vb
			n = -n

		for v in (va, vb, vc):
			vertex.addData3(v.x, v.y, v.z)
			normal.addData3(n.x, n.y, n.z)
			color_writer.addData4(*color)

		tris.addVertices(vertex_index, vertex_index + 1, vertex_index + 2)
		tris.closePrimitive()
		vertex_index += 3

	vdata.setNumRows(vertex_index)
	geom = Geom(vdata)
	geom.addPrimitive(tris)

	node = GeomNode(name)
	node.addGeom(geom)
	return node


def make_wire_box_node(width, height, length, color=(0.5, 0.5, 0.5, 1.0),
		position=(0, 0, 0), name="wire", thickness=2.0):
	"""Wireframe outline of a box centered at position."""
	lines = LineSegs(name)
	lines.setThickness(thickness)
	lines.setColor(*color)
	hw, hh, hl = width / 2, height / 2, length / 2
	ox, oy, oz = position
	c = [
		(ox - hw, oy - hl, oz - hh), (ox + hw, oy - hl, oz - hh),
		(ox + hw, oy + hl, oz - hh), (ox - hw, oy + hl, oz - hh),
		(ox - hw, oy - hl, oz + hh), (ox + hw, oy - hl, oz + hh),
		(ox + hw, oy + hl, oz + hh), (ox - hw, oy + hl, oz + hh),
	]
	edges = [
		(0, 1), (1, 2), (2, 3), (3, 0),
		(4, 5), (5, 6), (6, 7), (7, 4),
		(0, 4), (1, 5), (2, 6), (3, 7),
	]
	for a, b in edges:
		lines.moveTo(*c[a])
		lines.drawTo(*c[b])
	return lines.create()


def make_box_node_uv(width, height, length, position=(0, 0, 0), name="box"):
	"""Build a textured box GeomNode centered at position (v3n3t2), UVs 0..1 per face."""
	fmt = GeomVertexFormat.get_v3n3t2()
	vdata = GeomVertexData(f"{name}_verts", fmt, Geom.UHStatic)

	vertex = GeomVertexWriter(vdata, "vertex")
	normal = GeomVertexWriter(vdata, "normal")
	texcoord = GeomVertexWriter(vdata, "texcoord")

	tris = GeomTriangles(Geom.UHStatic)
	vertex_index = 0

	hw, hh, hl = width / 2, height / 2, length / 2
	ox, oy, oz = position
	faces = _box_faces(hw, hh, hl, ox, oy, oz)
	uvs = [(0, 0), (1, 0), (1, 1), (0, 1)]

	for i, face in enumerate(faces):
		verts = face["verts"]
		norms = face["norms"]

		for j, v in enumerate(verts):
			vertex.addData3(*v)
			normal.addData3(*norms[j])
			texcoord.addData2(*uvs[j])

		if i in _FLIP_FACES:
			tris.addVertices(vertex_index, vertex_index + 2, vertex_index + 1)
			tris.addVertices(vertex_index, vertex_index + 3, vertex_index + 2)
		else:
			tris.addVertices(vertex_index, vertex_index + 1, vertex_index + 2)
			tris.addVertices(vertex_index, vertex_index + 2, vertex_index + 3)
		tris.closePrimitive()
		vertex_index += 4

	vdata.setNumRows(vertex_index)
	geom = Geom(vdata)
	geom.addPrimitive(tris)

	node = GeomNode(name)
	node.addGeom(geom)
	return node
