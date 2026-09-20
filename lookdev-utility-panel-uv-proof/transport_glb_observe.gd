extends SceneTree

const CONTRACT := "res://generated/ta_glb_receiving_contract.json"
const OWNER_PNG := "res://utility-panel-review-checker-512.png"
const POSITIVE_GLB := "res://generated/utility-panel-material-review-transport.glb"
const NEGATIVE_GLB := "res://generated/utility-panel-material-review-transport-aspect-blind-negative.glb"
const RECEIPT := "res://utility-panel-ta-glb-material-lookdev-receipt.json"

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
        "schema": "axm.building-utility-panel-ta-glb-material-receiving-runtime/v0.1",
        "state": "FAIL_MATERIAL_RECEIVING_EVIDENCE",
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

func find_mesh_instance(node: Node) -> MeshInstance3D:
    if node is MeshInstance3D:
        return node as MeshInstance3D
    for child in node.get_children():
        var found := find_mesh_instance(child)
        if found != null:
            return found
    return null

func import_glb(path: String) -> Dictionary:
    var document := GLTFDocument.new()
    var state := GLTFState.new()
    var error := document.append_from_file(path, state)
    if error != OK:
        return {"state": "FAIL_IMPORT", "error": error}
    var root := document.generate_scene(state)
    if root == null:
        return {"state": "FAIL_SCENE"}
    var mesh_instance := find_mesh_instance(root)
    if mesh_instance == null or mesh_instance.mesh == null:
        root.free()
        return {"state": "FAIL_MESH"}
    return {"state": "PASS", "root": root, "mesh_instance": mesh_instance}

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

func inspect_positive_import() -> Dictionary:
    var expected: Dictionary = contract["expected_imported_surface"]
    var glb_sha := sha256_bytes(FileAccess.get_file_as_bytes(POSITIVE_GLB))
    var expected_glb_sha := String(contract["technical_art_owner"]["positive_glb_sha256"])
    if glb_sha != expected_glb_sha:
        return {"state": "FAIL_POSITIVE_GLB_SHA", "actual": glb_sha, "expected": expected_glb_sha}
    var imported := import_glb(POSITIVE_GLB)
    if imported.get("state") != "PASS":
        return imported
    var root := imported["root"] as Node
    var mesh_instance := imported["mesh_instance"] as MeshInstance3D
    var mesh := mesh_instance.mesh
    if mesh.get_surface_count() != 1:
        root.free()
        return {"state": "FAIL_SURFACE_COUNT", "surface_count": mesh.get_surface_count()}
    var arrays := mesh.surface_get_arrays(0)
    var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
    var uvs: PackedVector2Array = arrays[Mesh.ARRAY_TEX_UV]
    var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
    var expected_positions: Array = expected["positions"]
    var expected_uvs: Array = expected["uvs"]
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
    if absf(base.metallic - float(expected["metallic"])) > 0.000001:
        root.free()
        return {"state": "FAIL_METALLIC", "actual": base.metallic, "expected": expected["metallic"]}
    if absf(base.roughness - float(expected["roughness"])) > 0.000001:
        root.free()
        return {"state": "FAIL_ROUGHNESS", "actual": base.roughness, "expected": expected["roughness"]}
    if base.albedo_texture == null:
        root.free()
        return {"state": "FAIL_TEXTURE"}
    var image := base.albedo_texture.get_image()
    if image == null or image.is_empty():
        root.free()
        return {"state": "FAIL_IMAGE"}
    image.convert(Image.FORMAT_RGBA8)
    var rgba_sha := sha256_bytes(image.get_data())
    if rgba_sha != String(expected["image_rgba8_sha256"]):
        root.free()
        return {"state": "FAIL_RGBA_SHA", "actual": rgba_sha, "expected": expected["image_rgba8_sha256"]}
    var result := {
        "state": "PASS",
        "glb_sha256": glb_sha,
        "surface_count": mesh.get_surface_count(),
        "vertex_count": vertices.size(),
        "uv_count": uvs.size(),
        "index_count": indices.size(),
        "metallic": base.metallic,
        "roughness": base.roughness,
        "cull_mode": base.cull_mode,
        "image_width": image.get_width(),
        "image_height": image.get_height(),
        "image_rgba8_sha256": rgba_sha,
    }
    root.free()
    return result

