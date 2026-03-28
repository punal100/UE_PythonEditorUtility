from .ProjectIntegration import call_script, read_existing_state, write_tool_snapshot


_STATE_FILE = "LightmapResolutionState.json"
_STATUS_FILE = "LightmapResolutionStatus.txt"
_SORT_COLUMNS = {"Level", "Actor", "Mesh", "Effective", "Asset", "Override"}
_SORT_DIRECTIONS = {"Asc", "Desc"}
_UI_STATE = {
    "resolution": "64",
    "open_level_only": False,
    "override_only": False,
    "sort_column": "Level",
    "sort_direction": "Asc",
    "selected_row_keys": [],
}


def _load_saved_state():
    payload = read_existing_state(_STATE_FILE)
    _UI_STATE["resolution"] = str(payload.get("resolution") or _UI_STATE["resolution"])
    _UI_STATE["open_level_only"] = bool(payload.get("open_level_only", _UI_STATE["open_level_only"]))
    _UI_STATE["override_only"] = bool(payload.get("override_only", _UI_STATE["override_only"]))
    sort_column = str(payload.get("sort_column") or _UI_STATE["sort_column"])
    _UI_STATE["sort_column"] = sort_column if sort_column in _SORT_COLUMNS else "Level"
    sort_direction = str(payload.get("sort_direction") or _UI_STATE["sort_direction"])
    _UI_STATE["sort_direction"] = sort_direction if sort_direction in _SORT_DIRECTIONS else "Asc"
    _UI_STATE["selected_row_keys"] = [str(key) for key in payload.get("selected_row_keys", [])]


def _normalized_resolution(value: str) -> str:
    try:
        return str(max(1, int(str(value).strip() or "64")))
    except Exception:
        return "64"


def _save(action: str = "refresh"):
    payload = call_script(
        "peu_example_lightmap_resolution",
        "build_level_lighting.py",
        "build_lightmap_snapshot",
        _UI_STATE["resolution"],
        _UI_STATE["open_level_only"],
        _UI_STATE["override_only"],
        _UI_STATE["sort_column"],
        _UI_STATE["sort_direction"],
        _UI_STATE["selected_row_keys"],
        action,
    )
    write_tool_snapshot(_STATE_FILE, _STATUS_FILE, payload)


def refresh_status():
    _load_saved_state()
    _save()


def set_resolution(value: str):
    _load_saved_state()
    _UI_STATE["resolution"] = _normalized_resolution(value)
    _save()


def set_open_level_only(value: bool):
    _load_saved_state()
    _UI_STATE["open_level_only"] = bool(value)
    _save()


def set_override_only(value: bool):
    _load_saved_state()
    _UI_STATE["override_only"] = bool(value)
    _save()


def set_sort(sort_column: str, sort_direction: str):
    _load_saved_state()
    _UI_STATE["sort_column"] = sort_column if sort_column in _SORT_COLUMNS else "Level"
    _UI_STATE["sort_direction"] = sort_direction if sort_direction in _SORT_DIRECTIONS else "Asc"
    _save()


def set_selected_rows(selected_keys):
    _load_saved_state()
    _UI_STATE["selected_row_keys"] = [str(key) for key in selected_keys or []]
    _save()


def apply_to_instance():
    _load_saved_state()
    _save("apply_instance")


def clear_instance_override():
    _load_saved_state()
    _save("clear_instance_override")


def apply_to_asset():
    _load_saved_state()
    _save("apply_asset")


def open_selected_actor():
    _load_saved_state()
    _save("open_selected_actor")


def sync_selected_asset():
    _load_saved_state()
    _save("sync_selected_asset")
