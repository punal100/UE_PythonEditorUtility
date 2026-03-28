import os

from project_path_utils import get_export_from_blender_dir, get_export_from_ue_dir


SOURCE_DIR = get_export_from_ue_dir(__file__)
DESTINATION_DIR = get_export_from_blender_dir(__file__)
DEFAULT_BLENDER_ENV_VAR = "BLENDER_EXECUTABLE"
DEFAULT_ISLAND_MARGIN = 0.05
DEFAULT_MERGE_DISTANCE = 0.0001
DEFAULT_IGNORE_COLLISION = True
DEFAULT_MERGE_BY_DISTANCE = True
DEFAULT_APPLY_SCALE = True
DEFAULT_MARK_ACTIVE_FOR_EXPORT = True
DEFAULT_EXPORT_PRESET = "UE_Export"
DEFAULT_EXPORT_PRESET_CHOICE = "__AUTO__"


def canonicalize_blender_executable_path(candidate_path: str) -> str:
    normalized_path = os.path.abspath(os.path.expanduser(candidate_path or "")) if candidate_path else ""
    base_name = os.path.basename(normalized_path).lower()
    if base_name not in {"blender-launcher.exe", "blender-launcher"}:
        return normalized_path

    sibling_candidates = (
        os.path.join(os.path.dirname(normalized_path), "blender.exe"),
        os.path.join(os.path.dirname(normalized_path), "blender"),
    )
    for sibling_path in sibling_candidates:
        if os.path.isfile(sibling_path):
            return sibling_path
    return normalized_path


def _normalize_folder(value: str, fallback: str) -> str:
    candidate = str(value or fallback or "").strip()
    if not candidate:
        return ""
    return os.path.abspath(os.path.normpath(os.path.expanduser(candidate)))


def _normalize_file(value: str, fallback: str) -> str:
    candidate = str(value or fallback or "").strip()
    if not candidate:
        return ""
    return canonicalize_blender_executable_path(candidate)


def _normalize_export_preset_choice(value: str) -> str:
    candidate = str(value or DEFAULT_EXPORT_PRESET_CHOICE).strip()
    return candidate or DEFAULT_EXPORT_PRESET_CHOICE


def _get_export_preset_display_text(export_preset_choice: str) -> str:
    normalized = str(export_preset_choice or "").strip().lower()
    if normalized in {"", "auto", "auto / none", "none", "default", "__auto__"}:
        return "Auto / None"
    return str(export_preset_choice).strip()


def get_default_settings() -> dict:
    return {
        "source_dir": SOURCE_DIR,
        "destination_dir": DESTINATION_DIR,
        "blender_executable": _normalize_file(os.environ.get(DEFAULT_BLENDER_ENV_VAR, ""), ""),
        "island_margin": DEFAULT_ISLAND_MARGIN,
        "merge_distance": DEFAULT_MERGE_DISTANCE,
        "merge_by_distance": DEFAULT_MERGE_BY_DISTANCE,
        "ignore_collision": DEFAULT_IGNORE_COLLISION,
        "apply_scale": DEFAULT_APPLY_SCALE,
        "mark_active_for_export": DEFAULT_MARK_ACTIVE_FOR_EXPORT,
        "default_export_preset": DEFAULT_EXPORT_PRESET,
        "default_export_preset_choice": DEFAULT_EXPORT_PRESET_CHOICE,
        "available_export_presets": [DEFAULT_EXPORT_PRESET],
    }


def discover_export_presets(blender_executable: str = "") -> dict:
    resolved_blender_path = _normalize_file(blender_executable, os.environ.get(DEFAULT_BLENDER_ENV_VAR, ""))
    if not resolved_blender_path:
        resolved_blender_path = "blender.exe"
    return {
        "resolved_blender_path": resolved_blender_path,
        "preset_names": [DEFAULT_EXPORT_PRESET],
        "default_export_preset": DEFAULT_EXPORT_PRESET,
        "default_export_preset_choice": DEFAULT_EXPORT_PRESET_CHOICE,
    }


def build_headless_command(source_dir, destination_dir, blender_executable, island_margin, merge_distance, merge_by_distance, ignore_collision, apply_scale, mark_active_for_export, export_preset_choice):
    resolved_blender = discover_export_presets(blender_executable).get("resolved_blender_path") or "blender.exe"
    command = [
        resolved_blender,
        "--background",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "--python",
        os.path.abspath(__file__),
        "--",
        "--headless",
        "--source-dir",
        _normalize_folder(source_dir, SOURCE_DIR),
        "--destination-dir",
        _normalize_folder(destination_dir, DESTINATION_DIR),
        "--island-margin",
        str(island_margin),
        "--merge-distance",
        str(merge_distance),
        "--export-preset-choice",
        _normalize_export_preset_choice(export_preset_choice),
    ]
    if not merge_by_distance:
        command.append("--disable-merge-by-distance")
    if not ignore_collision:
        command.append("--include-collision")
    if not apply_scale:
        command.append("--disable-apply-scale")
    if not mark_active_for_export:
        command.append("--disable-mark-active")
    return command


