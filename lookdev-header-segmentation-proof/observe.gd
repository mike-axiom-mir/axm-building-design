extends SceneTree

const PAYLOAD := "res://generated/payload.json"
const RECEIPT := "res://runtime_receipt.json"
const EXPECTED_HARD_SURFACE_HEAD := "34124101e616c423c5a3ed5e122ddf09b98a1650"
const MAX_CONTINUITY_CHANGED_FRACTION := 0.01

var payload: Dictionary = {}
var receipt := {
    "schema": "axm.building-material-header-segmentation-runtime/v0.1",
    "promotion_effect": "NONE",
    "renderer_boundary": "Godot 4.7.2 GL Compatibility. This compares the exact source-owned closed/outward logical pre-segmentation representation with the exact source-owned six-segment header representation under one unchanged five-surface Materials profile. It is a bounded material-binding continuity check, not Map equivalence or final aesthetic approval."
}

func write_receipt() -> void:
    var file := FileAccess.open(RECEIPT, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(receipt, "  ") + "\n")
        file.close()

func fail(message: String) -> void:
    receipt["state"] = "FAIL_TARGET_HOST"
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

func make_material(material_id: String) -> StandardMaterial3D:
    var spec := payload["materials"][material_id] as Dictionary
    var rgba := spec["albedo"] as Array
    var material := StandardMaterial3D.new()
    material.albedo_color = Color(float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
    material.metallic = float(spec["metallic"])
    material.roughness = float(spec["roughness"])
    material.cull_mode = BaseMaterial3D.CULL_BACK
    return material

func make_component(component: Dictionary) -> MeshInstance3D:
    var node := MeshInstance3D.new()
    node.name = String(component["id"])
    var vertices := component["vertices_m"] as Array
    var faces := payload["faces"] as Array
    var surface := SurfaceTool.new()
    surface.begin(Mesh.PRIMITIVE_TRIANGLES)
    surface.set_material(make_material(String(component["material_id"])))
    for raw_face in faces:
        var face := raw_face as Array
        var a := source_vec3(vertices[int(face[0])] as Array)
        var source_b := source_vec3(vertices[int(face[1])] as Array)
        var source_c := source_vec3(vertices[int(face[2])] as Array)
        var normal := (source_b - a).cross(source_c - a).normalized()
        surface.set_normal(normal)
        surface.add_vertex(a)
        surface.set_normal(normal)
        surface.add_vertex(source_c)
        surface.set_normal(normal)
        surface.add_vertex(source_b)
    node.mesh = surface.commit()
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

func configure_camera(camera: Camera3D, context: String) -> void:
    camera.near = 0.05
    camera.far = 40.0
    camera.fov = 45.0
    if context == "front_service":
        camera.look_at_from_position(Vector3(0.0, 2.65, 9.5), Vector3(0.0, 1.65, 0.0), Vector3.UP)
    elif context == "east_service":
        camera.look_at_from_position(Vector3(10.8, 2.65, 0.0), Vector3(0.0, 1.65, 0.0), Vector3.UP)
    else:
        camera.look_at_from_position(Vector3(10.0, 5.6, 8.2), Vector3(0.0, 1.60, 0.0), Vector3.UP)

func make_viewport(context: String) -> Dictionary:
    var viewport := SubViewport.new()
    viewport.size = Vector2i(900, 650)
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
    var rows := payload["variants"][variant] as Array
    var material_counts := {}
    for raw_component in rows:
        var component := raw_component as Dictionary
        root3d.add_child(make_component(component))
        var material_id := String(component["material_id"])
        material_counts[material_id] = int(material_counts.get(material_id, 0)) + 1
    for _i in range(12):
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
        "component_count": rows.size(),
        "material_counts": material_counts,
        "width": image.get_width(),
        "height": image.get_height(),
        "bytes": FileAccess.get_file_as_bytes(capture_path).size()
    }
    viewport.queue_free()
    for _i in range(2):
        await process_frame
    return {"meta": meta, "image": image}

