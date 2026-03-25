import os
from datetime import datetime
import sys

import unreal


SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from project_path_utils import get_export_from_blender_dir


SOURCE = get_export_from_blender_dir(__file__)
DESTINATION = "/Game"
SOURCE_EXTENSIONS = {".fbx", ".obj"}
REPORT_FILE_NAME = "StaticMesh_LightmapAudit_LastImport.log"


def normalize_asset_folder(asset_path: str) -> str:
    return asset_path.rstrip("/")


def gather_source_files(source_root: str) -> list[str]:
    mesh_files = []

    for root, _, files in os.walk(source_root):
        for file_name in files:
            extension = os.path.splitext(file_name)[1].lower()
            if extension in SOURCE_EXTENSIONS:
                mesh_files.append(os.path.join(root, file_name))

    return mesh_files


def normalize_asset_name(file_name: str) -> str:
    asset_name = os.path.splitext(file_name)[0]
    name_parts = asset_name.split(".")

    if len(name_parts) >= 2 and all(part == name_parts[0] for part in name_parts[1:]):
        return name_parts[0]

    return asset_name


def build_destination_path(file_path: str, source_root: str, destination_root: str) -> tuple[str, str]:
    relative_file_path = os.path.relpath(file_path, source_root)
    relative_folder = os.path.dirname(relative_file_path)
    destination_path = destination_root

    if relative_folder and relative_folder != ".":
        destination_path = f"{destination_root}/{relative_folder.replace(os.sep, '/')}"

    asset_name = normalize_asset_name(os.path.basename(file_path))
    return destination_path, asset_name


def build_asset_path(destination_path: str, asset_name: str) -> str:
    return f"{destination_path}/{asset_name}"


def build_import_options() -> unreal.FbxImportUI:
    options = unreal.FbxImportUI()
    options.import_mesh = True
    options.import_as_skeletal = False
    options.import_materials = False
    options.import_textures = False
    options.import_animations = False
    options.create_physics_asset = False
    options.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    options.static_mesh_import_data.combine_meshes = False
    options.static_mesh_import_data.generate_lightmap_u_vs = False
    return options


def get_report_file_path() -> str:
    project_dir = unreal.Paths.project_dir()
    log_dir = os.path.join(project_dir, "Saved", "Logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, REPORT_FILE_NAME)


def write_audit_report(lines: list[str]) -> None:
    report_path = get_report_file_path()
    with open(report_path, "w", encoding="utf-8") as report_file:
        report_file.write("\n".join(lines) + "\n")

    unreal.log(f"Wrote lightmap audit report: {report_path}")


def get_audit_sort_key(audit_data: dict[str, object]) -> tuple[int, float, int, str]:
    overlap_percentage = audit_data.get("overlap_percentage")
    overlap_rank = 1 if overlap_percentage is None else 0
    overlap_value = 0.0 if overlap_percentage is None else -float(overlap_percentage)
    issue_rank = 0 if audit_data.get("issues") else 1
    asset_name = str(audit_data.get("asset_name") or "")
    return (overlap_rank, overlap_value, issue_rank, asset_name.casefold())


def build_popup_summary_line(audit_data: dict[str, object]) -> str:
    overlap_percentage = audit_data.get("overlap_percentage")
    overlap_text = "Unknown" if overlap_percentage is None else f"{float(overlap_percentage):.1f}%"
    return (
        f"{audit_data['asset_name']}: Import Generate Lightmap UVs={audit_data['import_generate_lightmap_uvs']}, "
        f"LOD0 Generate Lightmap UVs={audit_data['lod0_generate_lightmap_u_vs']}, "
        f"Overlap={overlap_text}"
    )


def format_enabled_state(value: bool | None) -> str:
    if value is True:
        return "Enabled"
    if value is False:
        return "Disabled"
    return "Unknown"


def make_mesh_element_id(id_type_name: str, index: int):
    id_type = getattr(unreal, id_type_name, None)
    if id_type is None:
        return index

    try:
        return id_type(index)
    except Exception:
        return index


def triangle_area_2d(triangle: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]) -> float:
    (ax, ay), (bx, by), (cx, cy) = triangle
    return abs(((bx - ax) * (cy - ay)) - ((by - ay) * (cx - ax))) * 0.5


