extends SceneTree

const PAYLOAD := "res://generated/payload.json"
const RECEIPT := "res://runtime_receipt.json"

var payload: Dictionary = {}
var receipt := {
    "schema": "axm.building-material-boundary-shell-compaction-runtime/v0.2",
    "promotion_effect": "NONE",
    "renderer_boundary": "Godot 4.7.2 GL Compatibility. Exact Geometry reference boundary shell and explicitly selected compact receiving shell receive the unchanged Building five-surface scalar PBR family. Normals are explicit per triangle from the exact plane, with no vertex smoothing."
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

func make_material(material_id: String) -> StandardMaterial3D:
    var spec := payload["materials"][material_id] as Dictionary
    var rgba := spec["albedo"] as Array
    var material := StandardMaterial3D.new()
    material.albedo_color = Color(float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
    material.metallic = float(spec["metallic"])
    material.roughness = float(spec["roughness"])
    material.cull_mode = BaseMaterial3D.CULL_BACK
    return material

func make_mesh_variant(variant: String) -> Array:
    var mesh_payload := payload[variant] as Dictionary
    var vertices := mesh_payload["vertices"] as Array
    var triangles := mesh_payload["triangles"] as Array
    var owners := mesh_payload["triangle_owners"] as Array
    var mapping := payload["component_materials"] as Dictionary
    var materials := payload["materials"] as Dictionary
    var nodes: Array = []
    var counts := {}
    for material_id in materials.keys():
        counts[material_id] = 0
        var surface := SurfaceTool.new()
        surface.begin(Mesh.PRIMITIVE_TRIANGLES)
        surface.set_material(make_material(String(material_id)))
        for triangle_index in range(triangles.size()):
            var owner := owners[triangle_index] as Dictionary
            var source_component_id := String(owner["source_component_id"])
            if not mapping.has(source_component_id):
                return []
            if String(mapping[source_component_id]) != String(material_id):
                continue
            var face := triangles[triangle_index] as Array
            var a := source_vec3(vertices[int(face[0])] as Array)
            var b := source_vec3(vertices[int(face[1])] as Array)
            var c := source_vec3(vertices[int(face[2])] as Array)
            var normal := (b - a).cross(c - a).normalized()
            surface.set_normal(normal)
            surface.add_vertex(a)
            surface.set_normal(normal)
            surface.add_vertex(c)
            surface.set_normal(normal)
            surface.add_vertex(b)
            counts[material_id] = int(counts[material_id]) + 1
        var committed := surface.commit()
        if committed != null and int(counts[material_id]) > 0:
            var node := MeshInstance3D.new()
            node.name = "%s-%s" % [variant, material_id]
            node.mesh = committed
            nodes.append(node)
    return [nodes, counts]

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
    var built := make_mesh_variant(variant)
    if built.is_empty():
        viewport.queue_free()
        return {"state": "FAIL_MESH"}
    var nodes := built[0] as Array
    var counts := built[1] as Dictionary
    for node in nodes:
        root3d.add_child(node)
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
        "material_surface_count": nodes.size(),
        "material_triangle_counts": counts,
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
    var payload_schema := String(payload.get("schema", ""))
    if payload_schema != "axm.building-material-boundary-shell-compaction-lookdev/v0.1" and payload_schema != "axm.building-material-boundary-shell-compaction-lookdev/v0.2":
        fail("missing or invalid Materials boundary-shell payload")
        return

    var expected_geometry_head := "43ace6fc44e6f6c0f637cd3436a94099c97c2d48"
    if payload_schema == "axm.building-material-boundary-shell-compaction-lookdev/v0.2":
        expected_geometry_head = "16253e7dd2f8cd590667f9631e4b50fdfcc7280d"
        if payload.get("hard_surface_owner_head") != "35d0ba62d7e534b3cd00ac69e99386843ffa3f2e":
            fail("Hard-Surface compact-v2 owner head drift")
            return
        if payload.get("selected_representation_id") != "boundary-only-union-shell-conforming-compact-v2-001":
            fail("compact-v2 representation selection drift")
            return
        receipt["schema"] = "axm.building-material-boundary-shell-compaction-runtime/v0.2"
    else:
        receipt["schema"] = "axm.building-material-boundary-shell-compaction-runtime/v0.1"

    if payload.get("geometry_donor_head") != expected_geometry_head:
        fail("Geometry donor head drift")
        return
    if payload.get("normal_policy") != "EXPLICIT_PER_TRIANGLE_PLANE_NORMAL__NO_VERTEX_SMOOTHING__HARD_SURFACE_REVIEW":
        fail("hard-surface normal policy drift")
        return

    var rows := {}
    for raw_context in payload["contexts"]:
        var context := String(raw_context)
        var reference_path := "res://reference-%s.png" % context
        var compact_path := "res://compact-%s.png" % context
        var reference_capture := await capture_variant(context, "reference", reference_path)
        var compact_capture := await capture_variant(context, "compact", compact_path)
        if not reference_capture.has("image") or not compact_capture.has("image"):
            fail("capture failed for " + context)
            return
        var comparison := compare_images(reference_capture["image"] as Image, compact_capture["image"] as Image)
        if comparison.get("state") != "PASS":
            fail("comparison failed for " + context)
            return
        rows[context] = {
            "reference": reference_capture["meta"],
            "compact": compact_capture["meta"],
            "comparison": comparison
        }

    receipt["state"] = "PASS_TARGET_HOST_BUILDING_BOUNDARY_SHELL_COMPACTION_MATERIAL_CONTINUITY_CAPTURED"
    receipt["payload_schema"] = payload_schema
    receipt["contexts"] = rows
    receipt["godot_version"] = Engine.get_version_info()
    receipt["exact_materials_head"] = payload["exact_materials_head"]
    receipt["geometry_donor_head"] = payload["geometry_donor_head"]
    receipt["normal_policy"] = payload["normal_policy"]
    receipt["reference_stats"] = payload["reference_stats"]
    receipt["compact_stats"] = payload["compact_stats"]
    receipt["geometry_evidence"] = payload["geometry_evidence"]
    receipt["material_profile_sha256"] = payload["material_profile_sha256"]
    receipt["truth_boundary"] = payload["truth_boundary"]
    if payload_schema == "axm.building-material-boundary-shell-compaction-lookdev/v0.2":
        receipt["hard_surface_owner_head"] = payload["hard_surface_owner_head"]
        receipt["hard_surface_owner_policy_sha256"] = payload["hard_surface_owner_policy_sha256"]
        receipt["semantic_source_variant_id"] = payload["semantic_source_variant_id"]
        receipt["reference_representation_id"] = payload["reference_representation_id"]
        receipt["selected_representation_id"] = payload["selected_representation_id"]
        receipt["geometry_compact_payload_sha256"] = payload["geometry_compact_payload_sha256"]
    write_receipt()
    print("AXM BUILDING BOUNDARY SHELL COMPACTION MATERIAL LOOKDEV ", JSON.stringify(receipt))
    quit(0)