func compare_images(a: Image, b: Image) -> Dictionary:
    if a.get_width() != b.get_width() or a.get_height() != b.get_height():
        return {"state": "FAIL_DIMENSIONS"}
    var changed := 0
    var max_delta := 0.0
    var sum_delta := 0.0
    var min_x := a.get_width()
    var min_y := a.get_height()
    var max_x := -1
    var max_y := -1
    for y in range(a.get_height()):
        for x in range(a.get_width()):
            var ca := a.get_pixel(x, y)
            var cb := b.get_pixel(x, y)
            var delta: float = maxf(absf(ca.r - cb.r), maxf(absf(ca.g - cb.g), absf(ca.b - cb.b)))
            sum_delta += absf(ca.r - cb.r) + absf(ca.g - cb.g) + absf(ca.b - cb.b)
            if delta > (1.0 / 255.0):
                changed += 1
                max_delta = maxf(max_delta, delta)
                min_x = mini(min_x, x)
                min_y = mini(min_y, y)
                max_x = maxi(max_x, x)
                max_y = maxi(max_y, y)
    var total := a.get_width() * a.get_height()
    return {
        "state": "PASS",
        "changed_pixels": changed,
        "total_pixels": total,
        "changed_fraction": float(changed) / float(total),
        "max_rgb_channel_delta": max_delta,
        "mean_absolute_rgb_channel_delta": sum_delta / float(total * 3),
        "changed_bbox": [] if changed == 0 else [min_x, min_y, max_x, max_y]
    }

func _initialize() -> void:
    payload = read_json(PAYLOAD)
    if payload.get("schema") != "axm.building-material-header-segmentation-lookdev/v0.1":
        fail("missing or invalid header segmentation lookdev payload")
        return
    if payload.get("hard_surface_source_head") != EXPECTED_HARD_SURFACE_HEAD:
        fail("Hard-Surface source head drift")
        return
    var truth := payload.get("truth_boundary", {}) as Dictionary
    if truth.get("explicit_segment_id_binding") != true or truth.get("wildcard_or_prefix_material_inference") != false:
        fail("payload does not preserve explicit fail-closed material binding")
        return

    var rows := {}
    for raw_context in payload["contexts"]:
        var context := String(raw_context)
        var control := await capture_variant(context, "logical_pre_segmentation", "res://logical_pre_segmentation-%s.png" % context)
        var candidate := await capture_variant(context, "source_owned_segmented_headers", "res://source_owned_segmented_headers-%s.png" % context)
        if not control.has("meta") or not candidate.has("meta"):
            fail("capture failed for " + context)
            return
        var comparison := compare_images(control["image"] as Image, candidate["image"] as Image)
        if comparison.get("state") != "PASS":
            fail("comparison failed for " + context)
            return
        if float(comparison["changed_fraction"]) > MAX_CONTINUITY_CHANGED_FRACTION:
            fail("header segmentation exceeded bounded material continuity guard in " + context)
            return
        var candidate_meta := candidate["meta"] as Dictionary
        var counts := candidate_meta["material_counts"] as Dictionary
        if int(counts.get("frame_galvanized", 0)) != 16:
            fail("segmented source did not retain exact galvanized frame binding in " + context)
            return
        rows[context] = {
            "control": control["meta"],
            "candidate": candidate["meta"],
            "comparison": comparison,
            "continuity_guard_max_changed_fraction": MAX_CONTINUITY_CHANGED_FRACTION
        }

    receipt["state"] = "PASS_TARGET_HOST_BUILDING_HEADER_SEGMENTATION_MATERIAL_CONTINUITY"
    receipt["godot_version"] = Engine.get_version_info()
    receipt["exact_materials_head"] = payload["exact_materials_head"]
    receipt["hard_surface_source_head"] = payload["hard_surface_source_head"]
    receipt["successor_revision"] = payload["successor_revision"]
    receipt["material_profile_sha256"] = payload["material_profile_sha256"]
    receipt["contexts"] = rows
    receipt["truth_boundary"] = payload["truth_boundary"]
    write_receipt()
    print("AXM BUILDING HEADER SEGMENTATION MATERIAL CONTINUITY ", JSON.stringify(receipt))
    quit(0)
