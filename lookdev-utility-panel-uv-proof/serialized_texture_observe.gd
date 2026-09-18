extends "res://observe.gd"

const SERIALIZED_CONTRACT := "res://generated/serialized_review_texture_contract.json"
const SERIALIZED_PNG := "res://utility-panel-review-checker-512.png"
const SERIALIZED_RECEIPT := "res://utility-panel-serialized-texture-runtime-receipt.json"

func sha256_bytes(data: PackedByteArray) -> String:
    var context := HashingContext.new()
    if context.start(HashingContext.HASH_SHA256) != OK:
        return ""
    if context.update(data) != OK:
        return ""
    return context.finish().hex_encode()

func write_serialized_receipt(data: Dictionary) -> void:
    var file := FileAccess.open(SERIALIZED_RECEIPT, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(data, "  ") + "\n")
        file.close()

func fail_serialized(message: String, extra := {}) -> void:
    var data := {
        "schema": "axm.building-utility-panel-serialized-review-texture-runtime/v0.1",
        "state": "FAIL_INFRASTRUCTURE",
        "failure": message,
        "promotion_effect": "NONE"
    }
    for key in extra:
        data[key] = extra[key]
    write_serialized_receipt(data)
    push_error(message)
    quit(1)

func build_base_review_image() -> Image:
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
    return image

func texture_from_base_image(base: Image) -> ImageTexture:
    var image := base.duplicate()
    image.generate_mipmaps()
    return ImageTexture.create_from_image(image)

