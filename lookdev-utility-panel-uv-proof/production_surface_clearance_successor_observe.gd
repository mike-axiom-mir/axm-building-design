extends SceneTree

const CONTRACT := "res://generated/runtime_contract.json"
const TEXTURE := "res://utility-panel-production-surface-001.png"
const RECEIPT := "res://utility-panel-production-surface-clearance-successor-runtime-receipt.json"

var contract: Dictionary = {}
var texture_image: Image
var texture_resource: ImageTexture

func read_json(path: String) -> Dictionary:
    if not FileAccess.file_exists(path):
        return {}
    var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
    return parsed as Dictionary if parsed is Dictionary else {}

func write_receipt(data: Dictionary) -> void:
    var file := FileAccess.open(RECEIPT, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(data, "  ") + "\n")
        file.close()

func fail(message: String, extra := {}) -> void:
    var data := {
        "schema": "axm.building-utility-panel-production-surface-clearance-successor-runtime/v0.1",
        "state": "FAIL_TARGET_HOST_BUILDING_UTILITY_PANEL_PRODUCTION_SURFACE_CLEARANCE_SUCCESSOR_REVIEW",
        "failure": message,
        "promotion_effect": "NONE"
    }
    for key in extra:
        data[key] = extra[key]
    write_receipt(data)
    push_error(message)
    quit(1)

func sha256_bytes(data: PackedByteArray) -> String:
    var context := HashingContext.new()
    if context.start(HashingContext.HASH_SHA256) != OK:
        return ""
    if context.update(data) != OK:
        return ""
    return context.finish().hex_encode()

func vec3(row: Array) -> Vector3:
    return Vector3(float(row[0]), float(row[1]), float(row[2]))

func make_plate_material() -> StandardMaterial3D:
    var material := StandardMaterial3D.new()
    material.albedo_color = Color(0.26, 0.29, 0.32, 1.0)
    material.metallic = 0.62
    material.roughness = 0.56
    return material

func make_panel_body_material(unshaded: bool) -> StandardMaterial3D:
    var base: Array = contract["material"]["base_srgb8"]
    var material := StandardMaterial3D.new()
    material.albedo_color = Color(float(base[0]) / 255.0, float(base[1]) / 255.0, float(base[2]) / 255.0, 1.0)
    material.metallic = float(contract["material"]["metallic"])
    material.roughness = float(contract["material"]["roughness"])
    if unshaded:
        material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    return material

func make_surface_material(unshaded: bool) -> StandardMaterial3D:
    var material := StandardMaterial3D.new()
    material.albedo_color = Color.WHITE
    material.albedo_texture = texture_resource
    material.metallic = float(contract["material"]["metallic"])
    material.roughness = float(contract["material"]["roughness"])
    material.cull_mode = BaseMaterial3D.CULL_DISABLED
    material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
    material.texture_repeat = true
    if unshaded:
        material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    return material

func make_box(center: Vector3, normal: Vector3, lateral: Vector3, up: Vector3, size_local: Vector3, material: Material, name_value: String) -> MeshInstance3D:
    var box := BoxMesh.new()
    box.size = size_local
    var node := MeshInstance3D.new()
    node.name = name_value
    node.mesh = box
    node.material_override = material
    node.transform = Transform3D(Basis(normal, lateral, up), center)
    return node

func make_service_surface(receiver: Dictionary, panel_center: Vector3, unshaded: bool) -> MeshInstance3D:
    var normal := vec3(receiver["normal"])
    var lateral := vec3(receiver["lateral"])
    var up := vec3(receiver["up"])
    var footprint: Array = contract["panel"]["footprint_m"]
    var half_lateral := float(footprint[0]) * 0.5
    var half_up := float(footprint[1]) * 0.5
    var depth := float(contract["panel"]["body_depth_m"])
    var center := panel_center + normal * (depth * 0.5 + 0.0002)

    var vertices := PackedVector3Array([
        center - lateral * half_lateral - up * half_up,
        center + lateral * half_lateral - up * half_up,
        center + lateral * half_lateral + up * half_up,
        center - lateral * half_lateral + up * half_up
    ])
    var normals := PackedVector3Array([normal, normal, normal, normal])
    var uv_extent: Array = contract["review_uv_extent"]
    var u := float(uv_extent[0])
    var v := float(uv_extent[1])
    var uvs := PackedVector2Array([
        Vector2(0.0, 0.0), Vector2(u, 0.0), Vector2(u, v), Vector2(0.0, v)
    ])
    var indices := PackedInt32Array([0, 1, 2, 0, 2, 3])
    var arrays := []
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX] = vertices
    arrays[Mesh.ARRAY_NORMAL] = normals
    arrays[Mesh.ARRAY_TEX_UV] = uvs
    arrays[Mesh.ARRAY_INDEX] = indices
    var mesh := ArrayMesh.new()
    mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
    var node := MeshInstance3D.new()
    node.name = String(receiver["id"]) + "_production_surface"
    node.mesh = mesh
    node.material_override = make_surface_material(unshaded)
    return node

