extends SceneTree

const PAYLOAD := "res://generated/utility_panel_uv_density_payload.json"
const RECEIPT := "res://utility-panel-uv-density-runtime-receipt.json"
const VARIANT_PHYSICAL := "physical_density"
const VARIANT_NEGATIVE := "normalized_full_square_negative"

var payload: Dictionary = {}
var atlas_texture: ImageTexture
var receipt := {
    "schema": "axm.building-utility-panel-uv-density-runtime/v0.1",
    "promotion_effect": "NONE",
    "renderer_boundary": "Godot 4.7.2 GL Compatibility diagnostic receiver. Full pavilion proof boxes remain source-bound; only two temporary outer service-surface overlay quads receive the self-generated checker. This does not adopt production UVs, textures, atlas policy, Map integration or runtime representation."
}

func write_receipt() -> void:
    var file := FileAccess.open(RECEIPT, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(receipt, "  ") + "\n")
        file.close()

func fail(message: String) -> void:
    receipt["state"] = "FAIL_INFRASTRUCTURE"
    receipt["failure"] = message
    write_receipt()
    push_error(message)
    quit(1)

func read_json(path: String) -> Dictionary:
    if not FileAccess.file_exists(path):
        return {}
    var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
    return parsed as Dictionary if parsed is Dictionary else {}

func source_vec3(values: Array) -> Vector3:
    return Vector3(float(values[0]), float(values[2]), -float(values[1]))

func source_size(values: Array) -> Vector3:
    return Vector3(float(values[0]), float(values[2]), float(values[1]))

func source_basis_to_godot(source_basis: Array) -> Basis:
    var local_x := source_vec3(source_basis[0] as Array)
    var local_y := source_vec3(source_basis[1] as Array)
    var local_z := source_vec3(source_basis[2] as Array)
    return Basis(local_x, local_z, -local_y)

func make_scalar_material(spec: Dictionary) -> StandardMaterial3D:
    var material := StandardMaterial3D.new()
    var rgba: Array = spec["albedo"]
    material.albedo_color = Color(float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
    material.metallic = float(spec["metallic"])
    material.roughness = float(spec["roughness"])
    return material

func make_component(component: Dictionary) -> MeshInstance3D:
    if String(component.get("kind", "")) != "box":
        return null
    var materials: Dictionary = payload["base_candidate_materials"]
    var material_id := String(component["candidate_material"])
    if not materials.has(material_id):
        return null
    var node := MeshInstance3D.new()
    node.name = String(component["id"])
    var mesh := BoxMesh.new()
    mesh.size = source_size(component["size_local_xyz_m"] as Array)
    node.mesh = mesh
    node.position = source_vec3(component["center_m"] as Array)
    node.basis = source_basis_to_godot(component["source_basis"] as Array)
    node.material_override = make_scalar_material(materials[material_id] as Dictionary)
    return node

func make_floor() -> MeshInstance3D:
    var node := MeshInstance3D.new()
    var mesh := PlaneMesh.new()
    mesh.size = Vector2(18.0, 18.0)
    node.mesh = mesh
    var material := StandardMaterial3D.new()
    material.albedo_color = Color(0.095, 0.10, 0.105, 1.0)
    material.roughness = 0.96
    node.material_override = material
    return node

func color_from_array(values: Array) -> Color:
    return Color(float(values[0]), float(values[1]), float(values[2]), float(values[3]))

func build_atlas_texture() -> ImageTexture:
    var atlas: Dictionary = payload["review_atlas"]
    var size_px: Array = atlas["size_px"]
    var width := int(size_px[0])
    var height := int(size_px[1])
    var period := int(atlas["checker_period_px"])
    var dark := color_from_array(atlas["checker_dark_rgba"] as Array)
    var light := color_from_array(atlas["checker_light_rgba"] as Array)
    var image := Image.create(width, height, false, Image.FORMAT_RGBA8)
    for y in range(height):
        for x in range(width):
            var odd := ((x / period) + (y / period)) % 2
            image.set_pixel(x, y, light if odd == 0 else dark)
    image.generate_mipmaps()
    return ImageTexture.create_from_image(image)

func make_overlay_material() -> StandardMaterial3D:
    var spec: Dictionary = payload["review_atlas"]["base_material"]
    var material := StandardMaterial3D.new()
    material.albedo_color = Color.WHITE
    material.albedo_texture = atlas_texture
    material.metallic = float(spec["metallic"])
    material.roughness = float(spec["roughness"])
    material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
    material.cull_mode = BaseMaterial3D.CULL_DISABLED
    return material

func make_surface_overlay(component: Dictionary, variant: String) -> MeshInstance3D:
    var center: Array = component["center_m"]
    var basis_rows: Array = component["source_basis"]
    var normal_src: Array = basis_rows[0]
    var lateral_src: Array = basis_rows[1]
    var up_src: Array = basis_rows[2]
    var metric: Dictionary = payload["surface_metric"]
    var half_s := float(metric["primary_extent_m"]) * 0.5
    var half_t := float(metric["secondary_extent_m"]) * 0.5
    var face_x := float(metric["outer_face_local_x_m"]) + 0.0008

    var corners_st := [Vector2(-half_s, -half_t), Vector2(half_s, -half_t), Vector2(half_s, half_t), Vector2(-half_s, half_t)]
    var vertices := PackedVector3Array()
    for st in corners_st:
        var source_point := [
            float(center[0]) + float(normal_src[0]) * face_x + float(lateral_src[0]) * st.x + float(up_src[0]) * st.y,
            float(center[1]) + float(normal_src[1]) * face_x + float(lateral_src[1]) * st.x + float(up_src[1]) * st.y,
            float(center[2]) + float(normal_src[2]) * face_x + float(lateral_src[2]) * st.x + float(up_src[2]) * st.y,
        ]
        vertices.append(source_vec3(source_point))

    var normal_godot := source_vec3(normal_src).normalized()
    var normals := PackedVector3Array([normal_godot, normal_godot, normal_godot, normal_godot])
    var uv_bounds: Array
    if variant == VARIANT_PHYSICAL:
        uv_bounds = payload["review_atlas"]["active_uv_bounds"] as Array
    else:
        uv_bounds = payload["negative_control"]["full_square_uv_bounds"] as Array
    var u0 := float(uv_bounds[0])
    var v0 := float(uv_bounds[1])
    var u1 := float(uv_bounds[2])
    var v1 := float(uv_bounds[3])
    var uvs := PackedVector2Array([
        Vector2(u0, v0),
        Vector2(u1, v0),
        Vector2(u1, v1),
        Vector2(u0, v1),
    ])
    var arrays := []
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX] = vertices
    arrays[Mesh.ARRAY_NORMAL] = normals
    arrays[Mesh.ARRAY_TEX_UV] = uvs
    arrays[Mesh.ARRAY_INDEX] = PackedInt32Array([0, 1, 2, 0, 2, 3])
    var mesh := ArrayMesh.new()
    mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
    var node := MeshInstance3D.new()
    node.name = "%s__%s" % [String(component["id"]), variant]
    node.mesh = mesh
    node.material_override = make_overlay_material()
    return node