func _initialize() -> void:
    payload = read_json(PAYLOAD)
    var contract := read_json(SERIALIZED_CONTRACT)
    if String(payload.get("schema", "")) != PAYLOAD_SCHEMA_CLEARANCE_SUCCESSOR:
        fail_serialized("serialized review requires exact clearance-successor Materials payload")
        return
    if String(contract.get("schema", "")) != "axm.building-utility-panel-serialized-review-texture/v0.1":
        fail_serialized("missing or invalid serialized review texture contract")
        return
    if String(contract.get("asset_id", "")) != String(payload.get("asset_id", "")):
        fail_serialized("asset identity drift")
        return
    if String(contract.get("surface_id", "")) != String(payload.get("surface_id", "")):
        fail_serialized("surface identity drift")
        return

    var review_contract: Dictionary = contract["review_texture"]
    var atlas: Dictionary = payload["review_atlas"]
    if atlas["size_px"] != review_contract["image_size_px"]:
        fail_serialized("review texture dimensions drift")
        return
    if atlas["active_region_px"] != review_contract["active_region_px"]:
        fail_serialized("review active-region dimensions drift")
        return
    if atlas["active_region_origin_px"] != review_contract["active_region_origin_px"]:
        fail_serialized("review active-region origin drift")
        return
    if int(atlas["checker_period_px"]) != int(review_contract["checker_period_px"]):
        fail_serialized("checker period drift")
        return
    if atlas["texel_density_px_per_m"] != review_contract["directional_texels_per_m_by_chart_axis"]:
        fail_serialized("directional review density drift")
        return

    var base_image := build_base_review_image()
    if base_image == null or base_image.is_empty():
        fail_serialized("failed to build base review image")
        return
    var base_rgba8 := base_image.get_data()
    var base_rgba8_sha := sha256_bytes(base_rgba8)
    if base_rgba8_sha == "":
        fail_serialized("failed to hash in-memory RGBA8 base level")
        return
    if base_image.save_png(SERIALIZED_PNG) != OK:
        fail_serialized("failed to serialize review texture PNG")
        return

    var serialized_bytes := FileAccess.get_file_as_bytes(SERIALIZED_PNG)
    var serialized_png_sha := sha256_bytes(serialized_bytes)
    var loaded := Image.new()
    if loaded.load(SERIALIZED_PNG) != OK or loaded.is_empty():
        fail_serialized("failed to reload serialized review texture PNG")
        return
    loaded.convert(Image.FORMAT_RGBA8)
    if loaded.get_width() != base_image.get_width() or loaded.get_height() != base_image.get_height():
        fail_serialized("serialized image dimensions changed")
        return
    var loaded_rgba8 := loaded.get_data()
    var loaded_rgba8_sha := sha256_bytes(loaded_rgba8)
    if loaded_rgba8_sha != base_rgba8_sha or loaded_rgba8 != base_rgba8:
        fail_serialized("serialized PNG base-level texels are not byte-identical to the in-memory review image")
        return

    var contexts: Array = contract["comparison"]["contexts"]
    var comparisons := {}
    var negative_total_gt_1lsb := 0
    for raw_context in contexts:
        var context := String(raw_context)

        atlas_texture = texture_from_base_image(base_image)
        var in_memory_path := "res://utility-panel-serialized-%s-in-memory.png" % context
        var in_memory := await capture_variant(context, VARIANT_PHYSICAL, in_memory_path)
        if not in_memory.has("meta") or not in_memory.has("image"):
            fail_serialized("in-memory capture failed: %s" % context)
            return

        atlas_texture = texture_from_base_image(loaded)
        var serialized_path := "res://utility-panel-serialized-%s-reloaded.png" % context
        var serialized := await capture_variant(context, VARIANT_PHYSICAL, serialized_path)
        if not serialized.has("meta") or not serialized.has("image"):
            fail_serialized("serialized capture failed: %s" % context)
            return

        var negative_path := "res://utility-panel-serialized-%s-aspect-blind-negative.png" % context
        var negative := await capture_variant(context, VARIANT_NEGATIVE, negative_path)
        if not negative.has("meta") or not negative.has("image"):
            fail_serialized("serialized negative capture failed: %s" % context)
            return

        var serialization_diff := compare_images(in_memory["image"] as Image, serialized["image"] as Image)
        var negative_diff := compare_images(serialized["image"] as Image, negative["image"] as Image)
        if int(serialization_diff.get("raw_changed_pixels", -1)) != 0:
            fail_serialized("serialized texture changed rendered pixels: %s" % context, {"serialization_diff": serialization_diff})
            return
        if int(negative_diff.get("changed_pixels_gt_1lsb", 0)) <= 200:
            fail_serialized("aspect-blind negative is not visibly distinguishable: %s" % context, {"negative_diff": negative_diff})
            return
        if float(negative_diff.get("max_rgb_channel_delta", 0.0)) <= 0.01:
            fail_serialized("aspect-blind negative lacks material visual response: %s" % context, {"negative_diff": negative_diff})
            return
        negative_total_gt_1lsb += int(negative_diff["changed_pixels_gt_1lsb"])
        comparisons[context] = {
            "in_memory_meta": in_memory["meta"],
            "serialized_meta": serialized["meta"],
            "negative_meta": negative["meta"],
            "in_memory_vs_serialized": serialization_diff,
            "serialized_vs_aspect_blind_negative": negative_diff,
        }

    var result := {
        "schema": "axm.building-utility-panel-serialized-review-texture-runtime/v0.1",
        "state": "PASS_TARGET_HOST_BUILDING_UTILITY_PANEL_SERIALIZED_REVIEW_TEXTURE_CONTINUITY",
        "decision": "PASS_PORTABLE_REVIEW_TEXTURE_BASE_LEVEL_AND_RENDER_CONTINUITY__NO_GLTF_PACKAGING_OR_PRODUCTION_ADOPTION",
        "renderer": "Godot 4.7.2 GL Compatibility / X11 / Mesa llvmpipe proof host",
        "texture": {
            "format": "RGBA8",
            "width": base_image.get_width(),
            "height": base_image.get_height(),
            "base_rgba8_bytes": base_rgba8.size(),
            "base_rgba8_sha256": base_rgba8_sha,
            "reloaded_rgba8_sha256": loaded_rgba8_sha,
            "serialized_png_bytes": serialized_bytes.size(),
            "serialized_png_sha256": serialized_png_sha,
            "base_level_pixel_identity": true,
            "mipmap_policy": review_contract["mipmap_policy"],
        },
        "review_sampling": {
            "active_region_origin_px": atlas["active_region_origin_px"],
            "active_region_px": atlas["active_region_px"],
            "active_uv_bounds": atlas["active_uv_bounds"],
            "texel_density_px_per_m": atlas["texel_density_px_per_m"],
            "checker_period_px": atlas["checker_period_px"],
            "checker_period_m": atlas["checker_period_m"],
        },
        "contexts": comparisons,
        "total_changed_pixels_gt_1lsb_serialized_vs_aspect_blind_negative": negative_total_gt_1lsb,
        "handoff_boundary": contract["handoff_boundary"],
        "truth_boundary": contract["truth_boundary"],
        "promotion_effect": "NONE"
    }
    write_serialized_receipt(result)
    print(JSON.stringify(result, "  "))
    quit(0)
