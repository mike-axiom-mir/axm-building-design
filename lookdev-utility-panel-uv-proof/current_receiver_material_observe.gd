extends SceneTree

const CONTRACT := "res://generated/current_receiver_material_contract.json"
const OWNER_PNG := "res://utility-panel-review-checker-512.png"
const POSITIVE_GLB := "res://generated/current-receiver-utility-panel-service-faces.glb"
const RECEIPT := "res://utility-panel-current-receiver-material-lookdev-receipt.json"

var contract: Dictionary = {}

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
        "schema": "axm.building-utility-panel-current-receiver-material-lookdev-runtime/v0.1",
        "state": "FAIL_CURRENT_RECEIVER_MATERIAL_LOOKDEV",
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

func vector3_close(actual: Vector3, expected: Array, tolerance := 0.000001) -> bool:
    return (
        absf(actual.x - float(expected[0])) <= tolerance
        and absf(actual.y - float(expected[1])) <= tolerance
        and absf(actual.z - float(expected[2])) <= tolerance
    )

func vector2_close(actual: Vector2, expected: Array, tolerance := 0.000001) -> bool:
    return (
        absf(actual.x - float(expected[0])) <= tolerance
        and absf(actual.y - float(expected[1])) <= tolerance
    )

func find_mesh_instance(node: Node) -> MeshInstance3D:
    if node is MeshInstance3D:
        return node as MeshInstance3D
    for child in node.get_children():
        var found := find_mesh_instance(child)
        if found != null:
            return found
    return null

func import_positive() -> Dictionary:
    var expected_sha := String(contract["technical_art_owner"]["positive_glb_sha256"])
    var actual_sha := sha256_bytes(FileAccess.get_file_as_bytes(POSITIVE_GLB))
    if actual_sha != expected_sha:
        return {"state": "FAIL_GLB_SHA", "actual": actual_sha, "expected": expected_sha}
    var document := GLTFDocument.new()
    var state := GLTFState.new()
    var error := document.append_from_file(POSITIVE_GLB, state)
    if error != OK:
        return {"state": "FAIL_IMPORT", "error": error}
    var root := document.generate_scene(state)
    if root == null:
        return {"state": "FAIL_SCENE"}
    var mesh_instance := find_mesh_instance(root)
    if mesh_instance == null or mesh_instance.mesh == null:
        root.free()
        return {"state": "FAIL_MESH"}
    var mesh := mesh_instance.mesh
    if mesh.get_surface_count() != 1:
        root.free()
        return {"state": "FAIL_SURFACE_COUNT", "surface_count": mesh.get_surface_count()}
    var arrays := mesh.surface_get_arrays(0)
    var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
    var uvs: PackedVector2Array = arrays[Mesh.ARRAY_TEX_UV]
    var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
    var expected: Dictionary = contract["expected_current_receiver_service_faces"]
    var expected_positions: Array = expected["positions"]
    var expected_uvs: Array = expected["owner_uvs"]
    var expected_indices: Array = expected["indices"]
    if vertices.size() != expected_positions.size() or uvs.size() != expected_uvs.size() or indices.size() != expected_indices.size():
        root.free()
        return {"state": "FAIL_ARRAY_COUNTS", "vertices": vertices.size(), "uvs": uvs.size(), "indices": indices.size()}
    for i in range(vertices.size()):
        if not vector3_close(vertices[i], expected_positions[i] as Array):
            root.free()
            return {"state": "FAIL_POSITION", "index": i, "actual": vertices[i], "expected": expected_positions[i]}
        if not vector2_close(uvs[i], expected_uvs[i] as Array):
            root.free()
            return {"state": "FAIL_UV", "index": i, "actual": uvs[i], "expected": expected_uvs[i]}
    for i in range(indices.size()):
        if int(indices[i]) != int(expected_indices[i]):
            root.free()
            return {"state": "FAIL_INDEX", "index": i, "actual": indices[i], "expected": expected_indices[i]}
    var material := mesh.surface_get_material(0)
    if material == null or not (material is BaseMaterial3D):
        root.free()
        return {"state": "FAIL_MATERIAL"}
    var base := material as BaseMaterial3D
    if absf(base.metallic - float(contract["materials_predecessor"]["metallic"])) > 0.000001:
        root.free()
        return {"state": "FAIL_METALLIC", "actual": base.metallic}
    if absf(base.roughness - float(contract["materials_predecessor"]["roughness"])) > 0.000001:
        root.free()
        return {"state": "FAIL_ROUGHNESS", "actual": base.roughness}
    if base.albedo_texture == null:
        root.free()
        return {"state": "FAIL_TEXTURE"}
    var image := base.albedo_texture.get_image()
    if image == null or image.is_empty():
        root.free()
        return {"state": "FAIL_IMAGE"}
    image.convert(Image.FORMAT_RGBA8)
    var rgba_sha := sha256_bytes(image.get_data())
    if rgba_sha != String(contract["materials_predecessor"]["retained_rgba8_sha256"]):
        root.free()
        return {"state": "FAIL_RGBA_SHA", "actual": rgba_sha}
    var result := {
        "state": "PASS",
        "glb_sha256": actual_sha,
        "surface_count": mesh.get_surface_count(),
        "vertex_count": vertices.size(),
        "uv_count": uvs.size(),
        "index_count": indices.size(),
        "image_width": image.get_width(),
        "image_height": image.get_height(),
        "image_rgba8_sha256": rgba_sha,
        "metallic": base.metallic,
        "roughness": base.roughness
    }
    root.free()
    return result