def is_point_in_triangle_2d(point_x: float, point_y: float, triangle: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]) -> bool:
    (ax, ay), (bx, by), (cx, cy) = triangle

    denominator = ((by - cy) * (ax - cx)) + ((cx - bx) * (ay - cy))
    if abs(denominator) <= 1e-12:
        return False

    alpha = (((by - cy) * (point_x - cx)) + ((cx - bx) * (point_y - cy))) / denominator
    beta = (((cy - ay) * (point_x - cx)) + ((ax - cx) * (point_y - cy))) / denominator
    gamma = 1.0 - alpha - beta
    epsilon = 1e-9
    return alpha >= -epsilon and beta >= -epsilon and gamma >= -epsilon


def estimate_lightmap_overlap(asset: unreal.StaticMesh, uv_channel_index: int, light_map_resolution: int, uv_channel_count: int | None = None) -> tuple[float | None, bool, str | None]:
    if uv_channel_index < 0:
        return None, False, "Invalid light map coordinate index"

    if uv_channel_count is not None and uv_channel_count >= 0 and uv_channel_index >= uv_channel_count:
        return None, False, f"Light Map Coordinate Index {uv_channel_index} is outside the available UV channel count ({uv_channel_count})"

    try:
        mesh_description = asset.get_static_mesh_description(0)
    except Exception as exc:
        return None, False, f"Could not get mesh description: {exc}"

    if mesh_description is None:
        return None, False, "Mesh description is unavailable"

    try:
        triangle_count = mesh_description.get_triangle_count()
    except Exception as exc:
        return None, False, f"Could not get triangle count: {exc}"

    if triangle_count <= 0:
        return 0.0, False, None

    resolution = light_map_resolution if light_map_resolution and light_map_resolution > 0 else 128
    resolution = max(32, min(int(resolution), 128))

    coverage = [0] * (resolution * resolution)
    has_wrapping_uvs = False
    has_valid_triangles = False

    for triangle_index in range(triangle_count):
        triangle_id = make_mesh_element_id("TriangleID", triangle_index)

        try:
            if hasattr(mesh_description, "is_triangle_valid") and not mesh_description.is_triangle_valid(triangle_id):
                continue
            vertex_instance_ids = mesh_description.get_triangle_vertex_instances(triangle_id)
        except Exception:
            continue

        if len(vertex_instance_ids) != 3:
            continue

        triangle_uvs = []
        for vertex_instance_id in vertex_instance_ids:
            try:
                uv = mesh_description.get_vertex_instance_uv(vertex_instance_id, uv_channel_index)
            except Exception as exc:
                return None, False, f"Could not read UVs from mesh description: {exc}"

            uv_x = float(uv.x)
            uv_y = float(uv.y)
            if uv_x < 0.0 or uv_x > 1.0 or uv_y < 0.0 or uv_y > 1.0:
                has_wrapping_uvs = True
            triangle_uvs.append((uv_x, uv_y))

        triangle = (triangle_uvs[0], triangle_uvs[1], triangle_uvs[2])
        if triangle_area_2d(triangle) <= 1e-12:
            continue

        has_valid_triangles = True
        min_u = max(0.0, min(point[0] for point in triangle))
        max_u = min(1.0, max(point[0] for point in triangle))
        min_v = max(0.0, min(point[1] for point in triangle))
        max_v = min(1.0, max(point[1] for point in triangle))

        if max_u <= 0.0 or min_u >= 1.0 or max_v <= 0.0 or min_v >= 1.0:
            continue

        min_x = max(0, min(int(min_u * resolution), resolution - 1))
        max_x = max(0, min(int(max_u * resolution), resolution - 1))
        min_y = max(0, min(int(min_v * resolution), resolution - 1))
        max_y = max(0, min(int(max_v * resolution), resolution - 1))

        for grid_y in range(min_y, max_y + 1):
            sample_v = (grid_y + 0.5) / resolution
            for grid_x in range(min_x, max_x + 1):
                sample_u = (grid_x + 0.5) / resolution
                if is_point_in_triangle_2d(sample_u, sample_v, triangle):
                    coverage[(grid_y * resolution) + grid_x] += 1

    if not has_valid_triangles:
        return 0.0, has_wrapping_uvs, None

    occupied_samples = sum(1 for sample_count in coverage if sample_count > 0)
    overlapping_samples = sum(1 for sample_count in coverage if sample_count > 1)
    if occupied_samples == 0:
        return 0.0, has_wrapping_uvs, None

    overlap_percentage = round((overlapping_samples / occupied_samples) * 100.0, 1)
    return overlap_percentage, has_wrapping_uvs, None


