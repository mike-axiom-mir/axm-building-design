#!/usr/bin/env python3
"""Compatibility entrypoint for the repaired boundary-shell Materials evidence builder.

The initial implementation used strict serialized float equality for measured donor/
candidate surface area and correctly failed on ~1e-12 representation noise. The v2
builder keeps the same exact source, material, topology and ownership gates while using
the Geometry lane's existing 1e-9 tolerance for measured float invariants only.
"""
from build_building_material_boundary_shell_compaction_evidence_v2 import main

if __name__ == "__main__":
    main()
