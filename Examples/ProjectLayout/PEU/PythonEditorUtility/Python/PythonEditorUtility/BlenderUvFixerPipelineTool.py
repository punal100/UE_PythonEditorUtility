import os
import subprocess
import sys

from .ProjectIntegration import call_script, read_existing_state, write_tool_snapshot


_STATE_FILE = "BlenderUvFixerPipelineState.json"
_STATUS_FILE = "BlenderUvFixerPipelineStatus.txt"
_UI_STATE = {
    "source_folder": "",
    "destination_folder": "",
    "blender_executable": "",
    "island_margin": "0.05",
    "merge_distance": "0.0001",
    "merge_by_distance": True,
    "ignore_collision": True,
    "apply_scale": True,
    "mark_active_for_export": True,
    "export_preset_choice": "__AUTO__",
    "available_export_presets": [],
    "preset_source_status": "Preset list not loaded yet. Click Refresh Presets to query Blender operator presets.",
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
    normalized = os.path.abspath(os.path.normpath(os.path.expanduser(candidate)))
    base_name = os.path.basename(normalized).lower()
    if base_name in {"blender-launcher.exe", "blender-launcher"}:
        sibling_candidates = (
            os.path.join(os.path.dirname(normalized), "blender.exe"),
            os.path.join(os.path.dirname(normalized), "blender"),
        )
        for sibling_path in sibling_candidates:
            if os.path.isfile(sibling_path):
                return sibling_path
    return normalized


def _normalize_float_string(value, fallback: float, minimum: float = 0.0) -> str:
    try:
        parsed = float(str(value).strip())
    except Exception:
        parsed = float(fallback)
    parsed = max(minimum, parsed)
    formatted = f"{parsed:.6f}".rstrip("0").rstrip(".")
    return formatted or "0"


def _normalize_bool(value, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    if not normalized:
        return bool(fallback)
    return normalized in {"true", "1", "yes", "checked"}


def _normalize_export_preset_names(values) -> list[str]:
    normalized = []
    seen = set()
    for value in values or []:
        candidate = str(value or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return sorted(normalized, key=str.casefold)


def _normalize_export_preset_key(value: str) -> str:
    return "".join(character for character in str(value or "").strip().casefold() if character.isalnum())


def _resolve_matching_export_preset_name(candidate: str, preset_names: list[str]) -> str:
    candidate = str(candidate or "").strip()
    if not candidate:
        return ""
    if candidate in preset_names:
        return candidate

    normalized_candidate = _normalize_export_preset_key(candidate)
    for preset_name in preset_names:
        if _normalize_export_preset_key(preset_name) == normalized_candidate:
            return preset_name
    return ""


def _is_auto_export_preset_choice(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in {"", "auto", "auto / none", "none", "default", "__auto__"}


def _get_export_preset_display_text() -> str:
    choice = str(_UI_STATE.get("export_preset_choice") or "").strip()
    return "Auto / None" if _is_auto_export_preset_choice(choice) else choice


def _get_export_preset_cycle() -> list[str]:
    return ["__AUTO__"] + list(_UI_STATE.get("available_export_presets", []))


def _ensure_defaults():
    defaults = call_script("peu_example_blender_defaults", "UE_Lightmap_UV_Fixer_Batch.py", "get_default_settings")
    if not _UI_STATE["source_folder"]:
        _UI_STATE["source_folder"] = _normalize_folder(defaults.get("source_dir"), "")
    if not _UI_STATE["destination_folder"]:
        _UI_STATE["destination_folder"] = _normalize_folder(defaults.get("destination_dir"), "")
    if not _UI_STATE["blender_executable"]:
        _UI_STATE["blender_executable"] = _normalize_file(defaults.get("blender_executable"), "")
    _UI_STATE["island_margin"] = _normalize_float_string(defaults.get("island_margin"), 0.05)
    _UI_STATE["merge_distance"] = _normalize_float_string(defaults.get("merge_distance"), 0.0001)
    _UI_STATE["merge_by_distance"] = _normalize_bool(defaults.get("merge_by_distance"), True)
    _UI_STATE["ignore_collision"] = _normalize_bool(defaults.get("ignore_collision"), True)
    _UI_STATE["apply_scale"] = _normalize_bool(defaults.get("apply_scale"), True)
    _UI_STATE["mark_active_for_export"] = _normalize_bool(defaults.get("mark_active_for_export"), True)
    _UI_STATE["export_preset_choice"] = str(defaults.get("default_export_preset_choice") or "__AUTO__")
    _UI_STATE["available_export_presets"] = _normalize_export_preset_names(defaults.get("available_export_presets", []))


def _load_saved_state():
    _ensure_defaults()
    payload = read_existing_state(_STATE_FILE)
    _UI_STATE["source_folder"] = _normalize_folder(payload.get("source_folder"), _UI_STATE["source_folder"])
    _UI_STATE["destination_folder"] = _normalize_folder(payload.get("destination_folder"), _UI_STATE["destination_folder"])
    _UI_STATE["blender_executable"] = _normalize_file(payload.get("blender_executable"), _UI_STATE["blender_executable"])
    _UI_STATE["island_margin"] = _normalize_float_string(payload.get("island_margin"), float(_UI_STATE["island_margin"]))
    _UI_STATE["merge_distance"] = _normalize_float_string(payload.get("merge_distance"), float(_UI_STATE["merge_distance"]))
    _UI_STATE["merge_by_distance"] = _normalize_bool(payload.get("merge_by_distance"), _UI_STATE["merge_by_distance"])
    _UI_STATE["ignore_collision"] = _normalize_bool(payload.get("ignore_collision"), _UI_STATE["ignore_collision"])
    _UI_STATE["apply_scale"] = _normalize_bool(payload.get("apply_scale"), _UI_STATE["apply_scale"])
    _UI_STATE["mark_active_for_export"] = _normalize_bool(payload.get("mark_active_for_export"), _UI_STATE["mark_active_for_export"])
    _UI_STATE["export_preset_choice"] = str(payload.get("export_preset_choice") or _UI_STATE["export_preset_choice"])
    _UI_STATE["available_export_presets"] = _normalize_export_preset_names(payload.get("available_export_presets", _UI_STATE["available_export_presets"]))
    _UI_STATE["preset_source_status"] = str(
        payload.get("preset_source_status")
        or _UI_STATE.get("preset_source_status")
        or "Preset list not loaded yet. Click Refresh Presets to query Blender operator presets."
    )


def _apply_preset_discovery() -> None:
    discovery = call_script(
        "peu_example_blender_discover_presets",
        "UE_Lightmap_UV_Fixer_Batch.py",
        "discover_export_presets",
        _UI_STATE["blender_executable"],
    )
    preset_names = _normalize_export_preset_names(discovery.get("preset_names", []))
    _UI_STATE["available_export_presets"] = preset_names

    current_choice = str(_UI_STATE.get("export_preset_choice") or "").strip()
    default_preset = str(discovery.get("default_export_preset") or "UE_Export")
    auto_choice = str(discovery.get("default_export_preset_choice") or "__AUTO__")
    if _is_auto_export_preset_choice(current_choice):
        _UI_STATE["export_preset_choice"] = auto_choice
    else:
        matched_choice = _resolve_matching_export_preset_name(current_choice, preset_names)
        if matched_choice:
            _UI_STATE["export_preset_choice"] = matched_choice
        else:
            matched_default = _resolve_matching_export_preset_name(default_preset, preset_names)
            _UI_STATE["export_preset_choice"] = matched_default or auto_choice

    resolved_blender_path = str(discovery.get("resolved_blender_path") or _UI_STATE["blender_executable"] or "blender.exe")
    if preset_names:
        _UI_STATE["preset_source_status"] = f"Loaded {len(preset_names)} operator preset(s) from Blender: {resolved_blender_path}"
    else:
        _UI_STATE["preset_source_status"] = f"Blender returned no FBX operator presets. Auto / None will use Blender defaults. Source: {resolved_blender_path}"


def _build_payload(function_name: str):
    payload = call_script(
        f"peu_example_blender_{function_name}",
        "UE_Lightmap_UV_Fixer_Batch.py",
        function_name,
        _UI_STATE["source_folder"],
        _UI_STATE["destination_folder"],
        _UI_STATE["blender_executable"],
        float(_UI_STATE["island_margin"]),
        float(_UI_STATE["merge_distance"]),
        bool(_UI_STATE["merge_by_distance"]),
        bool(_UI_STATE["ignore_collision"]),
        bool(_UI_STATE["apply_scale"]),
        bool(_UI_STATE["mark_active_for_export"]),
        _UI_STATE["export_preset_choice"],
        list(_UI_STATE.get("available_export_presets", [])),
        _UI_STATE.get("preset_source_status", ""),
    )
    payload["source_folder"] = _UI_STATE["source_folder"]
    payload["destination_folder"] = _UI_STATE["destination_folder"]
    payload["blender_executable"] = _UI_STATE["blender_executable"]
    payload["island_margin"] = _UI_STATE["island_margin"]
    payload["merge_distance"] = _UI_STATE["merge_distance"]
    payload["merge_by_distance"] = bool(_UI_STATE["merge_by_distance"])
    payload["ignore_collision"] = bool(_UI_STATE["ignore_collision"])
    payload["apply_scale"] = bool(_UI_STATE["apply_scale"])
    payload["mark_active_for_export"] = bool(_UI_STATE["mark_active_for_export"])
    payload["export_preset_choice"] = _UI_STATE["export_preset_choice"]
    payload["export_preset_choice_display"] = _get_export_preset_display_text()
    payload["available_export_presets"] = list(_UI_STATE.get("available_export_presets", []))
    payload["preset_source_status"] = _UI_STATE["preset_source_status"]
    write_tool_snapshot(_STATE_FILE, _STATUS_FILE, payload)


def _refresh_snapshot(reload_saved_state: bool = True):
    if reload_saved_state:
        _load_saved_state()
    _build_payload("build_preview")


def refresh_status():
    _refresh_snapshot(reload_saved_state=True)


def set_paths(source_folder: str, destination_folder: str, blender_executable: str):
    _load_saved_state()
    previous_blender_executable = _UI_STATE["blender_executable"]
    _UI_STATE["source_folder"] = _normalize_folder(source_folder, _UI_STATE["source_folder"])
    _UI_STATE["destination_folder"] = _normalize_folder(destination_folder, _UI_STATE["destination_folder"])
    _UI_STATE["blender_executable"] = _normalize_file(blender_executable, _UI_STATE["blender_executable"])
    if _UI_STATE["blender_executable"] != previous_blender_executable or not _UI_STATE.get("available_export_presets"):
        try:
            _apply_preset_discovery()
        except Exception as error:
            _UI_STATE["available_export_presets"] = []
            _UI_STATE["export_preset_choice"] = "__AUTO__"
            _UI_STATE["preset_source_status"] = f"Could not query Blender operator presets: {error}"
    _refresh_snapshot(reload_saved_state=False)


def set_processing_values(island_margin: str, merge_distance: str, export_preset_choice: str):
    _load_saved_state()
    _UI_STATE["island_margin"] = _normalize_float_string(island_margin, float(_UI_STATE["island_margin"]))
    _UI_STATE["merge_distance"] = _normalize_float_string(merge_distance, float(_UI_STATE["merge_distance"]))
    if export_preset_choice:
        _UI_STATE["export_preset_choice"] = str(export_preset_choice).strip()
    _refresh_snapshot(reload_saved_state=False)


def set_toggle_options(merge_by_distance: str, ignore_collision: str, apply_scale: str, mark_active_for_export: str):
    _load_saved_state()
    _UI_STATE["merge_by_distance"] = _normalize_bool(merge_by_distance, _UI_STATE["merge_by_distance"])
    _UI_STATE["ignore_collision"] = _normalize_bool(ignore_collision, _UI_STATE["ignore_collision"])
    _UI_STATE["apply_scale"] = _normalize_bool(apply_scale, _UI_STATE["apply_scale"])
    _UI_STATE["mark_active_for_export"] = _normalize_bool(mark_active_for_export, _UI_STATE["mark_active_for_export"])
    _refresh_snapshot(reload_saved_state=False)


def refresh_export_presets():
    _load_saved_state()
    try:
        _apply_preset_discovery()
    except Exception as error:
        _UI_STATE["available_export_presets"] = []
        _UI_STATE["export_preset_choice"] = "__AUTO__"
        _UI_STATE["preset_source_status"] = f"Could not query Blender operator presets: {error}"
    _refresh_snapshot(reload_saved_state=False)


def _cycle_export_preset(step: int):
    _load_saved_state()
    if not _UI_STATE.get("available_export_presets"):
        try:
            _apply_preset_discovery()
        except Exception as error:
            _UI_STATE["available_export_presets"] = []
            _UI_STATE["preset_source_status"] = f"Could not query Blender operator presets: {error}"
            _refresh_snapshot(reload_saved_state=False)
            return

    cycle = _get_export_preset_cycle()
    current_choice = str(_UI_STATE.get("export_preset_choice") or "__AUTO__").strip()
    if current_choice not in cycle:
        current_choice = "__AUTO__"
    current_index = cycle.index(current_choice)
    _UI_STATE["export_preset_choice"] = cycle[(current_index + step) % len(cycle)]
    _refresh_snapshot(reload_saved_state=False)


def select_previous_export_preset():
    _cycle_export_preset(-1)


def select_next_export_preset():
    _cycle_export_preset(1)


def set_auto_export_preset():
    _load_saved_state()
    _UI_STATE["export_preset_choice"] = "__AUTO__"
    _refresh_snapshot(reload_saved_state=False)


def run_pipeline():
    _load_saved_state()
    _build_payload("run_pipeline")


def _open_path(path: str):
    normalized_path = os.path.abspath(os.path.normpath(os.path.expanduser(path)))
    if sys.platform.startswith("win"):
        os.startfile(normalized_path)
        return
    if sys.platform == "darwin":
        subprocess.run(["open", normalized_path], check=False)
        return
    subprocess.run(["xdg-open", normalized_path], check=False)


def _write_idle_notice(message: str):
    _refresh_snapshot(reload_saved_state=False)
    payload = read_existing_state(_STATE_FILE)
    status_text = str(payload.get("status_text") or "")
    payload["status_text"] = f"{status_text}\n{message}" if status_text else str(message)
    write_tool_snapshot(_STATE_FILE, _STATUS_FILE, payload)


def open_source_folder():
    _load_saved_state()
    target_folder = _normalize_folder(_UI_STATE["source_folder"], "")
    if not target_folder or not os.path.isdir(target_folder):
        _write_idle_notice("Source folder is not available to open.")
        return

    try:
        _open_path(target_folder)
    except Exception as error:
        _write_idle_notice(f"Could not open source folder: {error}")
        return
    refresh_status()


def open_destination_folder():
    _load_saved_state()
    target_folder = _normalize_folder(_UI_STATE["destination_folder"], "")
    if not target_folder:
        _write_idle_notice("Destination folder is not available to open.")
        return

    try:
        os.makedirs(target_folder, exist_ok=True)
        _open_path(target_folder)
    except Exception as error:
        _write_idle_notice(f"Could not open destination folder: {error}")
        return
    refresh_status()


_load_saved_state()
