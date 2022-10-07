
# Basic scene with pipeline

from random import randint
import harfang as hg
from collisions import setup_collisions, display_physics_debug, is_node_name_collision_enabled
from gameplay import test_pos_vs_nodes_table
from levels import *
from utils import clamp, range_adjust
from statistics import mean
from particles import InitParticle, UpdateParticleSystem

level_idx = 0
consumption = 2.5

print(levels)

hg.InputInit()
hg.AudioInit()
hg.WindowSystemInit()

res_x, res_y = 1280, 720

win = hg.RenderInit('AstroLander', res_x, res_y, hg.RF_VSync | hg.RF_MSAA4X)

# hg.SetRenderDebug(hg.RenderDebugProfiler | hg.RenderDebugStats | hg.RenderDebugText)

hg.AddAssetsFolder("../assets/")

# rendering pipeline
pipeline = hg.CreateForwardPipeline(2048, True)
res = hg.PipelineResources()

# AAA pipeline
pipeline_aaa_config = hg.ForwardPipelineAAAConfig()
pipeline_aaa = hg.CreateForwardPipelineAAAFromAssets("core", pipeline_aaa_config, hg.BR_Equal, hg.BR_Equal)
pipeline_aaa_config.sample_count = 1
pipeline_aaa_config.z_thickness = 10

# Vertex model:
vtx_layout = hg.VertexLayoutPosFloatNormUInt8()

# Geometries models:
cube_mdl = hg.CreateCubeModel(vtx_layout, 0.5, 0.5, 0.5)
cube_ref = res.AddModel('cube', cube_mdl)
ground_size = hg.Vec3(50, 0.01, 50)
ground_mdl = hg.CreateCubeModel(vtx_layout, ground_size.x, ground_size.y, ground_size.z)
ground_ref = res.AddModel('ground', ground_mdl)

# Load shader:
prg = hg.LoadPipelineProgramFromAssets('core/shader/default.hps', res, hg.GetForwardPipelineInfo())
prg_ref = res.AddProgram('default shader', prg)

# Create material
mat = hg.Material()
hg.SetMaterialProgram(mat, prg_ref)
hg.SetMaterialValue(mat, "uDiffuseColor", hg.Vec4(0.5, 0.5, 0.5, 1))
hg.SetMaterialValue(mat, "uSpecularColor", hg.Vec4(1, 1, 1, 0.1))

# Physics debug display
vtx_decl_lines = hg.VertexLayout()
vtx_decl_lines.Begin()
vtx_decl_lines.Add(hg.A_Position, 3, hg.AT_Float)
vtx_decl_lines.Add(hg.A_Color0, 3, hg.AT_Float)
vtx_decl_lines.End()
physx_debug_lines_program = hg.LoadProgramFromAssets("shaders/pos_rgb")
shader_texture = hg.LoadProgramFromAssets("shaders/texture")
render_state_quad_occluded = hg.ComputeRenderState(hg.BM_Alpha, False)
vtx_line_layout = hg.VertexLayoutPosFloatColorUInt8()
vtx_layout_particles = hg.VertexLayoutPosFloatTexCoord0UInt8()

# text rendering
font = hg.LoadFontFromAssets('font/default.ttf', 32)
font_program = hg.LoadProgramFromAssets('core/shader/font.vsb', 'core/shader/font.fsb')

text_uniform_values = [hg.MakeUniformSetValue('u_color', hg.Vec4(1, 1, 0.5))]
text_render_state = hg.ComputeRenderState(hg.BM_Alpha, hg.DT_Always, hg.FC_Disabled)
text_uniform_values_white = [hg.MakeUniformSetValue('u_color', hg.Vec4(1, 1, 1))]

# sounds
collect_coin_ref = hg.LoadWAVSoundAsset("audio/sfx/sfx_got_item.wav")
collision_ref = hg.LoadWAVSoundAsset("audio/sfx/sfx_metal_col_0.wav")
thrust_ref = hg.LoadWAVSoundAsset("audio/sfx/sfx_thrust.wav")
dirty_thrust_ref = hg.LoadWAVSoundAsset("audio/sfx/sfx_thrust_dirty.wav")
game_over_ref = hg.LoadWAVSoundAsset("audio/sfx/sfx_game_over.wav")