def audit_static_mesh_lightmap_settings(asset_path: str) -> tuple[bool, list[str], dict[str, object]]:
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if asset is None or not isinstance(asset, unreal.StaticMesh):
        lines = [f"RISK | {asset_path} | Failed to load static mesh for audit"]
        return False, lines, {
            "asset_name": os.path.basename(asset_path),
            "overlap_percentage": None,
            "has_overlap_warning": False,
            "has_wrapping_uvs": False,
            "import_generate_lightmap_uvs": None,
            "lod0_generate_lightmap_uvs": None,
            "lod0_generate_lightmap_u_vs": None,
            "issues": ["Failed to load static mesh for audit"],
        }

    issues = []

    try:
        uv_channel_count = unreal.EditorStaticMeshLibrary.get_num_uv_channels(asset, 0)
    except Exception:
        uv_channel_count = -1
        issues.append("Could not read UV channel count")

    light_map_coordinate_index = asset.get_editor_property("light_map_coordinate_index")
    light_map_resolution = asset.get_editor_property("light_map_resolution")

    import_generate_lightmap_uvs = None
    asset_import_data = asset.get_editor_property("asset_import_data")
    if asset_import_data is not None:
        try:
            import_generate_lightmap_uvs = asset_import_data.get_editor_property("generate_lightmap_u_vs")
        except Exception:
            import_generate_lightmap_uvs = None

    lod0_generate_lightmap_uvs = None
    lod0_src_lightmap_index = None
    lod0_dst_lightmap_index = None
    lod0_min_lightmap_resolution = None
    try:
        build_settings = unreal.EditorStaticMeshLibrary.get_lod_build_settings(asset, 0)
        lod0_generate_lightmap_uvs = build_settings.get_editor_property("generate_lightmap_u_vs")
        lod0_src_lightmap_index = build_settings.get_editor_property("src_lightmap_index")
        lod0_dst_lightmap_index = build_settings.get_editor_property("dst_lightmap_index")
        lod0_min_lightmap_resolution = build_settings.get_editor_property("min_lightmap_resolution")
    except Exception:
        issues.append("Could not read LOD0 build settings")

    if uv_channel_count >= 0 and uv_channel_count < 2:
        issues.append("Mesh has fewer than 2 UV channels")
    if uv_channel_count >= 0 and light_map_coordinate_index >= uv_channel_count:
        issues.append("Light Map Coordinate Index is outside the available UV channel count")
    if light_map_coordinate_index != 1:
        issues.append("Light Map Coordinate Index is not 1")
    if import_generate_lightmap_uvs is True:
        issues.append("Import data still has Generate Lightmap UVs enabled")
    if lod0_generate_lightmap_uvs is True:
        issues.append("LOD0 build settings still have Generate Lightmap UVs enabled")
    if lod0_dst_lightmap_index is not None and lod0_dst_lightmap_index != light_map_coordinate_index:
        issues.append("LOD0 destination lightmap index does not match mesh Light Map Coordinate Index")

    overlap_percentage, has_wrapping_uvs, overlap_error = estimate_lightmap_overlap(
        asset,
        light_map_coordinate_index,
        light_map_resolution,
        uv_channel_count,
    )
    if overlap_error:
        issues.append(overlap_error)
    if has_wrapping_uvs:
        issues.append("Lightmap UVs extend outside the 0-1 range")
    if overlap_percentage is not None and overlap_percentage > 0.0:
        issues.append(f"Lightmap UV overlap detected by import audit ({overlap_percentage:.1f}%)")

    import_generate_state = format_enabled_state(import_generate_lightmap_uvs)
    lod0_generate_state = format_enabled_state(lod0_generate_lightmap_uvs)
    overlap_text = "Unknown" if overlap_percentage is None else f"{overlap_percentage:.1f}%"
    wrapping_text = "Yes" if has_wrapping_uvs else "No"

    summary = (
        f"{asset_path} | UVChannels={uv_channel_count} | LightMapCoordinateIndex={light_map_coordinate_index} "
        f"| LightMapResolution={light_map_resolution} | ImportGenerateLightmapUVs={import_generate_state} "
        f"| LOD0GenerateLightmapUVs={lod0_generate_state} | LOD0SrcLightmapIndex={lod0_src_lightmap_index} "
        f"| LOD0DstLightmapIndex={lod0_dst_lightmap_index} | LOD0MinLightmapResolution={lod0_min_lightmap_resolution} "
        f"| ImportAuditOverlap={overlap_text} | WrappingUVs={wrapping_text}"
    )

    lines = []
    if issues:
        lines.append(f"RISK | {summary} | Issues={'; '.join(issues)}")
    else:
        lines.append(f"OK | {summary}")

    asset_name = asset.get_name() if hasattr(asset, "get_name") else os.path.basename(asset_path)
    if overlap_percentage is not None and overlap_percentage > 0.0:
        lines.append(f"Warning: {asset_name} Object has overlapping UVs.")
        lines.append(f"{asset_name} Lightmap UV are overlapping by {overlap_percentage:.1f}%. Please adjust content - Enable Error Coloring to visualize.")
    if has_wrapping_uvs:
        lines.append(f"Warning: {asset_name} Object has wrapping UVs.")

    return not issues, lines, {
        "asset_name": asset_name,
        "overlap_percentage": overlap_percentage,
        "has_overlap_warning": overlap_percentage is not None and overlap_percentage > 0.0,
        "has_wrapping_uvs": has_wrapping_uvs,
        "import_generate_lightmap_uvs": import_generate_state,
        "lod0_generate_lightmap_u_vs": lod0_generate_state,
        "issues": issues,
    }


