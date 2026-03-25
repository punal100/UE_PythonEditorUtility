import os
import sys

import unreal


SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from project_path_utils import get_export_from_ue_dir


SOURCE = "/Game"
DESTINATION = get_export_from_ue_dir(__file__)
EXPORT_EXTENSION = ".fbx"


def normalize_asset_folder(asset_path: str) -> str:
    return asset_path.rstrip("/")


def get_static_mesh_assets(source_folder: str) -> list[str]:
    asset_paths = unreal.EditorAssetLibrary.list_assets(source_folder, recursive=True, include_folder=False)
    static_mesh_paths = []

    for asset_path in asset_paths:
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
        if isinstance(asset, unreal.StaticMesh):
            static_mesh_paths.append(asset_path)

    return static_mesh_paths


def build_export_path(asset_path: str, source_folder: str, destination_root: str) -> str:
    relative_asset_path = asset_path.removeprefix(source_folder).lstrip("/")
    relative_folder = os.path.dirname(relative_asset_path.replace("/", os.sep))
    asset_name = os.path.basename(asset_path)

    export_folder = os.path.join(destination_root, relative_folder)
    os.makedirs(export_folder, exist_ok=True)

    return os.path.join(export_folder, f"{asset_name}{EXPORT_EXTENSION}")


def export_static_mesh(asset_path: str, export_path: str) -> bool:
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)

    export_task = unreal.AssetExportTask()
    export_task.object = asset
    export_task.filename = export_path
    export_task.automated = True
    export_task.prompt = False
    export_task.replace_identical = True
    export_task.exporter = unreal.StaticMeshExporterFBX()

    return unreal.Exporter.run_asset_export_task(export_task)


def run_bulk_export(source_folder: str = SOURCE, destination_root: str = DESTINATION) -> dict[str, object]:
    normalized_source_folder = normalize_asset_folder(source_folder)
    static_mesh_paths = get_static_mesh_assets(normalized_source_folder)

    result = {
        "source_folder": normalized_source_folder,
        "destination_root": destination_root,
        "processed": 0,
        "exported": 0,
        "failed": 0,
        "rows": [],
        "status_lines": [],
    }

    if not static_mesh_paths:
        warning = f"No Static Mesh assets found in {normalized_source_folder}"
        unreal.log_warning(warning)
        result["status_lines"] = [warning]
        return result

    status_lines = [
        "Bulk Export Static Meshes",
        f"Source folder: {normalized_source_folder}",
        f"Destination root: {destination_root}",
        f"Discovered static meshes: {len(static_mesh_paths)}",
    ]

    rows: list[dict[str, object]] = []
    exported_count = 0
    failed_count = 0

    for asset_path in static_mesh_paths:
        export_path = build_export_path(asset_path, normalized_source_folder, destination_root)
        success = export_static_mesh(asset_path, export_path)
        asset_name = os.path.basename(asset_path)
        row = {
            "key": asset_path,
            "asset_name": asset_name,
            "asset_path": asset_path,
            "source_file": "",
            "target_path": export_path,
            "action": "export",
            "result": "exported" if success else "failed",
            "overlap_percentage": None,
            "wrapping_uvs": False,
            "issues": [] if success else ["Failed to export static mesh asset"],
        }
        rows.append(row)

        if success:
            exported_count += 1
            unreal.log(f"Exported: {asset_path} -> {export_path}")
        else:
            failed_count += 1
            unreal.log_error(f"Failed to export: {asset_path}")

    status_lines.append(f"Exported: {exported_count}")
    status_lines.append(f"Failed: {failed_count}")
    status_lines.append(f"Processed: {len(static_mesh_paths)}")
    status_lines.append("Bulk export complete.")

    result.update(
        {
            "processed": len(static_mesh_paths),
            "exported": exported_count,
            "failed": failed_count,
            "rows": rows,
            "status_lines": status_lines,
        }
    )
    return result


def main() -> None:
    result = run_bulk_export()
    if result["processed"] == 0:
        return

    unreal.log(
        f"Bulk export complete. Exported {result['exported']} of {result['processed']} Static Mesh assets."
    )


if __name__ == "__main__":
    main()