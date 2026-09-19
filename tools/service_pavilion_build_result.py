#!/usr/bin/env python3
"""Versioned named interface over the source-owned service pavilion builder.

The historical ``build_service_pavilion.build()`` tuple remains untouched for
reproducibility. New consumers should bind fields by name through this module so
additive producer evolution does not force them to know tuple length/indexes.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "tools" / "build_service_pavilion.py"
SPEC = importlib.util.spec_from_file_location("build_service_pavilion", BUILDER_PATH)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

BUILD_RESULT_SCHEMA = "axm.building-build-result/v0.1"
HISTORICAL_PREFIX_FIELDS = (
    "pavilion",
    "panel",
    "receiver_fits",
    "obj_lines",
    "bounds_min",
    "bounds_max",
    "readable_path_gap_m",
    "negative_controls",
)
CURRENT_REQUIRED_FIELDS = HISTORICAL_PREFIX_FIELDS + ("topology_summary",)


def from_legacy_output(output: Sequence[object]) -> dict:
    """Map the stable source-owned prefix into a versioned named result.

    The current v0.1 contract requires the source-owned topology summary at the
    ninth position, but intentionally ignores any later opaque tuple extensions.
    That keeps old tuple evidence reproducible while preventing new consumers
    from depending on future tuple arity.
    """
    if len(output) < len(CURRENT_REQUIRED_FIELDS):
        raise ValueError(
            "Building build-result v0.1 requires the historical eight-field "
            "prefix plus source-owned topology_summary"
        )

    result = {
        "schema": BUILD_RESULT_SCHEMA,
        "pavilion": output[0],
        "panel": output[1],
        "receiver_fits": output[2],
        "obj_lines": output[3],
        "bounds_min": output[4],
        "bounds_max": output[5],
        "readable_path_gap_m": output[6],
        "negative_controls": output[7],
        "topology_summary": output[8],
        "legacy_output_count_observed": len(output),
        "opaque_trailing_extension_count": max(0, len(output) - len(CURRENT_REQUIRED_FIELDS)),
    }
    require_fields(result, CURRENT_REQUIRED_FIELDS)
    return result


def build_named() -> dict:
    """Build the exact current source and expose its result by stable names."""
    return from_legacy_output(builder.build())


def require_fields(result: Mapping[str, object], fields: Iterable[str]) -> Mapping[str, object]:
    """Fail closed if a consumer's declared named dependency is unavailable."""
    if result.get("schema") != BUILD_RESULT_SCHEMA:
        raise ValueError(f"unsupported Building build-result schema: {result.get('schema')!r}")
    missing = [field for field in fields if field not in result]
    if missing:
        raise ValueError("missing required Building build-result fields: " + ", ".join(missing))
    return result
