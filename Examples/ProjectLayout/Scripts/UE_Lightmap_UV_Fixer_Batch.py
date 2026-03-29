import os

from project_path_utils import get_export_from_blender_dir, get_export_from_ue_dir


SOURCE_DIR = get_export_from_ue_dir(__file__)
DESTINATION_DIR = get_export_from_blender_dir(__file__)
DEFAULT_BLENDER_ENV_VAR = "BLENDER_EXECUTABLE"
DEFAULT_SMART_UV_MARGIN = 0.05
DEFAULT_LIGHTMAP_MARGIN = 0.05
DEFAULT_LIGHTMAP_PACK_QUALITY = 12
UNWRAP_MODE_KEEP_EXISTING = "keep_existing"
UNWRAP_MODE_LIGHTMAP_PACK = "lightmap_pack"
UNWRAP_MODE_SMART_PROJECT = "smart_project"
DEFAULT_UV0_UNWRAP_MODE = UNWRAP_MODE_KEEP_EXISTING
DEFAULT_UV1_UNWRAP_MODE = UNWRAP_MODE_LIGHTMAP_PACK


def get_default_settings() -> dict:
    return {
        "source_dir": SOURCE_DIR,
        "destination_dir": DESTINATION_DIR,
        "blender_executable": os.environ.get(DEFAULT_BLENDER_ENV_VAR, ""),
        "uv0_unwrap_mode": DEFAULT_UV0_UNWRAP_MODE,
        "uv1_unwrap_mode": DEFAULT_UV1_UNWRAP_MODE,
        "smart_uv_margin": DEFAULT_SMART_UV_MARGIN,
        "lightmap_margin": DEFAULT_LIGHTMAP_MARGIN,
        "lightmap_pack_quality": DEFAULT_LIGHTMAP_PACK_QUALITY,
    }


def build_preview(
    source_dir: str,
    destination_dir: str,
    blender_executable: str,
    uv0_unwrap_mode: str,
    uv1_unwrap_mode: str,
    smart_uv_margin: str,
    lightmap_margin: str,
    lightmap_pack_quality: str,
) -> dict:
    normalized_source = os.path.abspath(os.path.normpath(source_dir or SOURCE_DIR))
    normalized_destination = os.path.abspath(os.path.normpath(destination_dir or DESTINATION_DIR))
    normalized_blender = str(blender_executable or os.environ.get(DEFAULT_BLENDER_ENV_VAR, "")).strip()
    uv0_label = {
        UNWRAP_MODE_KEEP_EXISTING: "Keep Existing",
        UNWRAP_MODE_LIGHTMAP_PACK: "Lightmap Pack",
        UNWRAP_MODE_SMART_PROJECT: "Smart UV Project",
    }.get(str(uv0_unwrap_mode), "Keep Existing")
    uv1_label = "Lightmap Pack" if str(uv1_unwrap_mode) == UNWRAP_MODE_LIGHTMAP_PACK else "Smart UV Project"
    smart_uv_scope = []
    if str(uv0_unwrap_mode) == UNWRAP_MODE_SMART_PROJECT:
        smart_uv_scope.append("UV 0")
    if str(uv1_unwrap_mode) == UNWRAP_MODE_SMART_PROJECT:
        smart_uv_scope.append("UV 1")
    lightmap_scope = []
    if str(uv0_unwrap_mode) == UNWRAP_MODE_LIGHTMAP_PACK:
        lightmap_scope.append("UV 0")
    if str(uv1_unwrap_mode) == UNWRAP_MODE_LIGHTMAP_PACK:
        lightmap_scope.append("UV 1")
    show_smart_uv_settings = bool(smart_uv_scope)
    show_lightmap_pack_settings = bool(lightmap_scope)
    status_lines = [
        "Blender UV Fixer Pipeline",
        f"Source folder: {normalized_source}",
        f"Destination folder: {normalized_destination}",
        f"Blender executable: {normalized_blender or 'Use BLENDER_EXECUTABLE or PATH'}",
        f"UV 0 mode: {uv0_label} | UV 1 mode: {uv1_label}",
        f"Shared Smart UV settings apply to {' and '.join(smart_uv_scope)} | Smart UV Margin: {smart_uv_margin}" if show_smart_uv_settings else "Smart UV settings hidden for the active unwrap configuration",
        f"Lightmap Pack settings apply to {' and '.join(lightmap_scope)} | Margin: {lightmap_margin} | Pack Quality: {lightmap_pack_quality}" if show_lightmap_pack_settings else "Lightmap Pack settings hidden for the active unwrap configuration",
        "Run the example pipeline to simulate the headless batch flow used by the live project.",
    ]
    detail_lines = [
        f"Source folder: {normalized_source}",
        f"Destination folder: {normalized_destination}",
        f"Blender executable override: {normalized_blender or 'None'}",
        f"UV 0 unwrap mode: {uv0_label} ({uv0_unwrap_mode})",
        f"UV 1 unwrap mode: {uv1_label} ({uv1_unwrap_mode})",
        f"Shared Smart UV settings apply to {' and '.join(smart_uv_scope) if smart_uv_scope else 'no active Smart UV path'} | Smart UV Margin: {smart_uv_margin}",
        f"Lightmap Pack settings apply to {' and '.join(lightmap_scope) if lightmap_scope else 'no active Lightmap Pack path'} | Margin: {lightmap_margin} | Pack Quality: {lightmap_pack_quality}",
        "This example does not invoke Blender. It demonstrates the same state contract and UI flow as the real project-owned batch tool.",
    ]
    return {
        "progress_text": "Idle",
        "progress_percent": 0.0,
        "status_text": "\n".join(status_lines),
        "detail_text": "\n".join(detail_lines),
        "show_smart_uv_settings": show_smart_uv_settings,
        "show_lightmap_pack_settings": show_lightmap_pack_settings,
        "show_smart_uv_cleanup": show_smart_uv_settings,
    }


def run_pipeline(
    source_dir: str,
    destination_dir: str,
    blender_executable: str,
    uv0_unwrap_mode: str,
    uv1_unwrap_mode: str,
    smart_uv_margin: str,
    lightmap_margin: str,
    lightmap_pack_quality: str,
) -> dict:
    payload = build_preview(
        source_dir,
        destination_dir,
        blender_executable,
        uv0_unwrap_mode,
        uv1_unwrap_mode,
        smart_uv_margin,
        lightmap_margin,
        lightmap_pack_quality,
    )
    payload["progress_text"] = "Completed"
    payload["progress_percent"] = 1.0
    payload["status_text"] += "\nCompleted example headless run with 3 sample FBX files."
    payload["detail_text"] += "\n\nSimulated actions:\n- Validate source and destination folders\n- Resolve Blender executable\n- Apply the selected UV 0 unwrap mode\n- Rebuild UV1 with the selected unwrap mode\n- Process 3 sample FBX files\n- Write fixed files to the destination folder"
    return payload