func load_owner_texture() -> ImageTexture:
    var image := Image.new()
    if image.load(OWNER_PNG) != OK or image.is_empty():
        return null
    image.convert(Image.FORMAT_RGBA8)
    if sha256_bytes(image.get_data()) != String(contract["materials_predecessor"]["retained_rgba8_sha256"]):
        return null
    image.generate_mipmaps()
    return ImageTexture.create_from_image(image)

func make_material(unshaded: bool) -> StandardMaterial3D:
    var texture := load_owner_texture()
    if texture == null:
        return null
    var material := StandardMaterial3D.new()
    material.albedo_color = Color.WHITE
    material.albedo_texture = texture
    material.metallic = float(contract["materials_predecessor"]["metallic"])
    material.roughness = float(contract["materials_predecessor"]["roughness"])
    material.cull_mode = BaseMaterial3D.CULL_DISABLED
    material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
    if unshaded:
        material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    return material

func make_native(use_negative_uvs: bool, unshaded: bool) -> MeshInstance3D:
    var expected: Dictionary = contract["expected_current_receiver_service_faces"]
    var vertices := PackedVector3Array()
    for row in expected["positions"]:
        var v := row as Array
        vertices.append(Vector3(float(v[0]), float(v[1]), float(v[2])))
    var normals := PackedVector3Array()
    for row in expected["source_outward_normals"]:
        var n := row as Array
        normals.append(Vector3(float(n[0]), float(n[1]), float(n[2])))
    var uv_rows: Array = expected["aspect_blind_negative_uvs"] if use_negative_uvs else expected["owner_uvs"]
    var uvs := PackedVector2Array()
    for row in uv_rows:
        var uv := row as Array
        uvs.append(Vector2(float(uv[0]), float(uv[1])))
    var indices := PackedInt32Array()
    for value in expected["indices"]:
        indices.append(int(value))
    var arrays := []
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX] = vertices
    arrays[Mesh.ARRAY_NORMAL] = normals
    arrays[Mesh.ARRAY_TEX_UV] = uvs
    arrays[Mesh.ARRAY_INDEX] = indices
    var mesh := ArrayMesh.new()
    mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
    var node := MeshInstance3D.new()
    node.name = "materials_native_current_receiver"
    node.mesh = mesh
    node.material_override = make_material(unshaded)
    return node

func configure_camera(camera: Camera3D, context: String) -> void:
    camera.near = 0.05
    camera.far = 40.0
    var up := Vector3(0.0, 0.0, 1.0)
    if context == "front_receiver":
        camera.fov = 32.0
        camera.look_at_from_position(Vector3(-2.45, 2.65, 1.95), Vector3(-2.45, 6.06, 1.65), up)
    elif context == "east_receiver":
        camera.fov = 32.0
        camera.look_at_from_position(Vector3(7.40, 7.30, 1.95), Vector3(3.94, 7.30, 1.65), up)
    else:
        camera.fov = 42.0
        camera.look_at_from_position(Vector3(8.60, 0.25, 5.10), Vector3(0.50, 6.75, 1.65), up)