source_state = hg.StereoSourceState()

thrust_source_state = hg.StereoSourceState(0.05, hg.SR_Loop)
dirty_thrust_source_state = hg.StereoSourceState(0.05, hg.SR_Loop)

thrust_source = hg.PlayStereo(thrust_ref, thrust_source_state)
dirty_thrust_source = hg.PlayStereo(dirty_thrust_ref, dirty_thrust_source_state)

dirty_thrust_ratio = 0.5

# input devices and fps controller states
keyboard = hg.Keyboard()
mouse = hg.Mouse()

# game logic
end_game = False
aaa_rendering = False
levels.append({"level" :"assets/titles/victory.scn", "music": "audio/music/children_of_science.wav", "background": "assets/background_1.scn"})

while not end_game:
	# Setup scene:
	scene = hg.Scene()

	# physics
	physics = hg.SceneBullet3Physics()
	clocks = hg.SceneClocks()
	physic_step = hg.time_from_sec_f(1 / 60)
	hg.SceneUpdateSystems(scene, clocks, hg.time_from_sec_f(1 / 60), physics, physic_step, 10)

	# player
	hg.LoadSceneFromAssets("assets/pod/pod.scn", scene, res, hg.GetForwardPipelineInfo())
	fuel = 100.0
	life = 100.0
	# 1 - normal / 2 - Quick / 0.5 - Slow
	time_factor = 1.0
	collected_all_coins = False
	level_done = False
	level_restart = False
	restart_timer = 5

	# world
	#music
	current_music_ref = hg.LoadWAVSoundAsset(levels[level_idx]['music'])
	music_source_state = hg.StereoSourceState(0.7, hg.SR_Loop)
	current_music_source = hg.PlayStereo(current_music_ref, music_source_state)

	# background
	hg.LoadSceneFromAssets(levels[level_idx]['background'], scene, res, hg.GetForwardPipelineInfo())

	# level
	hg.LoadSceneFromAssets(levels[level_idx]['level'], scene, res, hg.GetForwardPipelineInfo())

	# fog
	scene.environment.fog_color = scene.canvas.color
	scene.environment.fog_near = 100
	scene.environment.fog_far = 200

	# create collision boxes & item list
	scene.ComputeWorldMatrices()
	nodes = scene.GetAllNodes()
	coins = []
	bonus_life = []
	bonus_fuel = []
	bonus_slow_clock = []
	bonus_fast_clock = []
	engine_particles = []
	coll_nodes = []
	target_tex, _ = hg.LoadTextureFromAssets("assets/pod/touch_feedback.png", 0)
	texture_smoke = hg.MakeUniformSetTexture("s_texTexture", target_tex, 0)
	coll_id = 0
	for i in range(nodes.size()):
		nd = nodes.at(i)
		coll_id, coll_node = setup_collisions(scene, physics, res, vtx_layout, coll_id, nd)

		if coll_node:
			coll_nodes.append(coll_node)
			physics.NodeStartTrackingCollisionEvents(coll_node)

		if nd.HasInstance() and nd.GetName().lower() == "coin":
			coins.append({"node": nd, "pos": nd.GetTransform().GetPos()})
		if nd.HasObject() and nd.GetName().lower() == "bonus_fuel":
			bonus_fuel.append({"node": nd, "pos": nd.GetTransform().GetPos()})
		if nd.HasObject() and nd.GetName().lower() == "bonus_heal":
			bonus_life.append({"node": nd, "pos": nd.GetTransform().GetPos()})
		if nd.HasObject() and nd.GetName().lower() == "bonus_slow_clock":
			bonus_slow_clock.append({"node": nd, "pos": nd.GetTransform().GetPos()})
		if nd.HasObject() and nd.GetName().lower() == "bonus_fast_clock":
			bonus_fast_clock.append({"node": nd, "pos": nd.GetTransform().GetPos()})

	pod_bbox = hg.Vec3(3.0, 4.0, 2.0)

	pod_master = scene.GetNode('pod_body')
	start_node = scene.GetNode('start')
	end_node = scene.GetNode('homebase')

	start_pos = start_node.GetTransform().GetPos()
	end_pos = end_node.GetTransform().GetPos()

	# Place the player above the 'start' area

	pod_master.GetTransform().SetPos(hg.Vec3(start_pos.x, start_pos.y + 2, start_pos.z))

	thrust_item_l = scene.GetNode("thrust_item_l")
	thrust_item_r = scene.GetNode("thrust_item_r")
	flame_item_l = scene.GetNode("flame_l")
	flame_item_r = scene.GetNode("flame_r")
	flame_item_m = scene.GetNode("flame_m")

	# pod_master.RemoveObject()

	physics.NodeCreatePhysicsFromAssets(pod_master)

	physics.NodeSetLinearFactor(pod_master, hg.Vec3(1.0, 1.0, 0.0))
	physics.NodeSetAngularFactor(pod_master, hg.Vec3(0.0, 0.0, 1.0))

	# Camera
	cam_pos = hg.Vec3(0, 1, -50)
	cam_rot = hg.Vec3(0, 0, 0)

	# between end and start pos...
	temp_pos = (start_pos + end_pos) / 2.0

	cam_pos = hg.Vec3(temp_pos.x, temp_pos.y, cam_pos.z)
	cam_target = cam_pos

	cam = hg.CreateCamera(scene, hg.TransformationMat4(cam_pos, cam_rot), 10.0, 1000.0)
	scene.SetCurrentCamera(cam)

	# main loop
	hg.ResetClock()

	pod_thrust = 50.0
	dt_history = [1.0 / 60.0]
	velocity = 0.0
	prev_velocity = 0.0
	prev_pod_acceleration = 0.0
	pod_acceleration = 0.0
	last_collision = 0


	vtx = hg.Vertices(vtx_line_layout, 2)
	vid_scene_opaque = 0

	# important physics stuff before the first frame
	physics.NodeStartTrackingCollisionEvents(pod_master)
	physics.SceneCreatePhysicsFromAssets(scene)

	frame = 0

	while not end_game and not level_done:
		view_id = 0
		pass_id = 0
		keyboard.Update()
		mouse.Update()

		if keyboard.Down(hg.K_Escape):
			end_game = True

		if keyboard.Pressed(hg.K_K):
			aaa_rendering = not aaa_rendering

		dt = hg.TickClock()
		dt_history.append(hg.time_to_sec_f(dt))
		if len(dt_history) > 120:
			del dt_history[0]
		dtsmooth = mean(dt_history)

		# cam.GetTransform().SetPos(cam_pos)
		# cam.GetTransform().SetRot(cam_rot)

		# Player ship control
		thrust_left = False
		thrust_right = False
		if keyboard.Down(hg.K_Left):
			thrust_left = True
		if keyboard.Down(hg.K_Right):
			thrust_right = True

		_pod_world = pod_master.GetTransform().GetWorld()
		

		cam_target = hg.GetT(_pod_world) * hg.Vec3(1.0, 1.0, 0.0) + cam_pos * hg.Vec3(0.0, 0.0, 1.0)
		cam_target += physics.NodeGetLinearVelocity(pod_master) * hg.Vec3(1.0, 1.0, 0.0)
		cam_pos = hg.Lerp(cam_pos, cam_target, dtsmooth * 0.5)
		cam.GetTransform().SetPos(cam_pos)

		dirty_left = 0.5
		dirty_right = 0.5

		# left engine
		ray_start_pos = hg.GetTranslation(flame_item_l.GetTransform().GetWorld())
		ray_dir = hg.GetY(flame_item_l.GetTransform().GetWorld())
		ray_end_pos = ray_start_pos + ray_dir * 10
		raycast_out = physics.RaycastFirstHit(scene, ray_start_pos, ray_end_pos)
		if raycast_out.node.IsValid() and fuel > 0 and life > 0:
			random_scale = randint(2, 6)
			dirty_left = (hg.Dist(ray_start_pos, raycast_out.P) / 3.5) / 2
			if thrust_left:
				InitParticle(engine_particles, raycast_out.P + hg.RandomVec3(-0.3, 0.3), 0.75, shader_texture, hg.Vec3(random_scale, random_scale, random_scale))


		# right engine
		ray_start_pos = hg.GetTranslation(flame_item_r.GetTransform().GetWorld())
		ray_dir = hg.GetY(flame_item_r.GetTransform().GetWorld())
		ray_end_pos = ray_start_pos + ray_dir * 10
		raycast_out = physics.RaycastFirstHit(scene, ray_start_pos, ray_end_pos)
		if raycast_out.node.IsValid() and fuel > 0 and life > 0:
			random_scale = randint(2, 6)
			dirty_right = (hg.Dist(ray_start_pos, raycast_out.P) / 3.5) / 2 #3.5 is the furthest distance i could get with this raycast hitting a valid node
			if thrust_right:
				InitParticle(engine_particles, raycast_out.P + hg.RandomVec3(-0.3, 0.3), 0.75, shader_texture, hg.Vec3(random_scale, random_scale, random_scale))


		dirty_thrust_ratio = dirty_left + dirty_right

		# left
		if life > 0 and fuel > 0:
			if thrust_left and not thrust_right:
				physics.NodeAddForce(pod_master, hg.MakeVec3(hg.GetRow(_pod_world, 0) * pod_thrust * 0.9))
				physics.NodeAddForce(pod_master, hg.MakeVec3(hg.GetRow(_pod_world, 0) * pod_thrust * 0.1), hg.GetTranslation(thrust_item_l.GetTransform().GetWorld()))
				flame_item_l.Enable()
				flame_item_r.Disable()
				flame_item_m.Disable()
				hg.SetSourceVolume(thrust_source, 0 + dirty_thrust_ratio)
				hg.SetSourceVolume(dirty_thrust_source, 1 - dirty_thrust_ratio)

			# right
			if not thrust_left and thrust_right:		
				physics.NodeAddForce(pod_master, hg.MakeVec3(hg.GetRow(_pod_world, 0) * pod_thrust * -0.9))
				physics.NodeAddForce(pod_master, hg.MakeVec3(hg.GetRow(_pod_world, 0) * pod_thrust * -0.1), hg.GetTranslation(thrust_item_r.GetTransform().GetWorld()))
				flame_item_l.Disable()
				flame_item_m.Disable()
				flame_item_r.Enable()
				hg.SetSourceVolume(thrust_source, 0 + dirty_thrust_ratio)
				hg.SetSourceVolume(dirty_thrust_source, 1 - dirty_thrust_ratio)

			# up
			if thrust_left and thrust_right:
				physics.NodeAddForce(pod_master, hg.MakeVec3(hg.GetRow(_pod_world, 1) * pod_thrust), hg.GetTranslation(_pod_world))
				flame_item_l.Enable()
				flame_item_r.Enable()
				flame_item_m.Enable()
				hg.SetSourceVolume(thrust_source, 0 + dirty_thrust_ratio)
				hg.SetSourceVolume(dirty_thrust_source, 1 - dirty_thrust_ratio)


			if not thrust_left and not thrust_right:
				flame_item_l.Disable()
				flame_item_m.Disable()
				flame_item_r.Disable()
				hg.SetSourceVolume(thrust_source, 0.1)
				hg.SetSourceVolume(dirty_thrust_source, 0)

		# Auto align
		rot_z = hg.GetR(pod_master.GetTransform().GetWorld()).z
		ang_v_z = physics.NodeGetAngularVelocity(pod_master).z

		align = clamp(abs(hg.RadianToDegree(rot_z)) / 180.0, 0.0, 1.0)
		align *= 250.0
		prev_velocity = velocity
		prev_pod_acceleration = pod_acceleration
		velocity = hg.Len(physics.NodeGetLinearVelocity(pod_master))
		pod_acceleration = abs(prev_velocity - velocity)
		align *= clamp(range_adjust(velocity, 0.25, 0.5, 0.0, 1.0), 0.0, 1.0)

		physics.NodeAddTorque(pod_master, hg.Vec3(0.0, 0.0, -rot_z - ang_v_z) * align)
		# physics.NodeAddForce(pod_master, hg.GetRow(_pod_world, 0) * (-rot_z - ang_v_z) * align * -1.0, hg.GetTranslation(_pod_world) + hg.GetRow(_pod_world, 1) * 1.0)

		physics.NodeWake(pod_master)

		# Gameplay logic
		# Life / damage
		should_play_sound = False
		if velocity > 2.5 and abs(prev_pod_acceleration - pod_acceleration) > 1.0:
			paircontacts = physics.CollectCollisionEvents(scene)
			for nd in coll_nodes:
				nodes_in_contact = hg.GetNodePairContacts(nd, pod_master, paircontacts)
				if nodes_in_contact.size() > 0:
					# check if pod is in collision with something
					damage = abs(prev_pod_acceleration - pod_acceleration) * clamp(range_adjust(velocity, 2.5, 50.0, 0.0, 1.0), 0.0, 1.0)
					life = max(life - damage, 0.0)
					should_play_sound = True

		if should_play_sound and last_collision + hg.time_from_sec_f(0.2) < hg.GetClock():
			last_collision = hg.GetClock()
			hg.PlayStereo(collision_ref, source_state)


		# Fuel
		if thrust_left or thrust_right:
			fuel = max(0.0, fuel - consumption * hg.time_to_sec_f(dt))

		# Get a coin
		coin_hit = test_pos_vs_nodes_table(hg.GetTranslation(_pod_world), coins, 2.5)
		if coin_hit > -1:
			# print(coin_hit)
			hg.PlayStereo(collect_coin_ref, source_state)
			coins[coin_hit]["node"].Disable()
			del coins[coin_hit]

			if len(coins) <= 0:
				collected_all_coins = True
		# get a heal bonus
		heal_hit = test_pos_vs_nodes_table(hg.GetTranslation(_pod_world), bonus_life, 2.5)
		if heal_hit > -1:
			# print(heal_hit)
			bonus_life[heal_hit]["node"].Disable()
			life = 100
		# get a fuel bonus
		fuel_hit = test_pos_vs_nodes_table(hg.GetTranslation(_pod_world), bonus_fuel, 2.5)
		if fuel_hit > -1:
			# print(fuel_hit)
			bonus_fuel[fuel_hit]["node"].Disable()
			fuel = 100
		# get a slow clock bonus
		slow_clock_hit = test_pos_vs_nodes_table(hg.GetTranslation(_pod_world), bonus_slow_clock, 2.5)
		if slow_clock_hit > -1:
			# print(slow_clock_hit)
			bonus_slow_clock[slow_clock_hit]["node"].Disable()
			time_factor /= 2
		# get a fast clock bonus
		fast_clock_hit = test_pos_vs_nodes_table(hg.GetTranslation(_pod_world), bonus_fast_clock, 2.5)
		if fast_clock_hit > -1:
			# print(fast_clock_hit)
			bonus_fast_clock[fast_clock_hit]["node"].Disable()
			time_factor *= 2


		if collected_all_coins and life > 0:
			if velocity < 0.1:
				if hg.Dist(hg.GetTranslation(_pod_world), end_pos) < 5.0:
					hg.StopSource(current_music_source)
					level_done = True
					level_idx += 1

		# scene.Update(dt)
		hg.SceneUpdateSystems(scene, clocks, hg.time_from_sec_f(hg.time_to_sec_f(dt) * time_factor), physics, physic_step, 10)
		if aaa_rendering:
			view_id, pass_id = hg.SubmitSceneToPipeline(0, scene, hg.IntRect(0, 0, res_x, res_y), True, pipeline, res, pipeline_aaa, pipeline_aaa_config, frame)

		else:
			view_id, pass_id = hg.SubmitSceneToPipeline(view_id, scene, hg.IntRect(0, 0, res_x, res_y), True, pipeline, res)
		vid_scene_opaque = hg.GetSceneForwardPipelinePassViewId(pass_id, hg.SFPP_Opaque)

		view_id_scene_alpha = hg.GetSceneForwardPipelinePassViewId(pass_id, hg.SFPP_Transparent)
		engine_particles = UpdateParticleSystem(engine_particles, render_state_quad_occluded, dtsmooth, cam_rot, view_id_scene_alpha, vtx_layout_particles, texture_smoke)

		# on-screen usage text
		hg.SetView2D(view_id, 0, 0, res_x, res_y, -1, 1, hg.CF_Depth, hg.Color.Black, 1, 0)
		if aaa_rendering:
			hg.DrawText(view_id, font, 'Render : AAA (K to Switch)', font_program, 'u_tex', 0, hg.Mat4.Identity, hg.Vec3(200, res_y - 120, 0), hg.DTHA_Left, hg.DTVA_Bottom, text_uniform_values, [], text_render_state)
		else: 
			hg.DrawText(view_id, font, 'Render : Basic (K to Switch)', font_program, 'u_tex', 0, hg.Mat4.Identity, hg.Vec3(200, res_y - 120, 0), hg.DTHA_Left, hg.DTVA_Bottom, text_uniform_values, [], text_render_state)

		hg.DrawText(view_id, font, 'Time factor: %f' % time_factor, font_program, 'u_tex', 0, hg.Mat4.Identity, hg.Vec3(200, res_y - 80, 0), hg.DTHA_Left, hg.DTVA_Bottom, text_uniform_values, [], text_render_state)
		hg.DrawText(view_id, font, 'Level %d' % (level_idx + 1), font_program, 'u_tex', 0, hg.Mat4.Identity, hg.Vec3(200, res_y - 40, 0), hg.DTHA_Left, hg.DTVA_Bottom, text_uniform_values, [], text_render_state)
		if life < 1 or fuel < 1:
			if velocity < 0.03:
				level_restart = True
				hg.PlayStereo(game_over_ref, source_state)
		
		if level_restart == True and restart_timer > 0:
			hg.DrawText(view_id, font, 'GAME OVER', font_program, 'u_tex', 0, hg.Mat4.Identity, hg.Vec3(res_x / 2, res_y / 2, 0), hg.DTHA_Left, hg.DTVA_Bottom, text_uniform_values, [], text_render_state)
			hg.DrawText(view_id, font, 'RESTARTING LEVEL IN ' + str(restart_timer)[:3] + ' SECONDS', font_program, 'u_tex', 0, hg.Mat4.Identity, hg.Vec3(res_x / 2, res_y / 2 + 100, 0), hg.DTHA_Left, hg.DTVA_Bottom, text_uniform_values, [], text_render_state)
			restart_timer -= dtsmooth

		elif restart_timer < 0:
			level_done = True

		if len(coins) > 0:
			txt_col = text_uniform_values
		else:
			txt_col = text_uniform_values_white
		hg.DrawText(view_id, font, '%d Coins' % len(coins), font_program, 'u_tex', 0, hg.Mat4.Identity, hg.Vec3(res_x - 200, res_y - 120, 0), hg.DTHA_Left, hg.DTVA_Bottom, txt_col, [], text_render_state)
		hg.DrawText(view_id, font, 'Life: %d' % life, font_program, 'u_tex', 0, hg.Mat4.Identity, hg.Vec3(res_x - 200, res_y - 80, 0), hg.DTHA_Left, hg.DTVA_Bottom, text_uniform_values, [], text_render_state)
		hg.DrawText(view_id, font, 'Fuel: %d' % fuel, font_program, 'u_tex', 0, hg.Mat4.Identity, hg.Vec3(res_x - 200, res_y - 40, 0), hg.DTHA_Left, hg.DTVA_Bottom, text_uniform_values, [], text_render_state)

		# debug physics
		view_id += 1
		# display_physics_debug(scene, physics, view_id, res_x, res_y, vtx_decl_lines, physx_debug_lines_program)

		frame = hg.Frame()
		hg.UpdateWindow(win)

	scene.Clear()
	scene.GarbageCollect()

hg.RenderShutdown()
hg.DestroyWindow(win)