def build_preview(source_dir, destination_dir, blender_executable, island_margin, merge_distance, merge_by_distance, ignore_collision, apply_scale, mark_active_for_export, export_preset_choice, available_export_presets, preset_source_status):
    normalized_source = _normalize_folder(source_dir, SOURCE_DIR)
    normalized_destination = _normalize_folder(destination_dir, DESTINATION_DIR)
    normalized_blender = _normalize_file(blender_executable, os.environ.get(DEFAULT_BLENDER_ENV_VAR, ""))
    presets = available_export_presets or [DEFAULT_EXPORT_PRESET]
    status_lines = [
        "Blender UV Fixer Pipeline",
        f"Source folder: {normalized_source}",
        f"Destination folder: {normalized_destination}",
        f"Blender executable: {normalized_blender or 'Use BLENDER_EXECUTABLE or system PATH'}",
        f"Island margin: {island_margin}",
        f"Merge by distance: {bool(merge_by_distance)} | Merge distance: {merge_distance}",
        f"Ignore collision: {bool(ignore_collision)} | Apply scale: {bool(apply_scale)}",
        f"Mark UV active for export: {bool(mark_active_for_export)} | Operator preset: {_get_export_preset_display_text(export_preset_choice)}",
        str(preset_source_status or f"Loaded {len(presets)} example operator preset(s) from Blender: {normalized_blender or 'blender.exe'}"),
        f"Available operator presets ({len(presets)}): {', '.join(presets)}",
        "Run the example pipeline to simulate the external Blender contract used by the live project.",
    ]
    detail_lines = [
        f"Source folder: {normalized_source}",
        f"Destination folder: {normalized_destination}",
        f"Blender executable override: {normalized_blender or 'None'}",
        f"Operator preset choice: {_get_export_preset_display_text(export_preset_choice)}",
        str(preset_source_status or f"Loaded {len(presets)} example operator preset(s) from Blender: {normalized_blender or 'blender.exe'}"),
        f"Available operator presets ({len(presets)}): {', '.join(presets)}",
        f"Example command: {' '.join(build_headless_command(source_dir, destination_dir, blender_executable, island_margin, merge_distance, merge_by_distance, ignore_collision, apply_scale, mark_active_for_export, export_preset_choice))}",
        "",
        "This example stays lightweight. It mirrors the live project's preset-aware state contract and external Blender workflow surface without embedding the full production batch implementation.",
    ]
    return {
        "progress_text": "Idle",
        "progress_percent": 0.0,
        "status_text": "\n".join(status_lines),
        "detail_text": "\n".join(detail_lines),
    }


def run_pipeline(source_dir, destination_dir, blender_executable, island_margin, merge_distance, merge_by_distance, ignore_collision, apply_scale, mark_active_for_export, export_preset_choice, available_export_presets, preset_source_status):
    payload = build_preview(
        source_dir,
        destination_dir,
        blender_executable,
        island_margin,
        merge_distance,
        merge_by_distance,
        ignore_collision,
        apply_scale,
        mark_active_for_export,
        export_preset_choice,
        available_export_presets,
        preset_source_status,
    )
    normalized_destination = _normalize_folder(destination_dir, DESTINATION_DIR)
    example_outputs = [
        "Architecture/SM_WallPanel.fbx",
        "Architecture/SM_WindowFrame.fbx",
        "Architecture/SM_FloorTile.fbx",
        "Architecture/SM_Column_A.fbx",
    ]
    payload["progress_text"] = "Completed"
    payload["progress_percent"] = 1.0
    payload["status_text"] += "\nSimulated external Blender run completed successfully.\nUpdated destination artifacts: 4\nLast stdout: Blender quit"
    payload["detail_text"] += (
        "\n\nUpdated destination artifacts:\n- "
        + "\n- ".join(os.path.join(normalized_destination, relative_path).replace('\\', '/') for relative_path in example_outputs)
        + "\n\nSimulated results:\n- Discovered preset-driven external Blender workflow\n- Preserved UV-only Ignore UCX Collision export semantics\n- Processed 4 example FBX files into the destination folder"
    )
    return payload
