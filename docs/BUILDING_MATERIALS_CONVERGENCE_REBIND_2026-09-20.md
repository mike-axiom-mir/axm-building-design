# Building Materials convergence rebind — 2026-09-20

## Purpose

This convergence step combines the retained Building Materials lineage at
`eb31efc1639f58f2797bac44ce7f1bad774841ef` with accepted Building main at
`adae0a212a0790a433b388e2bb8aba5f5856d604` without replacing either history.
The merge keeps the accepted current Building source files and adds the Materials lookdev,
proof hosts, tests, and retained evidence.

## Observed integration defect

The historical Materials workflow rebuilt against source head
`57f66b1245812f0c3d402232a046b86c0b5c72d8`. Its evidence remains valid for that historical
source, but it is not current-source evidence. Before the bounded AI adapter was added, the
combined suite contained 186 tests with the exact Building and Sticker Fabric donors, while the
integrated workflow still expected 173.
That stale count would reject the compatible merged lineage.

## Repair

- The Materials rebind workflow now requires both exact parent lineages as ancestors of the
  tested head.
- It rebuilds the material payload from the checked-out integration head and requires the
  accepted current utility-panel source blob.
- It reruns the Godot A/B proof host in the three retained views against that newly bound source.
- The integrated workflow now runs all 190 tests with both exact donors, rebuilds the current
  receiver chain, and emits a current-head material structural receipt.
- A bounded JSON request/result adapter exposes only the already-existing material packet build.
  It requires the requested source head to equal the actual clean source checkout and records the
  exact implementation head and file digests. Its manifest remains `HOLD` until the remote
  current-source workflows pass.
- Historical Materials artifacts, failed inherited workflows, and the original PR remain
  recoverable; none are rewritten as current evidence.

## Fresh local evidence before remote review

- 186 pre-adapter tests passed with exact Building donor
  `fbfa3b47048755b45dac91451171d5511c8d4f47` and exact Sticker Fabric donor
  `3aa93b0132eea9becefb20c716c6ec1a023ad28b`; zero tests were skipped.
- The current-head material build returned
  `PASS_SOURCE_BOUND_BUILDING_SURFACE_PAYLOAD` for 19 components.
- The merged source retained 228 outward triangles, zero inward triangles, the front receiver
  center `[-2.45, -1.1, 1.65]`, the east receiver center `[3.9, 0.1, 1.65]`, and 0.02 m physical
  panel-body clearance.

These are structural and source-provenance results. They do not grant visual, art-direction,
environment, target-device runtime, or final Materials acceptance. The remote Godot render is
the next visual rebind gate; human acceptance remains separate.

## Rollback

- accepted pre-Materials Building main: `adae0a212a0790a433b388e2bb8aba5f5856d604`;
- retained Materials head: `eb31efc1639f58f2797bac44ce7f1bad774841ef`;
- historical Materials source identity: `57f66b1245812f0c3d402232a046b86c0b5c72d8`.

No history or failed evidence was deleted.
