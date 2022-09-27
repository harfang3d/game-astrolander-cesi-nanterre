import harfang as hg

def is_node_name_collision_enabled(node_name):
	for name in ["g_block_", "start", "homebase", "colshape"]:
		if node_name.lower().startswith(name):
			return True
	return False

def setup_collisions(scn, scene_physics, res, vtx_layout, coll_id, _node):
	if _node.HasObject() and is_node_name_collision_enabled(_node.GetName()):
		node = _node
		_, min_max = node.GetObject().GetMinMax(res)
		size = min_max.mx - min_max.mn

		instance_size = hg.GetS(node.GetTransform().GetWorld()) * size
		mat_collision_box = hg.TransformationMat4(hg.GetT(_node.GetTransform().GetWorld()), hg.GetR(_node.GetTransform().GetWorld()))

		# print(node.GetName() + ": " + str(size.x) + ", " + str(size.y) + ", " + str(size.z) + "  - Instance size : " + str(instance_size.x) + ", " + str(instance_size.y) + ", " + str(instance_size.z))
		box_collision_ref = res.AddModel('col_shape_' + str(coll_id), hg.CreateCubeModel(vtx_layout, instance_size.x, instance_size.y, instance_size.z))
		collision_node = hg.CreatePhysicCube(scn, instance_size, mat_collision_box, box_collision_ref, [], 0)
		collision_node.GetRigidBody().SetType(hg.RBT_Static)
		collision = collision_node.GetCollision(1)
		collision_node.RemoveObject()
		scene_physics.NodeCreatePhysicsFromAssets(collision_node)

		coll_id +=1
		return coll_id, collision_node
	return coll_id, None


def display_physics_debug(scn, physics, vid, res_x, res_y, vtx_decl_lines, physx_debug_lines_program):
	hg.SetViewRect(vid, 0, 0, res_x, res_y)
	cam = scn.GetCurrentCamera()
	hg.SetViewClear(vid, hg.CF_Depth, 0, 1.0, 0)
	cam_mat = cam.GetTransform().GetWorld()
	view_matrix = hg.InverseFast(cam_mat)
	c = cam.GetCamera()
	projection_matrix = hg.ComputePerspectiveProjectionMatrix(c.GetZNear(), c.GetZFar(), hg.FovToZoomFactor(c.GetFov()), hg.Vec2(res_x / res_y, 1))
	hg.SetViewTransform(vid, view_matrix, projection_matrix)
	physics.RenderCollision(vid, vtx_decl_lines, physx_debug_lines_program, hg.ComputeRenderState(hg.BM_Opaque, hg.DT_Disabled, hg.FC_Disabled), 1)