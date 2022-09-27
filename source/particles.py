import harfang as hg
from random import uniform

def InitParticle(particlestable, particle_pos, duration, shader, scale):
	particlestable.append([particle_pos, duration, shader, scale])

def UpdateParticleSystem(particlestable, render_state, dts, cam_rotation, view_id_scene, vertex_layout, texture):
	new_particles = []

	for n in particlestable:
		if n[1] - dts > 0:
			scale = n[3]
			if n[1] < 0.25:
				scale.x -= 0.1
				scale.y -= 0.1
				scale.z -= 0.1
				n[3] = scale

			mat = hg.TransformationMat4(n[0], cam_rotation, scale)
			n[0].y += uniform(0.01, 0.05)

			pos = hg.GetT(mat)
			axis_x = hg.GetX(mat) / 4
			axis_y = hg.GetY(mat) / 4
			# print(axis_x.x, axis_x.y, axis_x.z)
			# print(axis_y.x, axis_y.y, axis_y.z)

			quad_vtx = hg.Vertices(vertex_layout, 4)
			quad_vtx.Begin(0).SetPos(pos - axis_x - axis_y).SetTexCoord0(hg.Vec2(0, 1)).End()
			quad_vtx.Begin(1).SetPos(pos - axis_x + axis_y).SetTexCoord0(hg.Vec2(0, 0)).End()
			quad_vtx.Begin(2).SetPos(pos + axis_x + axis_y).SetTexCoord0(hg.Vec2(1, 0)).End()
			quad_vtx.Begin(3).SetPos(pos + axis_x - axis_y).SetTexCoord0(hg.Vec2(1, 1)).End()
			quad_idx = [0, 3, 2, 0, 2, 1]

			hg.DrawTriangles(view_id_scene, quad_idx, quad_vtx, n[2], [], [texture], render_state, 1)
			
			n[1] = n[1] - dts
			new_particles.append(n)

	return new_particles
