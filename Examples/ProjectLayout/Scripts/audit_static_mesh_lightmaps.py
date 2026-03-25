import importlib.util
import os
import sys
from datetime import datetime

import unreal


SCRIPT_DIR = os.path.dirname(__file__)
REIMPORT_SCRIPT_PATH = os.path.join(SCRIPT_DIR, "bulk_reimport_static_meshes.py")
ASSET_ROOT = "/Game"
REPORT_FILE_NAME = "StaticMesh_LightmapAudit_ExistingAssets.log"


def load_reimport_module():
    spec = importlib.util.spec_from_file_location("bulk_reimport_static_meshes_runtime", REIMPORT_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def list_static_mesh_asset_paths(asset_root: str) -> list[str]:
    asset_paths = unreal.EditorAssetLibrary.list_assets(asset_root, recursive=True, include_folder=False)
    static_mesh_paths = []

    for asset_path in asset_paths:
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
        if isinstance(asset, unreal.StaticMesh):
            static_mesh_paths.append(asset_path)

    return sorted(static_mesh_paths, key=str.casefold)


def show_asset_audit_summary(processed_count: int, risky_asset_count: int, overlap_warning_count: int, report_path: str, popup_lines: list[str]) -> None:
    lines = [
        f"Processed meshes: {processed_count}",
        f"Risky meshes: {risky_asset_count}",
        f"Meshes with overlap warnings: {overlap_warning_count}",
        f"Summary log: {report_path}",
        "",
    ]

    if popup_lines:
        lines.extend(popup_lines[:18])
        if len(popup_lines) > 18:
            lines.append("...")
            lines.append("See the summary log for the full report.")
    else:
        lines.append("No lightmap risks were detected.")

    summary = "\n".join(lines)
    unreal.EditorDialog.show_message("Static Mesh Lightmap Audit", summary, unreal.AppMsgType.OK)


def main() -> None:
    reimport_module = load_reimport_module()
    reimport_module.REPORT_FILE_NAME = REPORT_FILE_NAME

    asset_paths = list_static_mesh_asset_paths(ASSET_ROOT)
    if not asset_paths:
        unreal.EditorDialog.show_message(
            "Static Mesh Lightmap Audit",
            f"No static meshes found under {ASSET_ROOT}",
            unreal.AppMsgType.OK,
        )
        return

    report_path = reimport_module.get_report_file_path()
    report_lines = [
        f"Static mesh audit generated at {datetime.now().isoformat(timespec='seconds')}",
        f"Asset root: {ASSET_ROOT}",
        "Overlap percentages are import-audit estimates computed from each mesh's current lightmap UV channel.",
        "",
    ]

    risky_asset_count = 0
    overlap_warning_count = 0
    audit_entries = []

    for asset_path in asset_paths:
        audit_ok, audit_lines, audit_data = reimport_module.audit_static_mesh_lightmap_settings(asset_path)
        audit_entries.append({
            "lines": audit_lines,
            "data": audit_data,
        })

        if audit_data["has_overlap_warning"]:
            overlap_warning_count += 1

        if audit_ok:
            for audit_line in audit_lines:
                unreal.log(audit_line)
        else:
            risky_asset_count += 1
            for audit_line in audit_lines:
                unreal.log_warning(audit_line)

    sorted_audit_entries = sorted(audit_entries, key=lambda entry: reimport_module.get_audit_sort_key(entry["data"]))
    popup_lines = [
        reimport_module.build_popup_summary_line(entry["data"])
        for entry in sorted_audit_entries
        if entry["data"].get("issues") or entry["data"].get("has_overlap_warning")
    ]

    for entry in sorted_audit_entries:
        report_lines.extend(entry["lines"])

    report_lines.append("")
    report_lines.append(f"Summary: processed={len(asset_paths)}, risky={risky_asset_count}")
    reimport_module.write_audit_report(report_lines)
    show_asset_audit_summary(len(asset_paths), risky_asset_count, overlap_warning_count, report_path, popup_lines)


if __name__ == "__main__":
    main()