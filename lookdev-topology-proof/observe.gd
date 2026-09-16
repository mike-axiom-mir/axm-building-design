extends SceneTree

const PAYLOAD := "res://generated/building_material_topology_payload.json"
const RECEIPT := "res://material-topology-lookdev-runtime-receipt.json"

var payload: Dictionary = {}
var receipt := {
    "schema": "axm.building-material-topology-lookdev-runtime/v0.1",
    "promotion_effect": "NONE",
    "coordinate_conversion": "Source (x,y,z) -> Godot (x,z,-y) is orientation reversing, so every source triangle reverses vertex order exactly once before target-host rendering.",
    "renderer_boundary": "Godot 4.7.2 GL Compatibility. Same Building source vertices and same refined scalar-PBR profile are rendered as exact historical face-table defect reproduction, exact Geometry PR #6 closed/outward candidate, and the existing BoxMesh lookdev reference. This is Materials renderer evidence only."
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

func make_material(material_id: String) -> StandardMaterial3D:
    var spec := payload["materials"][material_id] as Dictionary
    var rgba := spec["albedo"] as Array
    var material := StandardMaterial3D.new()
    material.albedo_color = Color(float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
    material.metallic = float(spec["metallic"])
    material.roughness = float(spec["roughness"])
    material.cull_mode = BaseMaterial3D.CULL_BACK
    return material

func make_boxmesh_component(component: Dictionary) -> MeshInstance3D:
    var node := MeshInstance3D.new()
    node.name = String(component["id"]) + "-boxmesh"
    var mesh := BoxMesh.new()
    mesh.size = source_size(component["size_local_xyz_m"] as Array)
    node.mesh = mesh
    node.position = source_vec3(component["center_m"] as Array)
    node.basis = source_basis_to_godot(component["source_basis"] as Array)
    node.material_override = make_material(String(component["material_id"]))
    return node

func make_face_table_component(component: Dictionary, face_key: String) -> MeshInstance3D:
    var node := MeshInstance3D.new()
    node.name = String(component["id"]) + "-" + face_key
    var vertices := component["vertices_m"] as Array
    var faces := payload["faces"][face_key] as Array
    var surface := SurfaceTool.new()
    surface.begin(Mesh.PRIMITIVE_TRIANGLES)
    surface.set_material(make_material(String(component["material_id"])))
    for raw_face in faces:
        var face := raw_face as Array
        # source_vec3 is a handedness-reversing coordinate conversion. Reverse
        # source winding exactly once so source-outward remains Godot-outward.
        var a := source_vec3(vertices[int(face[0])] as Array)
        var b := source_vec3(vertices[int(face[2])] as Array)
        var c := source_vec3(vertices[int(face[1])] as Array)
        var normal := (b - a).cross(c - a).normalized()
        surface.set_normal(normal)
        surface.add_vertex(a)
        surface.set_normal(normal)
        surface.add_vertex(b)
        surface.set_normal(normal)
        surface.add_vertex(c)
    node.mesh = surface.commit()
    return node

func make_component(component: Dictionary, variant: String) -> MeshInstance3D:
    if variant == "boxmesh_reference":
        return make_boxmesh_component(component)
    if variant == "historical_malformed" or variant == "closed_outward_candidate":
        return make_face_table_component(component, variant)
    return null

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
    var count := 0
    for raw_component in payload["components"]:
        var component := raw_component as Dictionary
        var node := make_component(component, variant)
        if node == null:
            viewport.queue_free()
            return {"state": "FAIL_COMPONENT"}
        root3d.add_child(node)
        count += 1
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
        "component_count": count,
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
    if payload.get("schema") != "axm.building-material-topology-lookdev-payload/v0.1":
        fail("missing or invalid Building material topology lookdev payload")
        return

    var rows := {}
    for raw_context in payload["contexts"]:
        var context := String(raw_context)
        var images := {}
        var metas := {}
        for variant in ["historical_malformed", "closed_outward_candidate", "boxmesh_reference"]:
            var path := "res://%s-%s.png" % [variant, context]
            var capture := await capture_variant(context, variant, path)
            if not capture.has("meta"):
                fail("capture failed for " + context + " / " + variant)
                return
            images[variant] = capture["image"]
            metas[variant] = capture["meta"]

        var historical_vs_candidate := compare_images(
            images["historical_malformed"] as Image,
            images["closed_outward_candidate"] as Image
        )
        var candidate_vs_reference := compare_images(
            images["closed_outward_candidate"] as Image,
            images["boxmesh_reference"] as Image
        )
        if historical_vs_candidate.get("state") != "PASS" or int(historical_vs_candidate["changed_pixels"]) <= 0:
            fail("historical/candidate topology comparison produced no visible delta for " + context)
            return
        if candidate_vs_reference.get("state") != "PASS":
            fail("candidate/reference comparison failed for " + context)
            return
        rows[context] = {
            "captures": metas,
            "historical_vs_candidate": historical_vs_candidate,
            "candidate_vs_boxmesh_reference": candidate_vs_reference
        }

    receipt["state"] = "PASS_TARGET_HOST_BUILDING_TOPOLOGY_MATERIAL_AB_CAPTURED"
    receipt["contexts"] = rows
    receipt["godot_version"] = Engine.get_version_info()
    receipt["exact_materials_head"] = payload["exact_materials_head"]
    receipt["geometry_donor_head"] = payload["geometry_donor_head"]
    receipt["material_profile_sha256"] = payload["material_profile_sha256"]
    receipt["truth_boundary"] = payload["truth_boundary"]
    write_receipt()
    print("AXM BUILDING MATERIAL TOPOLOGY LOOKDEV ", JSON.stringify(receipt))
    quit(0)