func inspect_negative_identity() -> Dictionary:
    var glb_sha := sha256_bytes(FileAccess.get_file_as_bytes(NEGATIVE_GLB))
    var expected_sha := String(contract["technical_art_owner"]["aspect_blind_negative_glb_sha256"])
    if glb_sha != expected_sha:
        return {"state": "FAIL_NEGATIVE_GLB_SHA", "actual": glb_sha, "expected": expected_sha}
    var imported := import_glb(NEGATIVE_GLB)
    if imported.get("state") != "PASS":
        return imported
    var root := imported["root"] as Node
    var mesh_instance := imported["mesh_instance"] as MeshInstance3D
    var mesh := mesh_instance.mesh
    var arrays := mesh.surface_get_arrays(0)
    var uvs: PackedVector2Array = arrays[Mesh.ARRAY_TEX_UV]
    var expected_negative := [
        Vector2(0.0, 0.0),
        Vector2(1.0, 0.0),
        Vector2(1.0, 1.0),
        Vector2(0.0, 1.0),
    ]
    if uvs.size() != expected_negative.size():
        root.free()
        return {"state": "FAIL_NEGATIVE_UV_COUNT", "uv_count": uvs.size()}
    for i in range(uvs.size()):
        if uvs[i].distance_to(expected_negative[i]) > 0.000001:
            root.free()
            return {"state": "FAIL_NEGATIVE_UV", "index": i, "actual": uvs[i], "expected": expected_negative[i]}
    root.free()
    return {"state": "PASS", "glb_sha256": glb_sha}

func load_owner_texture() -> ImageTexture:
    var image := Image.new()
    if image.load(OWNER_PNG) != OK or image.is_empty():
        return null
    image.convert(Image.FORMAT_RGBA8)
    var expected_sha := String(contract["materials_predecessor"]["serialized_rgba8_sha256"])
    if sha256_bytes(image.get_data()) != expected_sha:
        return null
    image.generate_mipmaps()
    return ImageTexture.create_from_image(image)

func make_unshaded_owner_material() -> StandardMaterial3D:
    var texture := load_owner_texture()
    if texture == null:
        return null
    var material := StandardMaterial3D.new()
    material.albedo_color = Color.WHITE
    material.albedo_texture = texture
    material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    material.cull_mode = BaseMaterial3D.CULL_DISABLED
    material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
    return material

func make_native_reference() -> MeshInstance3D:
    var expected: Dictionary = contract["expected_imported_surface"]
    var vertices := PackedVector3Array()
    for row in expected["positions"]:
        var v := row as Array
        vertices.append(Vector3(float(v[0]), float(v[1]), float(v[2])))
    var uvs := PackedVector2Array()
    for row in expected["uvs"]:
        var uv := row as Array
        uvs.append(Vector2(float(uv[0]), float(uv[1])))
    var indices := PackedInt32Array()
    for value in expected["indices"]:
        indices.append(int(value))
    var arrays := []
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX] = vertices
    arrays[Mesh.ARRAY_TEX_UV] = uvs
    arrays[Mesh.ARRAY_INDEX] = indices
    var mesh := ArrayMesh.new()
    mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
    var node := MeshInstance3D.new()
    node.name = "materials_owner_native_reference"
    node.mesh = mesh
    node.material_override = make_unshaded_owner_material()
    return node

func configure_camera(camera: Camera3D, context: String) -> void:
    camera.near = 0.05
    camera.far = 20.0
    camera.fov = 38.0
    var target := Vector3(0.04, 0.0, 0.0)
    var source_up := Vector3(0.0, 0.0, 1.0)
    if context == "front":
        camera.look_at_from_position(Vector3(-3.0, 0.0, 0.0), target, source_up)
    elif context == "oblique":
        camera.look_at_from_position(Vector3(-2.6, 1.45, 0.80), target, source_up)
    else:
        camera.look_at_from_position(Vector3(-0.85, 2.75, 0.45), target, source_up)

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
    env.ambient_light_color = Color(0.46, 0.50, 0.56, 1.0)
    env.ambient_light_energy = 0.42
    var world := WorldEnvironment.new()
    world.environment = env
    root3d.add_child(world)

    var key := DirectionalLight3D.new()
    key.light_energy = 2.15
    key.shadow_enabled = false
    key.rotation_degrees = Vector3(-42.0, -28.0, 16.0)
    root3d.add_child(key)

    var fill := OmniLight3D.new()
    fill.light_energy = 3.2
    fill.omni_range = 10.0
    fill.position = Vector3(-2.1, -2.2, 2.3)
    root3d.add_child(fill)

    var camera := Camera3D.new()
    root3d.add_child(camera)
    camera.make_current()
    configure_camera(camera, context)
    return {"viewport": viewport, "root": root3d}

