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
  exact implementation head and file digests.
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

These local results are structural and source-provenance evidence. They do not grant visual,
art-direction, environment, target-device runtime, or final Materials acceptance. The remote
Godot evidence below is the separate target-host rebind; human acceptance remains separate.

## First remote exact-head rebind

Remote integration head `e7dae5cd090d379d9f17bbd1db4d043eb26ce341` passed all 14 triggered
workflows. The current integrated workflow run `35477584805` passed the 190-test exact-donor gate
on Python 3.11 and 3.13. The current-source workflow run `35477584990` rebuilt and rendered the
same 19 components with Godot 4.7.2 in front, east, and three-quarter contexts.

Artifact `10594657498`, digest
`923fa340d93287a22e5194f0c827a322f61b972c2398dc2240c66861a995d108`, retains all six A/B PNGs,
the material packet, structural receipt, and runtime receipt. The measured changed-pixel fractions
were 0.3348102564 front, 0.1337401709 east, and 0.1474256410 three-quarter. The artifact shows a
stable shared silhouette and receiver placement with visibly distinct candidate material
assignments. The east service panel is dark under the proof lighting; no final art-direction
acceptance is inferred.

This exact evidence promotes the bounded structural packet adapter to `AI_CALLABLE`. The promotion
changes no source geometry or material values. Human UI, intent compilation, environment adoption,
target-device runtime, and final Materials acceptance remain open, and the promoted exact head must
rerun the same gates.

## Rollback

- accepted pre-Materials Building main: `adae0a212a0790a433b388e2bb8aba5f5856d604`;
- retained Materials head: `eb31efc1639f58f2797bac44ce7f1bad774841ef`;
- historical Materials source identity: `57f66b1245812f0c3d402232a046b86c0b5c72d8`.

No history or failed evidence was deleted.
