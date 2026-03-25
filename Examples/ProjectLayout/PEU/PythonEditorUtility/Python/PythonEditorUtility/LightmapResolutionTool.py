import importlib.util
import json
import os

import unreal


_SORT_COLUMNS = ("Level", "Actor", "Component", "Mesh", "Mobility", "Effective", "Asset", "Override")
_SORT_DIRECTIONS = ("Asc", "Desc")
_UI_STATE = {
    "resolution": "64",
    "open_level_only": False,
    "override_only": False,
    "sort_column": "Level",
    "sort_direction": "Asc",
    "selected_row_keys": [],
}


def _get_state_dir():
    project_dir = os.path.abspath(os.path.normpath(unreal.Paths.project_dir()))
    state_dir = os.path.join(project_dir, "PEU", "PythonEditorUtility", "State")
    os.makedirs(state_dir, exist_ok=True)
    return state_dir


def _get_status_file_path():
    return os.path.join(_get_state_dir(), "LightmapResolutionStatus.txt")


def _get_state_file_path():
    return os.path.join(_get_state_dir(), "LightmapResolutionState.json")


def _load_backend_module():
    project_dir = os.path.abspath(os.path.normpath(unreal.Paths.project_dir()))
    script_path = os.path.join(project_dir, "Scripts", "build_level_lighting.py")
    spec = importlib.util.spec_from_file_location("build_level_lighting_backend", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load build lighting backend from {script_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _set_resolution_value(value):
    try:
        parsed = int(str(value).strip())
    except Exception:
        parsed = 64
    _UI_STATE["resolution"] = str(max(1, parsed))


def _normalize_sort_column(value):
    normalized = str(value or "").strip()
    return normalized if normalized in _SORT_COLUMNS else "Level"


def _normalize_sort_direction(value):
    normalized = str(value or "").strip()
    return normalized if normalized in _SORT_DIRECTIONS else "Asc"


def _row_key(row):
    return "||".join((str(row.level_path), str(row.actor_path), str(row.component_name), str(row.asset_path)))


def _row_override_text(row):
    return str(row.overridden_light_map_res) if row.override_light_map_res else "-"


def _row_to_dict(row):
    return {
        "key": _row_key(row),
        "level": str(row.level_path),
        "actor": str(row.actor_label),
        "component": str(row.component_name),
        "mesh": str(row.asset_name),
        "mobility": str(row.mobility),
        "effective": str(row.effective_light_map_resolution),
        "asset": str(row.asset_lightmap_resolution),
        "override": _row_override_text(row),
    }


def _rows_by_key(rows):
    return {_row_key(row): row for row in rows}


def _sanitize_selected_row_keys(rows):
    available = _rows_by_key(rows)
    _UI_STATE["selected_row_keys"] = [key for key in _UI_STATE.get("selected_row_keys", []) if key in available]
    return list(_UI_STATE["selected_row_keys"])


def _get_selected_rows(rows):
    available = _rows_by_key(rows)
    selected_row_keys = _sanitize_selected_row_keys(rows)
    return [available[key] for key in selected_row_keys if key in available]


def _write_state(progress_text, progress_percent, status_text, rows, selected_row_keys, detail_text):
    payload = {
        "resolution": _UI_STATE["resolution"],
        "open_level_only": bool(_UI_STATE["open_level_only"]),
        "override_only": bool(_UI_STATE["override_only"]),
        "sort_column": _UI_STATE["sort_column"],
        "sort_direction": _UI_STATE["sort_direction"],
        "progress_text": str(progress_text),
        "progress_percent": max(0.0, min(1.0, float(progress_percent))),
        "status_text": str(status_text),
        "rows": [_row_to_dict(row) for row in rows],
        "selected_row_keys": list(selected_row_keys),
        "detail_text": str(detail_text),
    }

    with open(_get_state_file_path(), "w", encoding="utf-8") as state_file:
        json.dump(payload, state_file, indent=2)

    with open(_get_status_file_path(), "w", encoding="utf-8") as status_file:
        status_file.write(str(status_text))

    for line in str(status_text).splitlines():
        unreal.log(line)


def _get_target_level_paths(backend):
    levels = backend.discover_levels()
    selected_level_paths = backend.get_selected_level_paths_from_editor(levels)
    current_level_path = backend.get_current_open_level_path()
    discovered_level_paths = {entry.level_path for entry in levels}

    normalized_current_level = None
    if current_level_path:
        normalized_current_level = backend.normalize_asset_level_path(current_level_path)

    if _UI_STATE["open_level_only"]:
        if normalized_current_level and normalized_current_level in discovered_level_paths:
            selected_level_paths = [normalized_current_level]
        else:
            selected_level_paths = []
    elif not selected_level_paths and normalized_current_level and normalized_current_level in discovered_level_paths:
        selected_level_paths = [normalized_current_level]

    return selected_level_paths, current_level_path


def _sort_rows(rows):
    sort_column = _UI_STATE["sort_column"]
    reverse = _UI_STATE["sort_direction"] == "Desc"

    def sort_key(row):
        if sort_column == "Level":
            return str(row.level_path).lower()
        if sort_column == "Actor":
            return str(row.actor_label).lower()
        if sort_column == "Component":
            return str(row.component_name).lower()
        if sort_column == "Mesh":
            return str(row.asset_name).lower()
        if sort_column == "Mobility":
            return str(row.mobility).lower()
        if sort_column == "Effective":
            return int(row.effective_light_map_resolution)
        if sort_column == "Asset":
            return int(row.asset_lightmap_resolution)
        if sort_column == "Override":
            return int(row.overridden_light_map_res if row.override_light_map_res else 0)
        return str(row.level_path).lower()

    return sorted(rows, key=sort_key, reverse=reverse)


def _load_rows(backend):
    selected_level_paths, current_level_path = _get_target_level_paths(backend)
    rows = backend.collect_selected_level_static_mesh_lightmap_rows(selected_level_paths) if selected_level_paths else []
    if _UI_STATE["override_only"]:
        rows = [row for row in rows if row.override_light_map_res]
    rows = _sort_rows(rows)
    return selected_level_paths, current_level_path, rows


def _build_detail_text(rows, selected_rows):
    if not rows:
        return "No static mesh rows loaded.\nSelect map assets in the Content Browser, or keep a level open, then click Refresh."

    if len(selected_rows) > 1:
        first_row = selected_rows[0]
        return "\n".join(
            (
                f"Selected rows: {len(selected_rows)}",
                f"First selected level: {first_row.level_path}",
                f"First selected actor: {first_row.actor_label}",
                f"First selected component: {first_row.component_name}",
                f"First selected effective resolution: {first_row.effective_light_map_resolution}",
                "Apply To Instance and Clear Instance Override affect Static mobility rows only.",
                "Open Level Only limits the visible rows to the currently open level.",
                "Override Only limits the visible rows to components with instance overrides enabled.",
                "Apply To Asset affects the first selected row's static mesh asset only.",
            )
        )

    if len(selected_rows) == 1:
        row = selected_rows[0]
        source_label = "Component override" if row.override_light_map_res else "Static mesh asset default"
        return "\n".join(
            (
                f"Level: {row.level_path}",
                f"Actor: {row.actor_label}",
                f"Actor Path: {row.actor_path}",
                f"Component: {row.component_name}",
                f"Component Path: {row.component_path}",
                f"Static Mesh: {row.asset_name}",
                f"Static Mesh Path: {row.asset_path}",
                f"Mobility: {row.mobility}",
                f"Effective Lightmap Resolution: {row.effective_light_map_resolution}",
                f"Asset Lightmap Resolution: {row.asset_lightmap_resolution}",
                f"Component Override Enabled: {row.override_light_map_res}",
                f"Component Override Resolution: {row.overridden_light_map_res}",
                f"Resolution Source: {source_label}",
            )
        )

    return "\n".join(
        (
            "Select a row to inspect or edit its lightmap resolution.",
            "Use Apply To Instance to set a per-level override on Static mobility rows.",
            "Enable Open Level Only to show only the currently open level.",
            "Enable Override Only to show only rows with instance overrides enabled.",
            "Use Apply To Asset to change the first selected static mesh asset default.",
        )
    )


def _build_status_text(title, selected_level_paths, current_level_path, rows, selected_rows, operation_lines=None):
    static_rows = [row for row in rows if str(row.mobility).strip().upper() == "STATIC"]
    override_rows = [row for row in rows if row.override_light_map_res]
    unique_assets = sorted({row.asset_path for row in rows}, key=str.casefold)

    lines = [
        str(title),
        f"Target levels: {len(selected_level_paths)}",
        f"Current open level: {current_level_path or 'None'}",
        f"Visible rows: {len(rows)}",
        f"Selected rows: {len(selected_rows)}",
        f"Static rows: {len(static_rows)}",
        f"Rows with instance override: {len(override_rows)}",
        f"Unique assets: {len(unique_assets)}",
        f"Sort: {_UI_STATE['sort_column']} {_UI_STATE['sort_direction']}",
        f"Filters: Open Level Only={_UI_STATE['open_level_only']} | Override Only={_UI_STATE['override_only']}",
        f"Resolution Input: {_UI_STATE['resolution']}",
    ]

    if selected_level_paths:
        lines.append("Targets: " + ", ".join(selected_level_paths))
    else:
        lines.append("Targets: None. Select map assets in the Content Browser, or keep a level open.")

    if operation_lines:
        lines.append("")
        lines.append("Operation log:")
        lines.extend(operation_lines)

    return "\n".join(lines)


def _emit_state(title, selected_level_paths, current_level_path, rows, operation_lines=None, progress_percent=0.0):
    selected_rows = _get_selected_rows(rows)
    selected_row_keys = [_row_key(row) for row in selected_rows]
    _write_state(
        title if title else "Idle",
        progress_percent,
        _build_status_text(title, selected_level_paths, current_level_path, rows, selected_rows, operation_lines),
        rows,
        selected_row_keys,
        _build_detail_text(rows, selected_rows),
    )


def _get_static_rows(rows):
    return [row for row in rows if str(row.mobility).strip().upper() == "STATIC"]


def _get_scoped_selected_rows(rows):
    return list(_get_selected_rows(rows))


def _get_first_selected_row(rows):
    selected_rows = _get_selected_rows(rows)
    return selected_rows[0] if selected_rows else None


def set_resolution(value):
    _set_resolution_value(value)


def set_open_level_only(value):
    _UI_STATE["open_level_only"] = str(value).strip().lower() in {"true", "1", "yes", "checked"}


def set_override_only(value):
    _UI_STATE["override_only"] = str(value).strip().lower() in {"true", "1", "yes", "checked"}


def set_sort(column, direction):
    _UI_STATE["sort_column"] = _normalize_sort_column(column)
    _UI_STATE["sort_direction"] = _normalize_sort_direction(direction)


def set_selected_rows(row_keys):
    if isinstance(row_keys, (list, tuple, set)):
        _UI_STATE["selected_row_keys"] = [str(key) for key in row_keys if str(key)]
    else:
        _UI_STATE["selected_row_keys"] = []
    refresh_status()


def refresh_status():
    backend = _load_backend_module()
    selected_level_paths, current_level_path, rows = _load_rows(backend)
    _emit_state(
        f"Ready: {len(rows)} visible rows, {len(rows)} scanned, {len(selected_level_paths)} levels, {len(_get_selected_rows(rows))} selected",
        selected_level_paths,
        current_level_path,
        rows,
    )


def apply_to_instance():
    backend = _load_backend_module()
    selected_level_paths, current_level_path, rows = _load_rows(backend)
    static_rows = _get_static_rows(_get_scoped_selected_rows(rows))
    if not static_rows:
        _emit_state("Select one or more Static rows first.", selected_level_paths, current_level_path, rows)
        return

    targets = [(row.level_path, row.actor_path, row.component_name) for row in static_rows]
    resolution = int(_UI_STATE["resolution"])
    success_count, result_lines, level_summary_lines, cancelled = backend.set_level_static_mesh_component_lightmap_resolution_batch(targets, resolution)
    refreshed_selected_level_paths, refreshed_current_level_path, refreshed_rows = _load_rows(backend)
    operation_lines = list(result_lines[:20]) or ["No operation messages were returned."]
    if level_summary_lines:
        operation_lines.append("")
        operation_lines.append("Per-level summary:")
        operation_lines.extend(level_summary_lines)
    suffix = " before cancellation" if cancelled else ""
    _emit_state(
        f"Applied instance override {resolution} to {success_count} row(s){suffix}.",
        refreshed_selected_level_paths,
        refreshed_current_level_path,
        refreshed_rows,
        operation_lines,
        progress_percent=1.0,
    )


def clear_instance_override():
    backend = _load_backend_module()
    selected_level_paths, current_level_path, rows = _load_rows(backend)
    scoped_rows = [row for row in _get_scoped_selected_rows(rows) if row.override_light_map_res]
    targets = [(row.level_path, row.actor_path, row.component_name) for row in scoped_rows]
    if not targets:
        _emit_state("Select one or more overridden rows first.", selected_level_paths, current_level_path, rows)
        return

    success_count, result_lines, level_summary_lines, cancelled = backend.clear_level_static_mesh_component_lightmap_resolution_override_batch(targets)
    refreshed_selected_level_paths, refreshed_current_level_path, refreshed_rows = _load_rows(backend)
    operation_lines = list(result_lines[:20]) or ["No operation messages were returned."]
    if level_summary_lines:
        operation_lines.append("")
        operation_lines.append("Per-level summary:")
        operation_lines.extend(level_summary_lines)
    suffix = " before cancellation" if cancelled else ""
    _emit_state(
        f"Cleared {success_count} instance override(s){suffix}.",
        refreshed_selected_level_paths,
        refreshed_current_level_path,
        refreshed_rows,
        operation_lines,
        progress_percent=1.0,
    )


def apply_to_asset():
    backend = _load_backend_module()
    selected_level_paths, current_level_path, rows = _load_rows(backend)
    first_row = _get_first_selected_row(rows)
    if first_row is None:
        _emit_state("Select a row first.", selected_level_paths, current_level_path, rows)
        return

    resolution = int(_UI_STATE["resolution"])
    success, message = backend.set_static_mesh_asset_lightmap_resolution(first_row.asset_path, resolution)
    refreshed_selected_level_paths, refreshed_current_level_path, refreshed_rows = _load_rows(backend)
    title = f"Applied asset lightmap resolution {resolution} to {first_row.asset_name}." if success else message
    _emit_state(
        title,
        refreshed_selected_level_paths,
        refreshed_current_level_path,
        refreshed_rows,
        [message],
        progress_percent=1.0,
    )


def open_selected_actor():
    backend = _load_backend_module()
    selected_level_paths, current_level_path, rows = _load_rows(backend)
    first_row = _get_first_selected_row(rows)
    if first_row is None:
        _emit_state("Select a row first.", selected_level_paths, current_level_path, rows)
        return

    success, message = backend.focus_static_mesh_lightmap_row(first_row.level_path, first_row.actor_path)
    _emit_state(message, selected_level_paths, current_level_path, rows, [] if success else [message], progress_percent=1.0)


def sync_selected_asset():
    backend = _load_backend_module()
    selected_level_paths, current_level_path, rows = _load_rows(backend)
    first_row = _get_first_selected_row(rows)
    if first_row is None:
        _emit_state("Select a row first.", selected_level_paths, current_level_path, rows)
        return

    success, message = backend.sync_content_browser_to_asset(first_row.asset_path)
    _emit_state(message, selected_level_paths, current_level_path, rows, [] if success else [message], progress_percent=1.0)


def apply_instance_override_64():
    set_resolution(64)
    apply_to_instance()


def apply_instance_override_128():
    set_resolution(128)
    apply_to_instance()


def clear_instance_overrides():
    clear_instance_override()


def apply_asset_resolution_64():
    set_resolution(64)
    apply_to_asset()


def apply_asset_resolution_128():
    set_resolution(128)
    apply_to_asset()


def open_first_actor():
    open_selected_actor()


def sync_first_asset():
    sync_selected_asset()