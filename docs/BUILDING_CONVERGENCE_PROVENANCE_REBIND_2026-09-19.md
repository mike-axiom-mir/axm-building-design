# Building convergence provenance rebind — 2026-09-19

## Trigger

The 3D Studio convergence pass integrated Building source, utility-panel clearance/chart,
topology/normal-policy ancestry, and Building-local Procedural work into main commit
`fcf3c2a0d3f2f7ee973fb0d7f090f65abf9b8c4e`.

The first full-suite run on that combined main executed 145 tests and exposed one failure plus
five errors. The isolated PR workflows had been green, but three consumers still pinned the
pre-clearance source representation. This record preserves that integration failure rather
than treating the earlier per-PR PASS results as combined-main evidence.

## Invalidated identities

1. The Procedural service-surface receiver family pinned Hard Surface PR #15 and service-surface
   contract blob `14037a0fb939104ea319c9ac96fbe9fdaa949a18`. The accepted clearance successor is Hard
   Surface PR #17 head `fbfa3b47048755b45dac91451171d5511c8d4f47`, whose exact service-surface contract blob is
   `8b4484d4ccbd500e58910a2835d8780112489919`.
2. Geometry's indexed planar-role candidate retained the same 604 vertices, 336 triangles, and
   312-group hard-normal quotient metrics, but the panel-center shift changed exact positions.
   The candidate digest changed from
   `f6a831058de66901fd42704b1d8c1cf187b13a0919ae3719c03c4369f107e6c0` to
   `9b1a13be7287f56ed5a23a4880a12544befcf458fe72b67847c8f319d65c0980`; the quotient digest
   changed from `7d9e0babf605e31ecb3e4edc92d06bd5460cf52a27f02ccbf32bbae44464688f` to
   `3ab469a8033f139370f278b8b4940512594262ea5291991ff086952a5959989e`.
3. The compact-v2 shell kept its 1,004 vertices, 2,052 triangles, source-owner coverage, closed
   topology, bounds, volume, and area gates, but exact payload identity changed from
   `d51d853ce95216ad66f6ce88cf5bca6aecfa19e22e5e8ce4045cf481b719936a` to
   `904ca8b5dc4a96677ce9f6ea4910e04f8aa4f100fc567a083cbe83d47516b16b`.

Equal structural counts were not used as provenance substitution. Each affected consumer now
records `fcf3c2a0d3f2f7ee973fb0d7f090f65abf9b8c4e` as the exact combined source-rebind head while
retaining the original specialist owner PR/head separately.

## Repair boundary

The repair changes only exact owner/rebind heads, Git-blob identities, derived payload digests,
and fail-closed regression assertions. It does not alter Building source geometry, receiver
placement, materials, UV intent, normal policy, Procedural authority, Map adoption, runtime
policy, visual acceptance, UC, or Profession Fabric.

## Local verification

On Python 3.12.14, the repaired combined branch completed:

- `python -m compileall tools tests` — PASS;
- `python -m unittest discover -s tests -v` — 160 PASS, 2 dependency-gated skips;
- `git diff --check` — PASS.

The two skips require exact external donor checkouts and remain workflow gates; this local result
does not replace them. GitHub exact-head workflow state is recorded separately on the integration
PR.

## Rollback

- pre-repair combined Building main: `fcf3c2a0d3f2f7ee973fb0d7f090f65abf9b8c4e`;
- source/receiver integration merge points: `a984c42e4a7e812ffad8bb5e10859556d1bf3ccc`,
  `7bc5bdfd77d600b8202ea008f7865481480f8d0a`, `046c2a1ce15242cbf5463355a23944df46506e4c`,
  and `fd9424ac71b1ad95ed254344f185f537fca2fced`;
- Building-local Procedural convergence merge: `fcf3c2a0d3f2f7ee973fb0d7f090f65abf9b8c4e`.

No history or failed evidence was deleted.