func add_receiver(root3d: Node3D, receiver: Dictionary, successor: bool, unshaded: bool) -> void:
    var origin := vec3(receiver["origin"])
    var normal := vec3(receiver["normal"])
    var lateral := vec3(receiver["lateral"])
    var up := vec3(receiver["up"])
    var plate_footprint: Array = receiver["plate_footprint_m"]
    var plate_thickness := float(receiver["plate_thickness_m"])
    var plate_center := origin + normal * (plate_thickness * 0.5)
    var plate_size := Vector3(plate_thickness, float(plate_footprint[0]), float(plate_footprint[1]))
    root3d.add_child(make_box(plate_center, normal, lateral, up, plate_size, make_plate_material(), String(receiver["id"]) + "_receiver_plate"))

    var center_key := "successor_panel_center_m" if successor else "historical_panel_center_m"
    var panel_center := vec3(receiver[center_key])
    var footprint: Array = contract["panel"]["footprint_m"]
    var panel_size := Vector3(float(contract["panel"]["body_depth_m"]), float(footprint[0]), float(footprint[1]))
    root3d.add_child(make_box(panel_center, normal, lateral, up, panel_size, make_panel_body_material(unshaded), String(receiver["id"]) + "_panel_body"))
    root3d.add_child(make_service_surface(receiver, panel_center, unshaded))

func configure_camera(camera: Camera3D, context: String) -> void:
    camera.near = 0.05
    camera.far = 40.0
    var up := Vector3(0.0, 0.0, 1.0)
    if context == "front_service":
        camera.fov = 32.0
        camera.look_at_from_position(Vector3(-2.45, -4.00, 2.00), Vector3(-2.45, -1.08, 1.65), up)
    elif context == "east_service":
        camera.fov = 32.0
        camera.look_at_from_position(Vector3(7.10, 0.10, 2.00), Vector3(3.90, 0.10, 1.65), up)
    else:
        camera.fov = 48.0
        camera.look_at_from_position(Vector3(7.50, -4.80, 4.80), Vector3(0.60, -0.15, 1.65), up)

func make_viewport(context: String) -> Dictionary:
    var viewport := SubViewport.new()
    viewport.size = Vector2i(1000, 700)
    viewport.own_world_3d = true
    viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    viewport.render_target_clear_mode = SubViewport.CLEAR_MODE_ALWAYS
    get_root().add_child(viewport)
    var root3d := Node3D.new()
    viewport.add_child(root3d)

    var env := Environment.new()
    env.background_mode = Environment.BG_COLOR
    env.background_color = Color(0.022, 0.027, 0.033, 1.0)
    env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
    env.ambient_light_color = Color(0.42, 0.46, 0.52, 1.0)
    env.ambient_light_energy = 0.52
    var world := WorldEnvironment.new()
    world.environment = env
    root3d.add_child(world)

    var key := DirectionalLight3D.new()
    key.light_energy = 2.1
    key.shadow_enabled = false
    key.rotation_degrees = Vector3(-47.0, -34.0, 17.0)
    root3d.add_child(key)

    var fill_front := OmniLight3D.new()
    fill_front.light_energy = 3.0
    fill_front.omni_range = 12.0
    fill_front.position = Vector3(-2.5, -3.0, 3.4)
    root3d.add_child(fill_front)

    var fill_east := OmniLight3D.new()
    fill_east.light_energy = 2.7
    fill_east.omni_range = 12.0
    fill_east.position = Vector3(6.6, 0.1, 3.2)
    root3d.add_child(fill_east)

    var camera := Camera3D.new()
    root3d.add_child(camera)
    camera.make_current()
    configure_camera(camera, context)
    return {"viewport": viewport, "root": root3d}