func make_viewport(context: String) -> Dictionary:
    var viewport := SubViewport.new()
    viewport.size = Vector2i(900, 700)
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
    env.ambient_light_color = Color(0.44, 0.48, 0.54, 1.0)
    env.ambient_light_energy = 0.50
    var world := WorldEnvironment.new()
    world.environment = env
    root3d.add_child(world)
    var key := DirectionalLight3D.new()
    key.light_energy = 2.0
    key.shadow_enabled = false
    key.rotation_degrees = Vector3(-48.0, -35.0, 18.0)
    root3d.add_child(key)
    var fill_front := OmniLight3D.new()
    fill_front.light_energy = 3.0
    fill_front.omni_range = 14.0
    fill_front.position = Vector3(-2.4, 2.8, 3.4)
    root3d.add_child(fill_front)
    var fill_east := OmniLight3D.new()
    fill_east.light_energy = 2.7
    fill_east.omni_range = 14.0
    fill_east.position = Vector3(7.0, 7.3, 3.2)
    root3d.add_child(fill_east)
    var camera := Camera3D.new()
    root3d.add_child(camera)
    camera.make_current()
    configure_camera(camera, context)
    return {"viewport": viewport, "root": root3d}

func finish_capture(viewport: SubViewport, path: String) -> Dictionary:
    for _i in range(14):
        await process_frame
    var image := viewport.get_texture().get_image()
    if image == null or image.is_empty():
        viewport.queue_free()
        return {"state": "FAIL_CAPTURE"}
    if image.save_png(path) != OK:
        viewport.queue_free()
        return {"state": "FAIL_SAVE"}
    var meta := {
        "state": "PASS",
        "width": image.get_width(),
        "height": image.get_height(),
        "bytes": FileAccess.get_file_as_bytes(path).size()
    }
    viewport.queue_free()
    for _i in range(2):
        await process_frame
    return {"state": "PASS", "meta": meta, "image": image}

func capture_native(context: String, negative_uvs: bool, unshaded: bool, path: String) -> Dictionary:
    var setup := make_viewport(context)
    var viewport := setup["viewport"] as SubViewport
    var root3d := setup["root"] as Node3D
    var node := make_native(negative_uvs, unshaded)
    if node == null or node.material_override == null:
        viewport.queue_free()
        return {"state": "FAIL_NATIVE"}
    root3d.add_child(node)
    return await finish_capture(viewport, path)

func capture_imported_unshaded(context: String, path: String) -> Dictionary:
    var setup := make_viewport(context)
    var viewport := setup["viewport"] as SubViewport
    var root3d := setup["root"] as Node3D
    var document := GLTFDocument.new()
    var state := GLTFState.new()
    var error := document.append_from_file(POSITIVE_GLB, state)
    if error != OK:
        viewport.queue_free()
        return {"state": "FAIL_IMPORT", "error": error}
    var imported_root := document.generate_scene(state)
    if imported_root == null:
        viewport.queue_free()
        return {"state": "FAIL_SCENE"}
    var mesh_instance := find_mesh_instance(imported_root)
    if mesh_instance == null:
        imported_root.free()
        viewport.queue_free()
        return {"state": "FAIL_MESH"}
    var material := make_material(true)
    if material == null:
        imported_root.free()
        viewport.queue_free()
        return {"state": "FAIL_MATERIAL"}
    mesh_instance.material_override = material
    root3d.add_child(imported_root)
    return await finish_capture(viewport, path)

func compare_images(a: Image, b: Image) -> Dictionary:
    if a.get_width() != b.get_width() or a.get_height() != b.get_height():
        return {"state": "FAIL_DIMENSIONS"}
    var raw_changed := 0
    var changed_gt_1lsb := 0
    var max_delta := 0.0
    var threshold := 1.0 / 255.0 + 0.0000001
    for y in range(a.get_height()):
        for x in range(a.get_width()):
            var pa := a.get_pixel(x, y)
            var pb := b.get_pixel(x, y)
            var delta: float = maxf(absf(pa.r - pb.r), maxf(absf(pa.g - pb.g), absf(pa.b - pb.b)))
            if delta > 0.0:
                raw_changed += 1
            if delta > threshold:
                changed_gt_1lsb += 1
            if delta > max_delta:
                max_delta = delta
    return {
        "state": "PASS",
        "raw_changed_pixels": raw_changed,
        "changed_pixels_gt_1lsb": changed_gt_1lsb,
        "max_rgb_channel_delta": max_delta
    }

