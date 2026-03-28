from .ProjectIntegration import call_script, read_existing_state, write_tool_snapshot


_STATE_FILE = "BlenderUvFixerPipelineState.json"
_STATUS_FILE = "BlenderUvFixerPipelineStatus.txt"
_UI_STATE = {
    "source_folder": "",
    "destination_folder": "",
    "blender_executable": "",
}


def _ensure_defaults():
    defaults = call_script("peu_example_blender_defaults", "UE_Lightmap_UV_Fixer_Batch.py", "get_default_settings")
    if not _UI_STATE["source_folder"]:
        _UI_STATE["source_folder"] = str(defaults.get("source_dir") or "")
    if not _UI_STATE["destination_folder"]:
        _UI_STATE["destination_folder"] = str(defaults.get("destination_dir") or "")
    if not _UI_STATE["blender_executable"]:
        _UI_STATE["blender_executable"] = str(defaults.get("blender_executable") or "")


def _load_saved_state():
    _ensure_defaults()
    payload = read_existing_state(_STATE_FILE)
    _UI_STATE["source_folder"] = str(payload.get("source_folder") or _UI_STATE["source_folder"])
    _UI_STATE["destination_folder"] = str(payload.get("destination_folder") or _UI_STATE["destination_folder"])
    _UI_STATE["blender_executable"] = str(payload.get("blender_executable") or _UI_STATE["blender_executable"])


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


def refresh_status():
    _load_saved_state()
    _save("peu_example_blender_preview")


def set_paths(source_folder: str, destination_folder: str, blender_executable: str):
    _load_saved_state()
    _UI_STATE["source_folder"] = str(source_folder or _UI_STATE["source_folder"])
    _UI_STATE["destination_folder"] = str(destination_folder or _UI_STATE["destination_folder"])
    _UI_STATE["blender_executable"] = str(blender_executable or _UI_STATE["blender_executable"])
    _save("peu_example_blender_preview")


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
