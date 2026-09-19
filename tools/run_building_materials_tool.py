from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from build_building_material_lookdev_evidence import build_payload


ROOT = Path(__file__).resolve().parents[1]
REQUEST_SCHEMA = "axm.building-materials-tool-request/v0.1"
RESULT_SCHEMA = "axm.building-materials-tool-result/v0.1"
TOOL_ID = "axm.building.materials.packet"
EXPECTED_KEYS = {
    "schema",
    "source_root",
    "source_head",
    "material_profile",
    "output_directory",
    "replace_existing",
}
REQUIRED_KEYS = EXPECTED_KEYS - {"replace_existing"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def git(source_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(source_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def validate_request(request: object) -> dict:
    if not isinstance(request, dict):
        raise AssertionError("request must be a JSON object")
    missing = sorted(REQUIRED_KEYS - set(request))
    extra = sorted(set(request) - EXPECTED_KEYS)
    if missing or extra:
        raise AssertionError(f"request keys mismatch missing={missing} extra={extra}")
    if request["schema"] != REQUEST_SCHEMA:
        raise AssertionError("request schema mismatch")
    for key in ("source_root", "source_head", "material_profile", "output_directory"):
        if not isinstance(request[key], str) or not request[key]:
            raise AssertionError(f"{key} must be a non-empty string")
    source_head = request["source_head"]
    if len(source_head) != 40 or any(character not in "0123456789abcdef" for character in source_head):
        raise AssertionError("source_head must be a lowercase 40-character Git identity")
    replace_existing = request.get("replace_existing", False)
    if not isinstance(replace_existing, bool):
        raise AssertionError("replace_existing must be a boolean")
    normalized = dict(request)
    normalized["replace_existing"] = replace_existing
    return normalized


def resolve_tracked_path(source_root: Path, relative_value: str, label: str) -> Path:
    relative = Path(relative_value)
    if relative.is_absolute():
        raise AssertionError(f"{label} must be relative to source_root")
    resolved = (source_root / relative).resolve()
    try:
        resolved.relative_to(source_root)
    except ValueError as exc:
        raise AssertionError(f"{label} escapes source_root") from exc
    if not resolved.is_file():
        raise AssertionError(f"{label} does not exist: {relative_value}")
    git(source_root, "ls-files", "--error-unmatch", relative.as_posix())
    return resolved


def run_request(request: object) -> dict:
    normalized = validate_request(request)
    source_root = Path(normalized["source_root"]).resolve()
    if not source_root.is_dir():
        raise AssertionError("source_root must be an existing directory")
    if source_root != ROOT.resolve():
        raise AssertionError("source_root must be the checkout that owns this Building tool")

    actual_head = git(source_root, "rev-parse", "HEAD")
    if actual_head != normalized["source_head"]:
        raise AssertionError(
            f"source_head mismatch requested={normalized['source_head']} actual={actual_head}"
        )
    if git(source_root, "status", "--porcelain", "--untracked-files=no"):
        raise AssertionError("tracked source checkout is dirty")

    pavilion_path = resolve_tracked_path(source_root, "assets/service_pavilion_001.json", "pavilion")
    panel_path = resolve_tracked_path(source_root, "assets/utility_access_panel_001.json", "panel")
    profile_path = resolve_tracked_path(source_root, normalized["material_profile"], "material_profile")
    output_directory = Path(normalized["output_directory"]).resolve()
    payload_path = output_directory / "building_material_payload.json"
    receipt_path = output_directory / "build_receipt.json"
    tool_result_path = output_directory / "tool_result.json"
    if not normalized["replace_existing"]:
        existing = [path.name for path in (payload_path, receipt_path, tool_result_path) if path.exists()]
        if existing:
            raise FileExistsError(f"refusing to replace existing tool outputs: {sorted(existing)}")

    payload, receipt = build_payload(
        pavilion_path,
        panel_path,
        profile_path,
        source_root=source_root,
        source_head=actual_head,
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    implementation_path = Path(__file__).resolve()
    builder_path = ROOT / "tools" / "build_building_material_lookdev_evidence.py"
    manifest_path = ROOT / "tooling" / "building-materials-packet.manifest.json"
    result = {
        "schema": RESULT_SCHEMA,
        "result": "PASS_BUILDING_MATERIALS_PACKET",
        "tool_id": TOOL_ID,
        "implementation_head": actual_head,
        "implementation_sha256": sha256(implementation_path),
        "builder_sha256": sha256(builder_path),
        "manifest_sha256": sha256(manifest_path),
        "request_sha256": canonical_digest(normalized),
        "source_head": actual_head,
        "evidence_scopes": ["structural"],
        "outputs": {
            "payload": payload_path.name,
            "payload_sha256": sha256(payload_path),
            "receipt": receipt_path.name,
            "receipt_sha256": sha256(receipt_path),
        },
        "open_gates": [
            "visual acceptance",
            "art-direction acceptance",
            "environment adoption",
            "target-device runtime acceptance",
        ],
        "receipt": receipt,
    }
    tool_result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    args = parser.parse_args()
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    print(json.dumps(run_request(request), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