func configure_camera(camera: Camera3D, context: String) -> void:
    camera.near = 0.05
    camera.far = 40.0
    camera.fov = 42.0
    if context == "front_service":
        camera.look_at_from_position(Vector3(-2.45, 2.15, 5.8), Vector3(-2.45, 1.65, 1.08), Vector3.UP)
    elif context == "east_service":
        camera.look_at_from_position(Vector3(8.6, 2.15, -0.10), Vector3(3.88, 1.65, -0.10), Vector3.UP)
    else:
        camera.look_at_from_position(Vector3(9.0, 5.2, 7.4), Vector3(0.0, 1.60, 0.15), Vector3.UP)

func make_viewport(context: String) -> Dictionary:
    var viewport := SubViewport.new()
    viewport.size = Vector2i(1000, 760)
    viewport.own_world_3d = true
    viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    viewport.render_target_clear_mode = SubViewport.CLEAR_MODE_ALWAYS
    get_root().add_child(viewport)

    var root3d := Node3D.new()
    viewport.add_child(root3d)

    var env := Environment.new()
    env.background_mode = Environment.BG_COLOR
    env.background_color = Color(0.025, 0.030, 0.036, 1.0)
    env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
    env.ambient_light_color = Color(0.47, 0.51, 0.57, 1.0)
    env.ambient_light_energy = 0.55
    var world := WorldEnvironment.new()
    world.environment = env
    root3d.add_child(world)
    root3d.add_child(make_floor())

    var key := DirectionalLight3D.new()
    key.light_energy = 2.1
    key.shadow_enabled = true
    key.rotation_degrees = Vector3(-49.0, -32.0, 0.0)
    root3d.add_child(key)

    var fill := OmniLight3D.new()
    fill.light_energy = 4.1
    fill.omni_range = 16.0
    fill.position = Vector3(-4.8, 5.2, 5.5)
    root3d.add_child(fill)

    var camera := Camera3D.new()
    root3d.add_child(camera)
    camera.make_current()
    configure_camera(camera, context)
    return {"viewport": viewport, "root": root3d}