func capture_native_unshaded(context: String, path: String) -> Dictionary:
    var setup := make_viewport(context)
    var viewport := setup["viewport"] as SubViewport
    var root3d := setup["root"] as Node3D
    var node := make_native_reference()
    if node == null or node.material_override == null:
        viewport.queue_free()
        return {"state": "FAIL_NATIVE_REFERENCE"}
    root3d.add_child(node)
    return await finish_capture(viewport, path)

func capture_imported(context: String, glb_path: String, unshaded: bool, path: String) -> Dictionary:
    var setup := make_viewport(context)
    var viewport := setup["viewport"] as SubViewport
    var root3d := setup["root"] as Node3D
    var imported := import_glb(glb_path)
    if imported.get("state") != "PASS":
        viewport.queue_free()
        return imported
    var imported_root := imported["root"] as Node3D
    var mesh_instance := imported["mesh_instance"] as MeshInstance3D
    if unshaded:
        var material := make_unshaded_owner_material()
        if material == null:
            imported_root.free()
            viewport.queue_free()
            return {"state": "FAIL_OWNER_MATERIAL"}
        mesh_instance.material_override = material
    root3d.add_child(imported_root)
    return await finish_capture(viewport, path)

func finish_capture(viewport: SubViewport, path: String) -> Dictionary:
    for _i in range(16):
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
        "bytes": FileAccess.get_file_as_bytes(path).size(),
    }
    viewport.queue_free()
    for _i in range(2):
        await process_frame
    return {"state": "PASS", "meta": meta, "image": image}

func compare_images(a: Image, b: Image) -> Dictionary:
    if a.get_width() != b.get_width() or a.get_height() != b.get_height():
        return {"state": "FAIL_DIMENSIONS"}
    var raw_changed := 0
    var changed_gt_1lsb := 0
    var max_delta := 0.0
    var sum_delta := 0.0
    for y in range(a.get_height()):
        for x in range(a.get_width()):
            var ca := a.get_pixel(x, y)
            var cb := b.get_pixel(x, y)
            var dr := absf(ca.r - cb.r)
            var dg := absf(ca.g - cb.g)
            var db := absf(ca.b - cb.b)
            var delta := maxf(dr, maxf(dg, db))
            if delta > 0.0:
                raw_changed += 1
            if delta > (1.0 / 255.0):
                changed_gt_1lsb += 1
            max_delta = maxf(max_delta, delta)
            sum_delta += (dr + dg + db) / 3.0
    var total := a.get_width() * a.get_height()
    return {
        "state": "PASS",
        "raw_changed_pixels": raw_changed,
        "changed_pixels_gt_1lsb": changed_gt_1lsb,
        "total_pixels": total,
        "changed_fraction_gt_1lsb": float(changed_gt_1lsb) / float(total),
        "max_rgb_channel_delta": max_delta,
        "mean_rgb_channel_delta": sum_delta / float(total),
    }