def show_import_audit_summary(processed_count: int, risky_asset_count: int, overlap_warning_count: int, report_path: str, popup_lines: list[str]) -> None:
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
        lines.append("No lightmap risks were detected after import.")

    summary = "\n".join(lines)
    unreal.EditorDialog.show_message("Static Mesh Lightmap Audit", summary, unreal.AppMsgType.OK)


def parse_audit_report_lines(audit_lines: list[str]) -> list[str]:
    parsed_issues = []
    for line in audit_lines:
        if "| Issues=" in line:
            parsed_issues.extend([item.strip() for item in line.split("| Issues=", 1)[1].split(";") if item.strip()])
        elif line.startswith("Warning:"):
            parsed_issues.append(line)
        elif line.startswith("RISK |"):
            parsed_issues.append(line)
    return parsed_issues


def configure_static_mesh_lightmap_settings(asset_path: str) -> bool:
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if asset is None or not isinstance(asset, unreal.StaticMesh):
        unreal.log_error(f"Failed to load Static Mesh for lightmap configuration: {asset_path}")
        return False

    asset.modify()
    asset.set_editor_property("light_map_coordinate_index", 1)

    try:
        build_settings = unreal.EditorStaticMeshLibrary.get_lod_build_settings(asset, 0)
        build_settings.set_editor_property("generate_lightmap_u_vs", False)
        build_settings.set_editor_property("src_lightmap_index", 0)
        build_settings.set_editor_property("dst_lightmap_index", 1)
        unreal.EditorStaticMeshLibrary.set_lod_build_settings(asset, 0, build_settings)
    except Exception:
        pass

    asset_import_data = asset.get_editor_property("asset_import_data")
    if asset_import_data is not None:
        try:
            asset_import_data.set_editor_property("generate_lightmap_u_vs", False)
        except Exception:
            pass

    if hasattr(asset, "post_edit_change"):
        asset.post_edit_change()

    unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False)
    return True


