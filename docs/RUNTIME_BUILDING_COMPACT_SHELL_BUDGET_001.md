# Runtime Building compact-shell budget 001

## Scope

This Runtime lane is stacked exactly on Hard-Surface PR #9 head `35d0ba62d7e534b3cd00ac69e99386843ffa3f2e`.

It does **not** adopt the compact shell. It characterizes the exact source-owned reference receiving representation (`1420v / 2884t`) against the exact source-owned compact-v2 receiving option (`1004v / 2052t`) under one deliberately bounded Runtime render-domain conversion.

The conversion keeps one neutral surface and indexes identical **position + explicit face-normal** tuples only. Different hard-edge normals remain different render vertices. No UV, tangent, material-role, skin, morph, custom-channel, collision, semantic-source, or Environment equivalence is inferred.

## Measurement contract

The dedicated workflow must:

1. rebuild the exact reference and compact-v2 meshes from the inherited Building tools;
2. measure logical geometry and the explicit hard-edge render-domain storage before rendering;
3. run both representations in separate pinned Godot 4.7.2 GL Compatibility processes;
4. compare draw calls, objects, primitives, observed buffer/texture memory, and two fixed-view PNGs;
5. fail if the compact candidate does not reduce render-domain storage or proof-host primitive count, or if submission/object count changes;
6. preserve any visual delta as an Art/Visual-QA tradeoff instead of silently accepting it;
7. exercise one deliberate negative control against the measured compact reduction.

A green workflow may establish only a bounded Runtime characterization. It does not transfer Materials, Art Direction, Visual QA, Technical Art, Environment, collision, gameplay, CANON, or production acceptance across receiving identities.

The workflow binds its payload and receipts to the **actual checked-out Runtime commit** at execution time; this document intentionally does not freeze a guessed future Runtime head.

## Expected decision boundary

If the exact-head workflow is green, the intended scoped state is:

`PASS_BUILDING_COMPACT_SHELL_RUNTIME_REPRESENTATION_COST_CHARACTERIZED__HOLD_VISUAL_AND_RECEIVER_ADOPTION`

No PASS is pre-claimed by this document. Exact-head Actions evidence is the gate.

## AXM roots

Truth before story; Agency / non-domination; Continuity; Wisdom before speed remain the merge gate.