func _initialize() -> void:
    contract = read_json(CONTRACT)
    if String(contract.get("schema", "")) != "axm.building-utility-panel-ta-glb-material-receiving/v0.1":
        fail("missing or invalid Technical Art GLB receiving contract")
        return
    var owner_png_sha := sha256_bytes(FileAccess.get_file_as_bytes(OWNER_PNG))
    if owner_png_sha != String(contract["materials_predecessor"]["serialized_png_sha256"]):
        fail("Materials serialized PNG byte identity drift", {"actual": owner_png_sha})
        return

    var positive_import := inspect_positive_import()
    if positive_import.get("state") != "PASS":
        fail("positive Technical Art carrier import drift", {"inspection": positive_import})
        return
    var negative_import := inspect_negative_identity()
    if negative_import.get("state") != "PASS":
        fail("aspect-blind Technical Art negative identity drift", {"inspection": negative_import})
        return

    var comparison: Dictionary = contract["comparison"]
    var rows := {}
    var negative_total := 0
    for raw_context in comparison["contexts"]:
        var context := String(raw_context)
        var native_path := "res://utility-panel-ta-glb-%s-owner-native-unshaded.png" % context
        var imported_unshaded_path := "res://utility-panel-ta-glb-%s-imported-positive-unshaded.png" % context
        var positive_lit_path := "res://utility-panel-ta-glb-%s-imported-positive-lit.png" % context
        var negative_lit_path := "res://utility-panel-ta-glb-%s-imported-negative-lit.png" % context

        var native := await capture_native_unshaded(context, native_path)
        var imported_unshaded := await capture_imported(context, POSITIVE_GLB, true, imported_unshaded_path)
        var positive_lit := await capture_imported(context, POSITIVE_GLB, false, positive_lit_path)
        var negative_lit := await capture_imported(context, NEGATIVE_GLB, false, negative_lit_path)
        for capture in [native, imported_unshaded, positive_lit, negative_lit]:
            if capture.get("state") != "PASS" or not capture.has("image"):
                fail("real-render capture failed: %s" % context, {"capture": capture})
                return

        var transport_diff := compare_images(native["image"] as Image, imported_unshaded["image"] as Image)
        var negative_diff := compare_images(positive_lit["image"] as Image, negative_lit["image"] as Image)
        var lighting_response := compare_images(imported_unshaded["image"] as Image, positive_lit["image"] as Image)

        if int(transport_diff.get("raw_changed_pixels", -1)) != 0:
            fail("owner-native versus imported positive unshaded transport is not pixel-identical: %s" % context, {"transport_diff": transport_diff})
            return
        if int(negative_diff.get("changed_pixels_gt_1lsb", 0)) < int(comparison["minimum_negative_changed_pixels_gt_1lsb_per_context"]):
            fail("aspect-blind negative is not visually distinguishable after import: %s" % context, {"negative_diff": negative_diff})
            return
        if float(negative_diff.get("max_rgb_channel_delta", 0.0)) < float(comparison["minimum_negative_max_rgb_channel_delta"]):
            fail("aspect-blind negative maximum delta is too weak: %s" % context, {"negative_diff": negative_diff})
            return
        if int(lighting_response.get("changed_pixels_gt_1lsb", 0)) < int(comparison["minimum_lighting_response_changed_pixels_gt_1lsb_per_context"]):
            fail("lit imported material path appears visually inert: %s" % context, {"lighting_response": lighting_response})
            return

        negative_total += int(negative_diff["changed_pixels_gt_1lsb"])
        rows[context] = {
            "owner_native_unshaded_meta": native["meta"],
            "imported_positive_unshaded_meta": imported_unshaded["meta"],
            "imported_positive_lit_meta": positive_lit["meta"],
            "imported_negative_lit_meta": negative_lit["meta"],
            "owner_native_vs_imported_positive_unshaded": transport_diff,
            "imported_positive_lit_vs_aspect_blind_negative_lit": negative_diff,
            "imported_positive_unshaded_vs_lit": lighting_response,
        }

    var result := {
        "schema": "axm.building-utility-panel-ta-glb-material-receiving-runtime/v0.1",
        "state": "PASS_TARGET_HOST_BUILDING_UTILITY_PANEL_TA_GLB_MATERIAL_RECEIVING_CONTINUITY",
        "decision": "PASS_EXACT_TA_GLB_PRESERVES_OWNER_TEXTURE_UV_COVERAGE_AND_LIT_PHYSICAL_DENSITY_DISTINCTION__HOLD_ENV_RUNTIME_ART_QA_ADOPTION",
        "renderer": "Godot 4.7.2 stable / GL Compatibility / X11 / Mesa llvmpipe proof host",
        "positive_import": positive_import,
        "negative_import": negative_import,
        "contexts": rows,
        "total_changed_pixels_gt_1lsb_positive_vs_aspect_blind_negative": negative_total,
        "ownership_boundary": contract["ownership_boundary"],
        "truth_boundary": contract["truth_boundary"],
        "promotion_effect": "NONE"
    }
    write_receipt(result)
    print(JSON.stringify(result, "  "))
    quit(0)
