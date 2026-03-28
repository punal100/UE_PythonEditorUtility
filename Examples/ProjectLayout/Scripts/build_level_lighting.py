import os
from copy import deepcopy

from project_path_utils import get_project_dir, get_project_name


_PROJECT_NAME = get_project_name(__file__)
_OPTIONS_FILE = os.path.join(get_project_dir(__file__), "Config", "DefaultEditor.ini")
_SORT_COLUMNS = ("Level", "Actor", "Mesh", "Effective", "Asset", "Override")
_SORT_DIRECTIONS = ("Asc", "Desc")


def _sample_levels() -> list[str]:
    return [
        f"/Game/Maps/{_PROJECT_NAME}_Lobby",
        f"/Game/Maps/{_PROJECT_NAME}_Lighting",
    ]


def _sample_rows() -> list[dict]:
    rows = [
        {
            "key": "lobby||BP_LampCluster||SM_LampPost",
            "level": _sample_levels()[0],
            "actor": "BP_LampCluster",
            "actor_path": f"{_sample_levels()[0]}.BP_LampCluster",
            "mesh": "SM_LampPost",
            "asset_path": "/Game/Props/Lighting/SM_LampPost",
            "mobility": "Static",
            "effective": 128,
            "asset": 128,
            "override": "-",
        },
        {
            "key": "lighting||SM_Archway_A||SM_Archway_A",
            "level": _sample_levels()[1],
            "actor": "SM_Archway_A",
            "actor_path": f"{_sample_levels()[1]}.SM_Archway_A",
            "mesh": "SM_Archway_A",
            "asset_path": "/Game/Architecture/SM_Archway_A",
            "mobility": "Static",
            "effective": 64,
            "asset": 64,
            "override": "-",
        },
        {
            "key": "lighting||BP_WindowSet||SM_WindowFrame",
            "level": _sample_levels()[1],
            "actor": "BP_WindowSet",
            "actor_path": f"{_sample_levels()[1]}.BP_WindowSet",
            "mesh": "SM_WindowFrame",
            "asset_path": "/Game/Architecture/SM_WindowFrame",
            "mobility": "Static",
            "effective": 96,
            "asset": 64,
            "override": "96",
        },
    ]
    return rows


def _sort_rows(rows: list[dict], sort_column: str, sort_direction: str) -> list[dict]:
    normalized_column = sort_column if sort_column in _SORT_COLUMNS else "Level"
    reverse = sort_direction == "Desc"

    def sort_key(row: dict):
        if normalized_column in {"Effective", "Asset"}:
            return int(row[normalized_column.lower()])
        if normalized_column == "Override":
            return -1 if row["override"] == "-" else int(row["override"])
        return str(row[normalized_column.lower()]).casefold()

    return sorted(rows, key=sort_key, reverse=reverse)


def _selected_rows(rows: list[dict], selected_row_keys: list[str]) -> list[dict]:
    selected = []
    wanted = {str(key) for key in selected_row_keys or []}
    for row in rows:
        if row["key"] in wanted:
            selected.append(row)
    return selected


def build_refresh_snapshot() -> dict:
    levels = _sample_levels()
    detail_lines = [
        "Build Lighting",
        "",
        f"Discovered levels: {len(levels)}",
        f"Current open level: {levels[0]}",
        f"Options file: {_OPTIONS_FILE}",
        "Live project parity points:",
        "- Run Precheck before a build",
        "- Link out to Lightmap Resolution for per-mesh adjustments",
        "- Keep project policy in Scripts/build_level_lighting.py",
    ]
    return {
        "progress_text": "Ready",
        "progress_percent": 0.0,
        "summary_text": f"Discovered levels: {len(levels)}",
        "current_level_text": f"Current open level: {levels[0]}",
        "options_file_text": f"Options file: {_OPTIONS_FILE}",
        "status_text": "\n".join(detail_lines),
        "detail_text": "\n".join(detail_lines),
    }


def build_precheck_snapshot() -> dict:
    payload = build_refresh_snapshot()
    lines = payload["detail_text"].splitlines()
    lines.extend(
        [
            "",
            "Precheck snapshot:",
            f"- {_sample_levels()[0]}: No blockers",
            f"- {_sample_levels()[1]}: Warning - Example Lightmass Importance Volume is undersized",
        ]
    )
    payload["progress_text"] = "Precheck complete"
    payload["progress_percent"] = 1.0
    payload["summary_text"] = "Precheck levels: 2 | Blockers: 0 | Warnings: 1"
    payload["status_text"] = "\n".join(lines)
    payload["detail_text"] = payload["status_text"]
    return payload