func _initialize() -> void:
    contract = read_json(CONTRACT)
    if contract.is_empty():
        fail("missing Materials current-receiver contract")
        return
    if String(contract.get("schema", "")) != "axm.building-utility-panel-current-receiver-material-lookdev/v0.1":
        fail("Materials current-receiver contract schema drift")
        return
    var imported_check := import_positive()
    if imported_check.get("state") != "PASS":
        fail("exact Technical Art current-receiver carrier failed import identity", {"import": imported_check})
        return

    var contexts: Array = contract["comparison"]["contexts"]
    var minimum_negative := int(contract["comparison"]["minimum_negative_changed_pixels_gt_1lsb_per_context"])
    var minimum_delta := float(contract["comparison"]["minimum_negative_max_rgb_channel_delta"])
    var minimum_lighting := int(contract["comparison"]["minimum_lighting_response_changed_pixels_gt_1lsb_per_context"])
    var rows := {}
    var total_negative := 0

    for context_value in contexts:
        var context := String(context_value)
        var prefix := "utility-panel-current-receiver-" + context
        var native_unshaded := await capture_native(context, false, true, prefix + "-native-positive-unshaded.png")
        var imported_unshaded := await capture_imported_unshaded(context, prefix + "-imported-positive-unshaded.png")
        var native_lit := await capture_native(context, false, false, prefix + "-native-positive-lit.png")
        var negative_lit := await capture_native(context, true, false, prefix + "-native-aspect-blind-negative-lit.png")
        for capture in [native_unshaded, imported_unshaded, native_lit, negative_lit]:
            if capture.get("state") != "PASS":
                fail("render capture failed", {"context": context, "capture": capture})
                return
        var transport := compare_images(native_unshaded["image"], imported_unshaded["image"])
        var negative := compare_images(native_lit["image"], negative_lit["image"])
        var lighting := compare_images(native_unshaded["image"], native_lit["image"])
        if int(transport["raw_changed_pixels"]) != 0 or int(transport["changed_pixels_gt_1lsb"]) != 0:
            fail("imported current-receiver carrier is not pixel-identical to native owner coverage", {"context": context, "comparison": transport})
            return
        if int(negative["changed_pixels_gt_1lsb"]) < minimum_negative or float(negative["max_rgb_channel_delta"]) < minimum_delta:
            fail("aspect-blind UV negative is not visibly distinguishable", {"context": context, "comparison": negative})
            return
        if int(lighting["changed_pixels_gt_1lsb"]) < minimum_lighting:
            fail("lit Materials receiver is visually inert", {"context": context, "comparison": lighting})
            return
        total_negative += int(negative["changed_pixels_gt_1lsb"])
        rows[context] = {
            "native_positive_unshaded": native_unshaded["meta"],
            "imported_positive_unshaded": imported_unshaded["meta"],
            "native_positive_lit": native_lit["meta"],
            "native_aspect_blind_negative_lit": negative_lit["meta"],
            "native_vs_imported_positive_unshaded": transport,
            "native_positive_lit_vs_aspect_blind_negative_lit": negative,
            "native_positive_unshaded_vs_lit": lighting
        }

    var receipt := {
        "schema": "axm.building-utility-panel-current-receiver-material-lookdev-runtime/v0.1",
        "state": "PASS_TARGET_HOST_BUILDING_CURRENT_RECEIVER_DUAL_PANEL_MATERIAL_LOOKDEV_CONTINUITY",
        "decision": "PASS_EXACT_TA_CURRENT_RECEIVER_SERVICE_FACES_PRESERVE_OWNER_COVERAGE_AND_PHYSICAL_DENSITY_DISTINCTION__HOLD_ENV_RUNTIME_ART_QA_ADOPTION",
        "renderer": "Godot 4.7.2 stable / GL Compatibility / X11 / Mesa llvmpipe proof host",
        "positive_import": imported_check,
        "contexts": rows,
        "total_changed_pixels_gt_1lsb_positive_vs_aspect_blind_negative": total_negative,
        "reusable_discovery": "A current-world receiver transport should be checked in two stages: exact imported-vs-native unshaded coverage continuity on the owner-bound service faces, then a same-native-geometry lit UV negative that changes only the chart extent. This separates transport identity from material-density visibility without granting Environment adoption.",
        "truth_boundary": "This PASS is limited to the two exact current-receiver outer service faces and three Materials review cameras on Godot 4.7.2 GL Compatibility. The full 184v/276t/five-surface Environment receiver is not mutated or adopted here. The aspect-blind negative is Materials receiving-only. No production UV, texture, Environment, Runtime, Art/QA, CANON or production-readiness promotion follows.",
        "promotion_effect": "NONE"
    }
    write_receipt(receipt)
    print(JSON.stringify(receipt, "  "))
    quit(0)
