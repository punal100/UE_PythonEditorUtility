import os

from .ProjectIntegration import call_script, read_existing_state, write_tool_snapshot


_STATE_FILE = "BlenderUvFixerPipelineState.json"
_STATUS_FILE = "BlenderUvFixerPipelineStatus.txt"
_UV0_MODE_KEEP_EXISTING_LABEL = "Keep Existing"
_UV1_MODE_LIGHTMAP_PACK_LABEL = "Lightmap Pack"
_UV1_MODE_SMART_PROJECT_LABEL = "Smart UV Project"
_UI_STATE = {
    "source_folder": "",
    "destination_folder": "",
    "blender_executable": "",
    "uv0_unwrap_mode": _UV0_MODE_KEEP_EXISTING_LABEL,
    "uv1_unwrap_mode": _UV1_MODE_LIGHTMAP_PACK_LABEL,
    "smart_uv_margin": "0.05",
    "lightmap_margin": "0.05",
    "lightmap_pack_quality": "12",
}


def _normalize_folder(value: str, fallback: str) -> str:
    candidate = str(value or fallback or "").strip()
    if not candidate:
        return ""
    return os.path.abspath(os.path.normpath(os.path.expanduser(candidate)))


def _normalize_file(value: str, fallback: str) -> str:
    candidate = str(value or fallback or "").strip()
    if not candidate:
        return ""
    return os.path.abspath(os.path.normpath(os.path.expanduser(candidate)))


def _normalize_float_string(value, fallback: float) -> str:
    try:
        parsed = float(str(value).strip())
    except Exception:
        parsed = float(fallback)
    formatted = f"{parsed:.6f}".rstrip("0").rstrip(".")
    return formatted or "0"


def _normalize_int_string(value, fallback: int, minimum: int = 1, maximum: int = 48) -> str:
    try:
        parsed = int(str(value).strip())
    except Exception:
        parsed = int(fallback)
    parsed = max(minimum, min(maximum, parsed))
    return str(parsed)