def build_run_snapshot() -> dict:
    payload = build_refresh_snapshot()
    lines = payload["detail_text"].splitlines()
    lines.extend(
        [
            "",
            "Build result:",
            "- Queued 2 levels",
            "- Simulated Production quality bake",
            "- Post-build audit surfaced 1 mesh with a manual override",
        ]
    )
    payload["progress_text"] = "Completed"
    payload["progress_percent"] = 1.0
    payload["summary_text"] = "Queued levels: 2 | Example build complete"
    payload["status_text"] = "\n".join(lines)
    payload["detail_text"] = payload["status_text"]
    return payload


def build_options_snapshot() -> dict:
    payload = build_refresh_snapshot()
    payload["progress_text"] = "Options file"
    payload["progress_percent"] = 1.0
    payload["summary_text"] = f"Options file: {_OPTIONS_FILE}"
    payload["status_text"] = payload["detail_text"] + f"\n\nOpen the project lighting settings file at {_OPTIONS_FILE}."
    payload["detail_text"] = payload["status_text"]
    return payload


def build_native_actions_snapshot() -> dict:
    payload = build_refresh_snapshot()
    payload["progress_text"] = "Native actions"
    payload["progress_percent"] = 1.0
    payload["summary_text"] = "Native lighting actions overview"
    payload["status_text"] = payload["detail_text"] + "\n\nNative Unreal references:\n- Build > Build Lighting Only\n- Build > Lighting Info\n- View Mode > Lightmap Density"
    payload["detail_text"] = payload["status_text"]
    return payload


def build_lightmap_snapshot(
    resolution: str,
    open_level_only: bool,
    override_only: bool,
    sort_column: str,
    sort_direction: str,
    selected_row_keys: list[str],
    action: str = "refresh",
) -> dict:
    rows = deepcopy(_sample_rows())
    normalized_resolution = str(max(1, int(str(resolution or "64").strip() or "64")))

    if open_level_only:
        current_level = _sample_levels()[1]
        rows = [row for row in rows if row["level"] == current_level]

    selected_key_set = {str(key) for key in selected_row_keys or []}
    if action == "apply_instance":
        for row in rows:
            if row["key"] in selected_key_set:
                row["override"] = normalized_resolution
                row["effective"] = int(normalized_resolution)
    elif action == "clear_instance_override":
        for row in rows:
            if row["key"] in selected_key_set:
                row["override"] = "-"
                row["effective"] = int(row["asset"])
    elif action == "apply_asset":
        for row in rows:
            if row["key"] in selected_key_set:
                row["asset"] = int(normalized_resolution)
                if row["override"] == "-":
                    row["effective"] = int(normalized_resolution)

    if override_only:
        rows = [row for row in rows if row["override"] != "-"]

    rows = _sort_rows(rows, sort_column, sort_direction if sort_direction in _SORT_DIRECTIONS else "Asc")
    selected_rows = _selected_rows(rows, list(selected_key_set))

    action_text = {
        "refresh": "Refreshed example lightmap rows.",
        "apply_instance": f"Applied instance override {normalized_resolution} to {len(selected_rows)} row(s).",
        "clear_instance_override": f"Cleared instance overrides for {len(selected_rows)} row(s).",
        "apply_asset": f"Updated asset default to {normalized_resolution} for {len(selected_rows)} row(s).",
        "open_selected_actor": "Open Selected Actor would focus the first selected actor in the editor.",
        "sync_selected_asset": "Sync Selected Asset would focus the first selected static mesh asset.",
    }.get(action, "Refreshed example lightmap rows.")

    detail_lines = [
        f"Resolution input: {normalized_resolution}",
        f"Visible rows: {len(rows)}",
        f"Selected rows: {len(selected_rows)}",
        f"Sort: {sort_column if sort_column in _SORT_COLUMNS else 'Level'} {sort_direction if sort_direction in _SORT_DIRECTIONS else 'Asc'}",
        f"Filters: Open Level Only={bool(open_level_only)} | Override Only={bool(override_only)}",
        "",
        action_text,
    ]
    if selected_rows:
        first = selected_rows[0]
        detail_lines.extend(
            [
                "",
                f"First selected actor: {first['actor']}",
                f"First selected mesh: {first['mesh']}",
                f"First selected asset path: {first['asset_path']}",
            ]
        )

    status_lines = [
        "Lightmap Resolution",
        f"Visible rows: {len(rows)}",
        f"Selected rows: {len(selected_rows)}",
        action_text,
    ]

    return {
        "resolution": normalized_resolution,
        "open_level_only": bool(open_level_only),
        "override_only": bool(override_only),
        "sort_column": sort_column if sort_column in _SORT_COLUMNS else "Level",
        "sort_direction": sort_direction if sort_direction in _SORT_DIRECTIONS else "Asc",
        "progress_text": "Ready",
        "progress_percent": 1.0 if action != "refresh" else 0.0,
        "status_text": "\n".join(status_lines),
        "rows": rows,
        "selected_row_keys": [row["key"] for row in selected_rows],
        "detail_text": "\n".join(detail_lines),
    }
