import os

from .ProjectIntegration import call_script, read_existing_state, write_tool_snapshot


_STATE_FILE = "BlenderUvFixerPipelineState.json"
_STATUS_FILE = "BlenderUvFixerPipelineStatus.txt"
_UI_STATE = {
    "source_folder": "",
    "destination_folder": "",
    "blender_executable": "",
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


def _ensure_defaults():
    defaults = call_script("peu_example_blender_defaults", "UE_Lightmap_UV_Fixer_Batch.py", "get_default_settings")
    if not _UI_STATE["source_folder"]:
        _UI_STATE["source_folder"] = _normalize_folder(defaults.get("source_dir"), "")
    if not _UI_STATE["destination_folder"]:
        _UI_STATE["destination_folder"] = _normalize_folder(defaults.get("destination_dir"), "")
    if not _UI_STATE["blender_executable"]:
        _UI_STATE["blender_executable"] = _normalize_file(defaults.get("blender_executable"), "")


def _load_saved_state():
    _ensure_defaults()
    payload = read_existing_state(_STATE_FILE)
    _UI_STATE["source_folder"] = _normalize_folder(payload.get("source_folder"), _UI_STATE["source_folder"])
    _UI_STATE["destination_folder"] = _normalize_folder(payload.get("destination_folder"), _UI_STATE["destination_folder"])
    _UI_STATE["blender_executable"] = _normalize_file(payload.get("blender_executable"), _UI_STATE["blender_executable"])


def _save(runner_name: str):
    payload = call_script(
        runner_name,
        "UE_Lightmap_UV_Fixer_Batch.py",
        "build_preview",
        _UI_STATE["source_folder"],
        _UI_STATE["destination_folder"],
        _UI_STATE["blender_executable"],
    )
    payload["source_folder"] = _UI_STATE["source_folder"]
    payload["destination_folder"] = _UI_STATE["destination_folder"]
    payload["blender_executable"] = _UI_STATE["blender_executable"]
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


def run_pipeline():
    _load_saved_state()
    payload = call_script(
        "peu_example_blender_run",
        "UE_Lightmap_UV_Fixer_Batch.py",
        "run_pipeline",
        _UI_STATE["source_folder"],
        _UI_STATE["destination_folder"],
        _UI_STATE["blender_executable"],
    )
    payload["source_folder"] = _UI_STATE["source_folder"]
    payload["destination_folder"] = _UI_STATE["destination_folder"]
    payload["blender_executable"] = _UI_STATE["blender_executable"]
    write_tool_snapshot(_STATE_FILE, _STATUS_FILE, payload)


def open_source_folder():
    _load_saved_state()
    _save("peu_example_blender_preview")


def open_destination_folder():
    _load_saved_state()
    _save("peu_example_blender_preview")