func capture(context: String, successor: bool, unshaded: bool, suffix: String) -> Dictionary:
    var setup := make_viewport(context)
    var viewport := setup["viewport"] as SubViewport
    var root3d := setup["root"] as Node3D
    for receiver_value in contract["receivers"]:
        add_receiver(root3d, receiver_value as Dictionary, successor, unshaded)
    for _i in range(14):
        await process_frame
    var image := viewport.get_texture().get_image()
    if image == null or image.is_empty():
        viewport.queue_free()
        return {"state": "FAIL_CAPTURE"}
    var path := "res://utility-panel-clearance-%s-%s.png" % [context, suffix]
    if image.save_png(path) != OK:
        viewport.queue_free()
        return {"state": "FAIL_SAVE"}
    var result := {"state": "PASS", "path": path, "width": image.get_width(), "height": image.get_height(), "bytes": FileAccess.get_file_as_bytes(path).size()}
    viewport.queue_free()
    for _i in range(2):
        await process_frame
    return result

func _initialize() -> void:
    contract = read_json(CONTRACT)
    if String(contract.get("schema", "")) != "axm.building-utility-panel-production-surface-clearance-successor-runtime-contract/v0.1":
        fail("missing or invalid runtime contract")
        return
    if not FileAccess.file_exists(TEXTURE):
        fail("missing production surface texture")
        return
    var png_sha := sha256_bytes(FileAccess.get_file_as_bytes(TEXTURE))
    if png_sha != String(contract["texture_png_sha256"]):
        fail("production surface PNG identity drift", {"actual": png_sha, "expected": contract["texture_png_sha256"]})
        return
    texture_image = Image.new()
    if texture_image.load(TEXTURE) != OK or texture_image.is_empty():
        fail("unable to load production surface texture")
        return
    texture_image.convert(Image.FORMAT_RGBA8)
    var rgba_sha := sha256_bytes(texture_image.get_data())
    if rgba_sha != String(contract["texture_rgba8_sha256"]):
        fail("production surface RGBA identity drift", {"actual": rgba_sha, "expected": contract["texture_rgba8_sha256"]})
        return
    texture_image.generate_mipmaps()
    texture_resource = ImageTexture.create_from_image(texture_image)

    var captures := {}
    for context_value in contract["contexts"]:
        var context := String(context_value)
        var historical := await capture(context, false, false, "historical-lit")
        if historical["state"] != "PASS":
            fail("historical capture failed", {"context": context, "capture": historical})
            return
        var successor := await capture(context, true, false, "successor-lit")
        if successor["state"] != "PASS":
            fail("successor capture failed", {"context": context, "capture": successor})
            return
        var unshaded := await capture(context, true, true, "successor-unshaded")
        if unshaded["state"] != "PASS":
            fail("successor unshaded capture failed", {"context": context, "capture": unshaded})
            return
        captures[context] = {"historical_lit": historical, "successor_lit": successor, "successor_unshaded": unshaded}

    write_receipt({
        "schema": "axm.building-utility-panel-production-surface-clearance-successor-runtime/v0.1",
        "state": "PASS_TARGET_HOST_BUILDING_UTILITY_PANEL_PRODUCTION_SURFACE_CLEARANCE_SUCCESSOR_REVIEW",
        "surface_id": contract["surface_id"],
        "texture_png_sha256": png_sha,
        "texture_rgba8_sha256": rgba_sha,
        "receiver_count": (contract["receivers"] as Array).size(),
        "contexts": captures,
        "review_uv_extent": contract["review_uv_extent"],
        "review_texel_density_px_per_m": contract["review_texel_density_px_per_m"],
        "renderer": "Godot 4.7.2 GL Compatibility / X11 proof host",
        "renderer_boundary": contract["renderer_boundary"],
        "truth_boundary": contract["truth_boundary"],
        "promotion_effect": "NONE"
    })
    quit(0)