func capture_variant(context: String, variant: String, capture_path: String) -> Dictionary:
    var setup := make_viewport(context)
    var viewport := setup["viewport"] as SubViewport
    var root3d := setup["root"] as Node3D
    var component_count := 0
    var overlay_count := 0
    var panel_ids: Array = payload["panel_component_ids"]
    for raw_component in payload["base_components"]:
        var component := raw_component as Dictionary
        var node := make_component(component)
        if node == null:
            viewport.queue_free()
            return {"state": "FAIL_COMPONENT"}
        root3d.add_child(node)
        component_count += 1
        if panel_ids.has(String(component["id"])):
            root3d.add_child(make_surface_overlay(component, variant))
            overlay_count += 1
    for _i in range(16):
        await process_frame
    var image := viewport.get_texture().get_image()
    if image == null or image.is_empty():
        viewport.queue_free()
        return {"state": "FAIL_CAPTURE"}
    if image.save_png(capture_path) != OK:
        viewport.queue_free()
        return {"state": "FAIL_CAPTURE"}
    var meta := {
        "state": "PASS",
        "component_count": component_count,
        "overlay_count": overlay_count,
        "width": image.get_width(),
        "height": image.get_height(),
        "bytes": FileAccess.get_file_as_bytes(capture_path).size(),
    }
    viewport.queue_free()
    for _i in range(2):
        await process_frame
    return {"meta": meta, "image": image}

func compare_images(a: Image, b: Image) -> Dictionary:
    if a.get_width() != b.get_width() or a.get_height() != b.get_height():
        return {"state": "FAIL_DIMENSIONS"}
    var changed := 0
    var raw_changed := 0
    var max_delta := 0.0
    var sum_delta := 0.0
    for y in range(a.get_height()):
        for x in range(a.get_width()):
            var ca := a.get_pixel(x, y)
            var cb := b.get_pixel(x, y)
            var dr := absf(ca.r - cb.r)
            var dg := absf(ca.g - cb.g)
            var db := absf(ca.b - cb.b)
            var delta: float = maxf(dr, maxf(dg, db))
            if delta > 0.0:
                raw_changed += 1
            if delta > (1.0 / 255.0):
                changed += 1
            max_delta = maxf(max_delta, delta)
            sum_delta += (dr + dg + db) / 3.0
    var total := a.get_width() * a.get_height()
    return {
        "state": "PASS",
        "raw_changed_pixels": raw_changed,
        "changed_pixels_gt_1lsb": changed,
        "total_pixels": total,
        "changed_fraction_gt_1lsb": float(changed) / float(total),
        "max_rgb_channel_delta": max_delta,
        "mean_rgb_channel_delta": sum_delta / float(total),
    }

func _initialize() -> void:
    payload = read_json(PAYLOAD)
    if payload.get("schema") != "axm.building-utility-panel-uv-density-payload/v0.1":
        fail("missing or invalid utility-panel UV density payload")
        return
    atlas_texture = build_atlas_texture()
    if atlas_texture == null:
        fail("failed to build diagnostic atlas texture")
        return

    var rows := {}
    for raw_context in payload["contexts"]:
        var context := String(raw_context)
        var candidate_path := "res://utility-panel-uv-%s-%s.png" % [context, VARIANT_PHYSICAL]
        var negative_path := "res://utility-panel-uv-%s-%s.png" % [context, VARIANT_NEGATIVE]
        var candidate := await capture_variant(context, VARIANT_PHYSICAL, candidate_path)
        var negative := await capture_variant(context, VARIANT_NEGATIVE, negative_path)
        if not candidate.has("meta") or not negative.has("meta"):
            fail("capture failed for " + context)
            return
        if int(candidate["meta"]["overlay_count"]) != 2 or int(negative["meta"]["overlay_count"]) != 2:
            fail("expected exactly two source-bound service-surface overlays")
            return
        var diff := compare_images(candidate["image"] as Image, negative["image"] as Image)
        if diff.get("state") != "PASS" or int(diff["changed_pixels_gt_1lsb"]) <= 0:
            fail("physical-density candidate is not distinguishable from anisotropic negative in " + context)
            return
        rows[context] = {
            "physical_density": candidate["meta"],
            "normalized_full_square_negative": negative["meta"],
            "pixel_difference": diff,
        }

    receipt["state"] = "PASS_TARGET_HOST_BUILDING_UTILITY_PANEL_PHYSICAL_UV_DENSITY_REVIEW"
    receipt["contexts"] = rows
    receipt["candidate"] = payload["review_atlas"]
    receipt["negative_control"] = payload["negative_control"]
    receipt["owner_evidence"] = payload["owner_evidence"]
    receipt["truth_boundary"] = payload["truth_boundary"]
    receipt["godot_version"] = Engine.get_version_info()
    write_receipt()
    print("AXM BUILDING UTILITY PANEL UV DENSITY ", JSON.stringify(receipt))
    quit(0)
