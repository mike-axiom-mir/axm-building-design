# Building utility-panel production surface successor 001

Status: **MATERIALS REVIEW CANDIDATE / NON-CANON / ENVIRONMENT ADOPTION HELD**

This bounded Materials / LookDev successor answers Art Direction 042's request for one production-intent utility-panel surface while retaining the exact checker as a diagnostic transport control.

## Surface intent

`utility_panel_ochre_production_surface_001` keeps the existing ochre service-panel family and the existing scalar metallic `0.18` / roughness `0.62`. Its only authored texture content is deterministic broad/medium coated-color variation around the established ochre base. It does not add seams, fasteners, damage, decals, wear, labels or geometric facts.

The 512x512 RGBA8 texture is generated from fixed-point value noise with a fixed seed. It is fully opaque, low local contrast and reproducible byte-for-byte. The generator verifies its exact serialized PNG SHA-256 and exact decoded RGBA8 SHA-256.

## Exact current-world review

The workflow reuses Map Environment PR #51 exact head `595df99daf866b5e3dcaa4be87eeb650af637919` and Technical Art head `1434bc4a64faa04db10f47723c37ab7925aaa163`. It does not rewrite either owner lane.

Three held variants are compared in the exact existing current world:

1. scalar ochre control;
2. retained checker diagnostic;
3. this Materials-owned production-surface successor.

The existing `path_eye` and `elevated_oblique` cameras, Building receiver, articulated Object sample 40 / 1.0 s, Nature, Weather source-width presentation, lighting and unrelated world state remain fixed. The successor observer is composed mechanically from the exact Environment material-bound observer donor after verifying its Git blob identity; only the Materials head, texture identity, state/rule text and truth-boundary text are rebound.

## Acceptance boundary

A green workflow proves only that the successor is reproducible, uses the proven current-receiver transport, stays localized to the already-proven utility-panel projection, remains visible in the retained current-world observations and does not silently alter unrelated runtime/world identity.

It does **not** grant final Art Direction preference, independent Visual QA acceptance, Environment adoption, Runtime/device acceptance, production UV policy, arbitrary-renderer equivalence, CANON or production readiness.