def _normalize_bool(value, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    if not normalized:
        return bool(fallback)
    return normalized in {"true", "1", "yes", "checked"}


def _normalize_uv0_unwrap_mode(value: str, fallback: str) -> str:
    candidate = str(value or "").strip()
    if candidate in {_UV0_MODE_KEEP_EXISTING_LABEL, _UV1_MODE_LIGHTMAP_PACK_LABEL, _UV1_MODE_SMART_PROJECT_LABEL}:
        return candidate
    if candidate == "keep_existing":
        return _UV0_MODE_KEEP_EXISTING_LABEL
    if candidate == "lightmap_pack":
        return _UV1_MODE_LIGHTMAP_PACK_LABEL
    if candidate == "smart_project":
        return _UV1_MODE_SMART_PROJECT_LABEL
    normalized_bool = candidate.lower()
    if normalized_bool in {"true", "1", "yes", "checked"}:
        return _UV1_MODE_SMART_PROJECT_LABEL
    if normalized_bool in {"false", "0", "no", "unchecked"}:
        return _UV0_MODE_KEEP_EXISTING_LABEL
    return str(fallback or _UV0_MODE_KEEP_EXISTING_LABEL)


def _normalize_uv1_unwrap_mode(value: str, fallback: str) -> str:
    candidate = str(value or "").strip()
    if candidate in {_UV1_MODE_LIGHTMAP_PACK_LABEL, _UV1_MODE_SMART_PROJECT_LABEL}:
        return candidate
    if candidate == "lightmap_pack":
        return _UV1_MODE_LIGHTMAP_PACK_LABEL
    if candidate == "smart_project":
        return _UV1_MODE_SMART_PROJECT_LABEL
    return str(fallback or _UV1_MODE_LIGHTMAP_PACK_LABEL)


def _get_uv0_unwrap_mode_value() -> str:
    if _UI_STATE["uv0_unwrap_mode"] == _UV1_MODE_SMART_PROJECT_LABEL:
        return "smart_project"
    if _UI_STATE["uv0_unwrap_mode"] == _UV1_MODE_LIGHTMAP_PACK_LABEL:
        return "lightmap_pack"
    return "keep_existing"


def _get_uv1_unwrap_mode_value() -> str:
    if _UI_STATE["uv1_unwrap_mode"] == _UV1_MODE_SMART_PROJECT_LABEL:
        return "smart_project"
    return "lightmap_pack"


def _show_smart_uv_settings() -> bool:
    return _get_uv0_unwrap_mode_value() == "smart_project" or _get_uv1_unwrap_mode_value() == "smart_project"


def _show_lightmap_pack_settings() -> bool:
    return _get_uv0_unwrap_mode_value() == "lightmap_pack" or _get_uv1_unwrap_mode_value() == "lightmap_pack"


def _describe_mode_scope(command_value: str) -> str:
    channels = []
    if _get_uv0_unwrap_mode_value() == command_value:
        channels.append("UV 0")
    if _get_uv1_unwrap_mode_value() == command_value:
        channels.append("UV 1")
    if not channels:
        return "none"
    if len(channels) == 2:
        return "UV 0 and UV 1"
    return channels[0]


def _ensure_defaults():
    defaults = call_script("peu_example_blender_defaults", "UE_Lightmap_UV_Fixer_Batch.py", "get_default_settings")
    if not _UI_STATE["source_folder"]:
        _UI_STATE["source_folder"] = _normalize_folder(defaults.get("source_dir"), "")
    if not _UI_STATE["destination_folder"]:
        _UI_STATE["destination_folder"] = _normalize_folder(defaults.get("destination_dir"), "")
    if not _UI_STATE["blender_executable"]:
        _UI_STATE["blender_executable"] = _normalize_file(defaults.get("blender_executable"), "")
    _UI_STATE["uv0_unwrap_mode"] = _normalize_uv0_unwrap_mode(defaults.get("uv0_unwrap_mode", defaults.get("uv0_smart_project")), _UV0_MODE_KEEP_EXISTING_LABEL)
    _UI_STATE["uv1_unwrap_mode"] = _normalize_uv1_unwrap_mode(defaults.get("uv1_unwrap_mode"), _UV1_MODE_LIGHTMAP_PACK_LABEL)
    _UI_STATE["smart_uv_margin"] = _normalize_float_string(defaults.get("smart_uv_margin"), 0.05)
    _UI_STATE["lightmap_margin"] = _normalize_float_string(defaults.get("lightmap_margin"), 0.05)
    _UI_STATE["lightmap_pack_quality"] = _normalize_int_string(defaults.get("lightmap_pack_quality"), 12)


def _load_saved_state():
    _ensure_defaults()
    payload = read_existing_state(_STATE_FILE)
    _UI_STATE["source_folder"] = _normalize_folder(payload.get("source_folder"), _UI_STATE["source_folder"])
    _UI_STATE["destination_folder"] = _normalize_folder(payload.get("destination_folder"), _UI_STATE["destination_folder"])
    _UI_STATE["blender_executable"] = _normalize_file(payload.get("blender_executable"), _UI_STATE["blender_executable"])
    _UI_STATE["uv0_unwrap_mode"] = _normalize_uv0_unwrap_mode(payload.get("uv0_unwrap_mode", payload.get("uv0_smart_project")), _UI_STATE["uv0_unwrap_mode"])
    _UI_STATE["uv1_unwrap_mode"] = _normalize_uv1_unwrap_mode(payload.get("uv1_unwrap_mode"), _UI_STATE["uv1_unwrap_mode"])
    _UI_STATE["smart_uv_margin"] = _normalize_float_string(payload.get("smart_uv_margin", payload.get("island_margin")), 0.05)
    _UI_STATE["lightmap_margin"] = _normalize_float_string(payload.get("lightmap_margin"), 0.05)
    _UI_STATE["lightmap_pack_quality"] = _normalize_int_string(payload.get("lightmap_pack_quality"), 12)


def _save(runner_name: str):
    payload = call_script(
        runner_name,
        "UE_Lightmap_UV_Fixer_Batch.py",
        "build_preview",
        _UI_STATE["source_folder"],
        _UI_STATE["destination_folder"],
        _UI_STATE["blender_executable"],
        _get_uv0_unwrap_mode_value(),
        _get_uv1_unwrap_mode_value(),
        _UI_STATE["smart_uv_margin"],
        _UI_STATE["lightmap_margin"],
        _UI_STATE["lightmap_pack_quality"],
    )
    payload["source_folder"] = _UI_STATE["source_folder"]
    payload["destination_folder"] = _UI_STATE["destination_folder"]
    payload["blender_executable"] = _UI_STATE["blender_executable"]
    payload["uv0_unwrap_mode"] = _UI_STATE["uv0_unwrap_mode"]
    payload["uv0_smart_project"] = _get_uv0_unwrap_mode_value() == "smart_project"
    payload["uv1_unwrap_mode"] = _UI_STATE["uv1_unwrap_mode"]
    payload["smart_uv_margin"] = _UI_STATE["smart_uv_margin"]
    payload["lightmap_margin"] = _UI_STATE["lightmap_margin"]
    payload["lightmap_pack_quality"] = _UI_STATE["lightmap_pack_quality"]
    if _show_smart_uv_settings():
        payload["smart_uv_scope"] = f"Shared Smart UV settings apply to {_describe_mode_scope('smart_project')}"
    else:
        payload["smart_uv_scope"] = "Smart UV settings hidden for the active unwrap configuration"
    payload["lightmap_pack_scope"] = f"Lightmap Pack settings apply to {_describe_mode_scope('lightmap_pack')}" if _show_lightmap_pack_settings() else "Lightmap Pack settings hidden for the active unwrap configuration"
    payload["show_smart_uv_settings"] = _show_smart_uv_settings()
    payload["show_lightmap_pack_settings"] = _show_lightmap_pack_settings()
    payload["show_smart_uv_cleanup"] = _show_smart_uv_settings()
    write_tool_snapshot(_STATE_FILE, _STATUS_FILE, payload)


def _snapshot_preview(reload_saved_state: bool = True):
    if reload_saved_state:
        _load_saved_state()
    _save("peu_example_blender_preview")


def refresh_status():
    _snapshot_preview(reload_saved_state=True)


def set_paths(source_folder: str, destination_folder: str, blender_executable: str):
    _load_saved_state()
    _UI_STATE["source_folder"] = _normalize_folder(source_folder, _UI_STATE["source_folder"])
    _UI_STATE["destination_folder"] = _normalize_folder(destination_folder, _UI_STATE["destination_folder"])
    _UI_STATE["blender_executable"] = _normalize_file(blender_executable, _UI_STATE["blender_executable"])
    _snapshot_preview(reload_saved_state=False)


def set_uv_workflow_options(uv0_unwrap_mode: str, uv1_unwrap_mode: str):
    _load_saved_state()
    _UI_STATE["uv0_unwrap_mode"] = _normalize_uv0_unwrap_mode(uv0_unwrap_mode, _UI_STATE["uv0_unwrap_mode"])
    _UI_STATE["uv1_unwrap_mode"] = _normalize_uv1_unwrap_mode(uv1_unwrap_mode, _UI_STATE["uv1_unwrap_mode"])
    _snapshot_preview(reload_saved_state=False)


def set_smart_uv_settings(smart_uv_margin: str):
    _load_saved_state()
    _UI_STATE["smart_uv_margin"] = _normalize_float_string(smart_uv_margin, 0.05)
    _snapshot_preview(reload_saved_state=False)


def set_lightmap_pack_settings(lightmap_margin: str, lightmap_pack_quality: str):
    _load_saved_state()
    _UI_STATE["lightmap_margin"] = _normalize_float_string(lightmap_margin, 0.05)
    _UI_STATE["lightmap_pack_quality"] = _normalize_int_string(lightmap_pack_quality, 12)
    _snapshot_preview(reload_saved_state=False)


def run_pipeline():
    _load_saved_state()
    payload = call_script(
        "peu_example_blender_run",
        "UE_Lightmap_UV_Fixer_Batch.py",
        "run_pipeline",
        _UI_STATE["source_folder"],
        _UI_STATE["destination_folder"],
        _UI_STATE["blender_executable"],
        _get_uv0_unwrap_mode_value(),
        _get_uv1_unwrap_mode_value(),
        _UI_STATE["smart_uv_margin"],
        _UI_STATE["lightmap_margin"],
        _UI_STATE["lightmap_pack_quality"],
    )
    payload["source_folder"] = _UI_STATE["source_folder"]
    payload["destination_folder"] = _UI_STATE["destination_folder"]
    payload["blender_executable"] = _UI_STATE["blender_executable"]
    payload["uv0_unwrap_mode"] = _UI_STATE["uv0_unwrap_mode"]
    payload["uv0_smart_project"] = _get_uv0_unwrap_mode_value() == "smart_project"
    payload["uv1_unwrap_mode"] = _UI_STATE["uv1_unwrap_mode"]
    payload["smart_uv_margin"] = _UI_STATE["smart_uv_margin"]
    payload["lightmap_margin"] = _UI_STATE["lightmap_margin"]
    payload["lightmap_pack_quality"] = _UI_STATE["lightmap_pack_quality"]
    if _show_smart_uv_settings():
        payload["smart_uv_scope"] = f"Shared Smart UV settings apply to {_describe_mode_scope('smart_project')}"
    else:
        payload["smart_uv_scope"] = "Smart UV settings hidden for the active unwrap configuration"
    payload["lightmap_pack_scope"] = f"Lightmap Pack settings apply to {_describe_mode_scope('lightmap_pack')}" if _show_lightmap_pack_settings() else "Lightmap Pack settings hidden for the active unwrap configuration"
    payload["show_smart_uv_settings"] = _show_smart_uv_settings()
    payload["show_lightmap_pack_settings"] = _show_lightmap_pack_settings()
    payload["show_smart_uv_cleanup"] = _show_smart_uv_settings()
    write_tool_snapshot(_STATE_FILE, _STATUS_FILE, payload)


def open_source_folder():
    _load_saved_state()
    _save("peu_example_blender_preview")


def open_destination_folder():
    _load_saved_state()
    _save("peu_example_blender_preview")
