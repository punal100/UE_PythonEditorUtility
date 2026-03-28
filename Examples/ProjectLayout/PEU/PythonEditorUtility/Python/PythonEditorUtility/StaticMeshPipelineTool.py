from .ProjectIntegration import call_script, read_existing_state, write_tool_snapshot


_STATE_FILE = "StaticMeshPipelineState.json"
_STATUS_FILE = "StaticMeshPipelineStatus.txt"
_SORT_COLUMNS = {"Asset", "Action", "Result", "Overlap", "Wrapping"}
_SORT_DIRECTIONS = {"Asc", "Desc"}
_UI_STATE = {
    "risks_only": False,
    "sort_column": "Result",
    "sort_direction": "Desc",
    "export_source": "",
    "export_destination": "",
    "import_source": "",
    "import_destination": "",
    "selected_row_keys": [],
}


def _normalize_folder(value: str, fallback: str) -> str:
    candidate = str(value or fallback or "").strip()
    if not candidate:
        return ""
    return os.path.abspath(os.path.normpath(os.path.expanduser(candidate)))


def _ensure_defaults():
    if not _UI_STATE["export_source"] or not _UI_STATE["export_destination"]:
        export_settings = call_script("peu_example_export_defaults", "bulk_export_static_meshes.py", "get_default_settings")
        _UI_STATE["export_source"] = str(export_settings.get("source") or "/Game")
        _UI_STATE["export_destination"] = _normalize_folder(export_settings.get("destination"), "")
    if not _UI_STATE["import_source"] or not _UI_STATE["import_destination"]:
        import_settings = call_script("peu_example_import_defaults", "bulk_reimport_static_meshes.py", "get_default_settings")
        _UI_STATE["import_source"] = _normalize_folder(import_settings.get("source"), "")
        _UI_STATE["import_destination"] = str(import_settings.get("destination") or "/Game")


def _load_saved_state():
    _ensure_defaults()
    payload = read_existing_state(_STATE_FILE)
    _UI_STATE["risks_only"] = bool(payload.get("risks_only", _UI_STATE["risks_only"]))
    sort_column = str(payload.get("sort_column") or _UI_STATE["sort_column"])
    _UI_STATE["sort_column"] = sort_column if sort_column in _SORT_COLUMNS else "Result"
    sort_direction = str(payload.get("sort_direction") or _UI_STATE["sort_direction"])
    _UI_STATE["sort_direction"] = sort_direction if sort_direction in _SORT_DIRECTIONS else "Desc"
    _UI_STATE["export_source"] = str(payload.get("export_source") or _UI_STATE["export_source"])
    _UI_STATE["export_destination"] = _normalize_folder(payload.get("export_destination"), _UI_STATE["export_destination"])
    _UI_STATE["import_source"] = _normalize_folder(payload.get("import_source"), _UI_STATE["import_source"])
    _UI_STATE["import_destination"] = str(payload.get("import_destination") or _UI_STATE["import_destination"])
    _UI_STATE["selected_row_keys"] = [str(key) for key in payload.get("selected_row_keys", [])]


def _snapshot(operation_result: dict | None = None):
    payload = call_script(
        "peu_example_static_mesh_pipeline",
        "audit_static_mesh_lightmaps.py",
        "build_pipeline_snapshot",
        _UI_STATE["export_source"],
        _UI_STATE["export_destination"],
        _UI_STATE["import_source"],
        _UI_STATE["import_destination"],
        _UI_STATE["risks_only"],
        _UI_STATE["sort_column"],
        _UI_STATE["sort_direction"],
        _UI_STATE["selected_row_keys"],
        operation_result,
    )
    payload["risks_only"] = _UI_STATE["risks_only"]
    payload["sort_column"] = _UI_STATE["sort_column"]
    payload["sort_direction"] = _UI_STATE["sort_direction"]
    payload["export_source"] = _UI_STATE["export_source"]
    payload["export_destination"] = _UI_STATE["export_destination"]
    payload["import_source"] = _UI_STATE["import_source"]
    payload["import_destination"] = _UI_STATE["import_destination"]
    write_tool_snapshot(_STATE_FILE, _STATUS_FILE, payload)


def refresh_status():
    _load_saved_state()
    _snapshot()


def set_paths(export_source: str, export_destination: str, import_source: str, import_destination: str):
    _load_saved_state()
    _UI_STATE["export_source"] = str(export_source or _UI_STATE["export_source"])
    _UI_STATE["export_destination"] = _normalize_folder(export_destination, _UI_STATE["export_destination"])
    _UI_STATE["import_source"] = _normalize_folder(import_source, _UI_STATE["import_source"])
    _UI_STATE["import_destination"] = str(import_destination or _UI_STATE["import_destination"])
    _snapshot()


def set_risks_only(value: bool):
    _load_saved_state()
    _UI_STATE["risks_only"] = bool(value)
    _snapshot()


def set_sort(sort_column: str, sort_direction: str):
    _load_saved_state()
    _UI_STATE["sort_column"] = sort_column if sort_column in _SORT_COLUMNS else "Result"
    _UI_STATE["sort_direction"] = sort_direction if sort_direction in _SORT_DIRECTIONS else "Desc"
    _snapshot()


def set_selected_rows(selected_keys):
    _load_saved_state()
    _UI_STATE["selected_row_keys"] = [str(key) for key in selected_keys or []]
    _snapshot()


def run_export():
    _load_saved_state()
    result = call_script(
        "peu_example_static_mesh_export",
        "bulk_export_static_meshes.py",
        "run_export",
        _UI_STATE["export_source"],
        _UI_STATE["export_destination"],
    )
    _snapshot(result)


def run_import_reimport():
    _load_saved_state()
    result = call_script(
        "peu_example_static_mesh_import",
        "bulk_reimport_static_meshes.py",
        "run_import_reimport",
        _UI_STATE["import_source"],
        _UI_STATE["import_destination"],
    )
    _snapshot(result)


def open_last_audit_report():
    _load_saved_state()
    _snapshot(
        {
            "operation": "Open Audit Report",
            "message": "Open the latest audit report from the export destination or promote this stub to your project's real report writer.",
            "processed": 0,
            "exported": 0,
            "imported_new": 0,
            "reimported_existing": 0,
            "failed": 0,
            "risky": 1,
        }
    )