def import_mesh_file(file_path: str, destination_path: str, asset_name: str) -> bool:
    unreal.EditorAssetLibrary.make_directory(destination_path)

    task = unreal.AssetImportTask()
    task.filename = file_path
    task.destination_path = destination_path
    task.destination_name = asset_name
    task.automated = True
    task.replace_existing = True
    task.replace_existing_settings = False
    task.save = True
    task.options = build_import_options()

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    if task.imported_object_paths:
        return True

    return unreal.EditorAssetLibrary.does_asset_exist(build_asset_path(destination_path, asset_name))


def snapshot_static_materials(asset_path: str) -> list[unreal.StaticMaterial]:
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if asset is None or not isinstance(asset, unreal.StaticMesh):
        return []

    return list(asset.get_editor_property("static_materials"))


def restore_static_materials(asset_path: str, saved_materials: list[unreal.StaticMaterial]) -> bool:
    if not saved_materials:
        return False

    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if asset is None or not isinstance(asset, unreal.StaticMesh):
        unreal.log_error(f"Failed to load Static Mesh for material restore: {asset_path}")
        return False

    asset.modify()
    asset.set_editor_property("static_materials", saved_materials)

    if hasattr(asset, "set_material"):
        for material_index, saved_material in enumerate(saved_materials):
            material_interface = saved_material.get_editor_property("material_interface")
            if material_interface is not None:
                asset.set_material(material_index, material_interface)

    if hasattr(asset, "post_edit_change"):
        asset.post_edit_change()

    unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False)
    return True


def reimport_existing_mesh(file_path: str, destination_path: str, asset_name: str, asset_path: str) -> bool:
    saved_materials = snapshot_static_materials(asset_path)
    if not import_mesh_file(file_path, destination_path, asset_name):
        return False

    if saved_materials:
        restore_static_materials(asset_path, saved_materials)

    if not configure_static_mesh_lightmap_settings(asset_path):
        return False

    return True


