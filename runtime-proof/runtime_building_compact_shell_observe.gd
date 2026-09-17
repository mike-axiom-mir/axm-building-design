extends SceneTree

const WIDTH := 960
const HEIGHT := 720
const PAYLOAD_PATH := "res://generated/building_compact_shell_runtime_payload.json"
const MODE_ENV := "AXM_RUNTIME_BUILDING_SHELL_MODE"
const OUT_ENV := "AXM_RUNTIME_BUILDING_SHELL_OUT"
const CONTROL := "REFERENCE_CONTROL"
const CANDIDATE := "COMPACT_V2_CANDIDATE"

var _failed := false

func fail(message:String)->void:
    push_error(message)
    _failed = true

func load_json(path:String)->Dictionary:
    var file := FileAccess.open(path, FileAccess.READ)
    if file == null:
        fail("cannot open JSON: " + path)
        return {}
    var parsed = JSON.parse_string(file.get_as_text())
    if not (parsed is Dictionary):
        fail("JSON root is not a dictionary: " + path)
        return {}
    return parsed

func v3(row:Array)->Vector3:
    return Vector3(float(row[0]), float(row[1]), float(row[2]))

func build_mesh(row:Dictionary)->ArrayMesh:
    var vertices := PackedVector3Array()
    var normals := PackedVector3Array()
    var indices := PackedInt32Array()
    for item in row["vertices"]:
        vertices.append(v3(item))
    for item in row["normals"]:
        normals.append(v3(item))
    for item in row["indices"]:
        indices.append(int(item))
    if vertices.size() != int(row["stored_vertex_count"]):
        fail("stored vertex count drift")
    if normals.size() != vertices.size():
        fail("normal count drift")
    if indices.size() != int(row["index_count"]):
        fail("index count drift")
    if indices.size() / 3 != int(row["triangle_count"]):
        fail("triangle count drift")
    var arrays := []
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX] = vertices
    arrays[Mesh.ARRAY_NORMAL] = normals
    arrays[Mesh.ARRAY_INDEX] = indices
    var mesh := ArrayMesh.new()
    mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
    var material := StandardMaterial3D.new()
    material.albedo_color = Color(0.50, 0.56, 0.61, 1.0)
    material.metallic = 0.18
    material.roughness = 0.68
    material.cull_mode = BaseMaterial3D.CULL_BACK
    mesh.surface_set_material(0, material)
    return mesh

func render_info()->Dictionary:
    return {
        "draw_calls": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
        "objects": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME),
        "primitives": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME),
        "buffer_memory": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_BUFFER_MEM_USED),
        "texture_memory": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TEXTURE_MEM_USED),
    }

func save_json(path:String, value:Dictionary)->void:
    var file := FileAccess.open(path, FileAccess.WRITE)
    if file == null:
        fail("cannot write receipt: " + path)
        return
    file.store_string(JSON.stringify(value, "  ") + "\n")

func capture(camera:Camera3D, center:Vector3, position:Vector3, name:String, out_dir:String)->Dictionary:
    camera.position = position
    camera.look_at(center, Vector3.UP)
    await process_frame
    await process_frame
    await RenderingServer.frame_post_draw
    var image := get_root().get_texture().get_image()
    if image == null or image.is_empty():
        fail("empty viewport image: " + name)
        return {}
    var image_path := out_dir.path_join(name + ".png")
    var save_error := image.save_png(image_path)
    if save_error != OK:
        fail("PNG save failed: " + name)
        return {}
    var result := {"camera": name}
    result.merge(render_info())
    return result

func _initialize()->void:
    call_deferred("run")

func run()->void:
    var mode := OS.get_environment(MODE_ENV)
    if mode != CONTROL and mode != CANDIDATE:
        fail("explicit Runtime shell mode required")
        quit(1)
        return
    var out_dir := OS.get_environment(OUT_ENV)
    if out_dir.is_empty():
        fail("explicit Runtime shell output directory required")
        quit(1)
        return
    DirAccess.make_dir_recursive_absolute(out_dir)
    var payload := load_json(PAYLOAD_PATH)
    if payload.is_empty():
        quit(1)
        return
    if String(payload.get("schema", "")) != "axm.runtime-building-compact-shell-budget/v0.1":
        fail("payload schema drift")
        quit(1)
        return
    var row:Dictionary = payload["control"] if mode == CONTROL else payload["candidate"]
    var mesh := build_mesh(row)
    if _failed:
        quit(1)
        return

    get_root().size = Vector2i(WIDTH, HEIGHT)
    var root3d := Node3D.new()
    get_root().add_child(root3d)
    var environment_node := WorldEnvironment.new()
    var environment := Environment.new()
    environment.background_mode = Environment.BG_COLOR
    environment.background_color = Color(0.075, 0.085, 0.10, 1.0)
    environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
    environment.ambient_light_color = Color(0.72, 0.76, 0.82, 1.0)
    environment.ambient_light_energy = 0.78
    environment_node.environment = environment
    root3d.add_child(environment_node)

    var instance := MeshInstance3D.new()
    instance.mesh = mesh
    root3d.add_child(instance)

    var key := DirectionalLight3D.new()
    key.light_energy = 1.2
    key.rotation_degrees = Vector3(-52.0, -34.0, 0.0)
    key.shadow_enabled = true
    root3d.add_child(key)

    var camera := Camera3D.new()
    camera.fov = 52.0
    camera.current = true
    root3d.add_child(camera)

    var bmin := v3(payload["bounds"]["min"])
    var bmax := v3(payload["bounds"]["max"])
    var center := (bmin + bmax) * 0.5
    var extent := bmax - bmin
    var radius := max(max(extent.x, extent.y), extent.z)
    if radius <= 0.0:
        fail("invalid shell bounds")
        quit(1)
        return

    var cameras:Array = [
        {"name":"front_oblique", "position": center + Vector3(radius * 1.35, radius * 0.82, radius * 1.55)},
        {"name":"rear_oblique", "position": center + Vector3(-radius * 1.45, radius * 0.72, -radius * 1.18)},
    ]
    var rows:Array = []
    for context in cameras:
        var receipt_row := await capture(camera, center, context["position"], context["name"], out_dir)
        if receipt_row.is_empty():
            quit(1)
            return
        rows.append(receipt_row)

    var receipt := {
        "schema": "axm.runtime-building-compact-shell-godot-observer/v0.1",
        "mode": mode,
        "exact_runtime_head": payload["exact_runtime_head"],
        "hard_surface_parent_head": payload["hard_surface_parent_head"],
        "godot_version": Engine.get_version_info(),
        "renderer": RenderingServer.get_video_adapter_name(),
        "mesh": {
            "stored_vertex_count": int(row["stored_vertex_count"]),
            "index_count": int(row["index_count"]),
            "triangle_count": int(row["triangle_count"]),
            "surface_count": int(row["surface_count"]),
            "modeled_payload_bytes": int(row["modeled_payload_bytes"]),
        },
        "cameras": rows,
        "truth_boundary": "Proof-host GL Compatibility rendering of one neutral material and explicit hard-edge normals. It is not current Building Materials/Environment acceptance and not a target-device performance claim.",
    }
    save_json(out_dir.path_join("runtime.json"), receipt)
    if _failed:
        quit(1)
        return
    print(JSON.stringify(receipt, "  "))
    quit(0)