def run_bulk_reimport(source_root: str = SOURCE, destination_root: str = DESTINATION, show_dialog: bool = True) -> dict[str, object]:
    destination_root = normalize_asset_folder(destination_root)
    report_path = get_report_file_path()
    audit_report_lines = [
        f"Lightmap import audit generated at {datetime.now().isoformat(timespec='seconds')}",
        f"Source: {source_root}",
        f"Destination: {destination_root}",
        "Overlap percentages are import-audit estimates computed from the imported mesh's current lightmap UV channel.",
        "",
    ]

    result = {
        "source_root": source_root,
        "destination_root": destination_root,
        "report_path": report_path,
        "processed": 0,
        "imported_new": 0,
        "reimported_existing": 0,
        "failed": 0,
        "risky": 0,
        "overlap_warnings": 0,
        "rows": [],
        "status_lines": [],
    }

    if not os.path.isdir(source_root):
        message = f"Source folder does not exist: {source_root}"
        unreal.log_error(message)
        result["status_lines"] = [message]
        return result

    mesh_files = gather_source_files(source_root)
    if not mesh_files:
        message = f"No mesh files found in {source_root}"
        unreal.log_warning(message)
        result["status_lines"] = [message]
        return result

    risky_asset_count = 0
    overlap_warning_count = 0
    imported_new_count = 0
    reimported_existing_count = 0
    failed_count = 0
    audit_entries: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []

    for file_path in mesh_files:
        destination_path, asset_name = build_destination_path(file_path, source_root, destination_root)
        asset_path = build_asset_path(destination_path, asset_name)
        existed_before_import = unreal.EditorAssetLibrary.does_asset_exist(asset_path)

        operation_succeeded = False
        if existed_before_import:
            operation_succeeded = reimport_existing_mesh(file_path, destination_path, asset_name, asset_path)
            if operation_succeeded:
                reimported_existing_count += 1
                unreal.log(f"Reimported: {file_path} -> {asset_path}")
            else:
                failed_count += 1
                unreal.log_error(f"Failed to reimport: {file_path} -> {asset_path}")
        else:
            operation_succeeded = import_mesh_file(file_path, destination_path, asset_name)
            if operation_succeeded:
                configure_static_mesh_lightmap_settings(asset_path)
                imported_new_count += 1
                unreal.log(f"Imported new asset: {file_path} -> {asset_path}")
            else:
                failed_count += 1
                unreal.log_error(f"Failed to import new asset: {file_path} -> {asset_path}")

        audit_ok = False
        audit_lines: list[str] = []
        audit_data: dict[str, object] = {
            "asset_name": asset_name,
            "overlap_percentage": None,
            "has_overlap_warning": False,
            "has_wrapping_uvs": False,
            "import_generate_lightmap_uvs": "Unknown",
            "lod0_generate_lightmap_u_vs": "Unknown",
            "issues": ["Import or reimport failed"],
        }

        if operation_succeeded:
            audit_ok, audit_lines, audit_data = audit_static_mesh_lightmap_settings(asset_path)
            if audit_data["has_overlap_warning"]:
                overlap_warning_count += 1
            if audit_ok:
                for audit_line in audit_lines:
                    unreal.log(audit_line)
            else:
                risky_asset_count += 1
                for audit_line in audit_lines:
                    unreal.log_warning(audit_line)
            audit_entries.append({"lines": audit_lines, "data": audit_data})
        else:
            risky_asset_count += 1
            audit_lines = [f"RISK | {asset_path} | Import or reimport failed before audit"]
            audit_entries.append({"lines": audit_lines, "data": audit_data})

        row_issues = parse_audit_report_lines(audit_lines)
        if not operation_succeeded and not row_issues:
            row_issues.append("Import or reimport failed before audit")

        rows.append(
            {
                "key": asset_path,
                "asset_name": str(audit_data.get("asset_name") or asset_name),
                "asset_path": asset_path,
                "source_file": file_path,
                "target_path": destination_path,
                "action": "reimport" if existed_before_import else "import",
                "result": "ok" if operation_succeeded and audit_ok else ("risk" if operation_succeeded else "failed"),
                "overlap_percentage": audit_data.get("overlap_percentage"),
                "wrapping_uvs": bool(audit_data.get("has_wrapping_uvs") or False),
                "import_generate_lightmap_uvs": str(audit_data.get("import_generate_lightmap_uvs") or "Unknown"),
                "lod0_generate_lightmap_uvs": str(audit_data.get("lod0_generate_lightmap_u_vs") or "Unknown"),
                "issues": row_issues,
            }
        )

    unreal.EditorAssetLibrary.save_directory(destination_root, only_if_is_dirty=True, recursive=True)
    sorted_audit_entries = sorted(audit_entries, key=lambda entry: get_audit_sort_key(entry["data"]))
    popup_lines = [
        build_popup_summary_line(entry["data"])
        for entry in sorted_audit_entries
        if entry["data"].get("issues") or entry["data"].get("has_overlap_warning")
    ]
    for entry in sorted_audit_entries:
        audit_report_lines.extend(entry["lines"])

    audit_report_lines.append("")
    audit_report_lines.append(
        f"Summary: processed={len(mesh_files)}, risky={risky_asset_count}, failed={failed_count}, imported_new={imported_new_count}, reimported_existing={reimported_existing_count}"
    )
    write_audit_report(audit_report_lines)

    if show_dialog:
        show_import_audit_summary(len(mesh_files), risky_asset_count, overlap_warning_count, report_path, popup_lines)

    status_lines = [
        "Bulk Import/Reimport Static Meshes",
        f"Source folder: {source_root}",
        f"Destination root: {destination_root}",
        f"Processed: {len(mesh_files)}",
        f"Imported new: {imported_new_count}",
        f"Reimported existing: {reimported_existing_count}",
        f"Failed: {failed_count}",
        f"Risky assets: {risky_asset_count}",
        f"Overlap warnings: {overlap_warning_count}",
        f"Report path: {report_path}",
    ]

    unreal.log(f"Bulk reimport complete. Processed {len(mesh_files)} mesh files.")

    result.update(
        {
            "processed": len(mesh_files),
            "imported_new": imported_new_count,
            "reimported_existing": reimported_existing_count,
            "failed": failed_count,
            "risky": risky_asset_count,
            "overlap_warnings": overlap_warning_count,
            "rows": rows,
            "status_lines": status_lines,
        }
    )
    return result


def main() -> None:
    run_bulk_reimport(show_dialog=True)


if __name__ == "__main__":
    main()