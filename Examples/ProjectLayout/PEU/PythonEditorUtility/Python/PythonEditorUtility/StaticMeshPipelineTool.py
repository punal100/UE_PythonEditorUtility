import importlib.util
import json
import os

import unreal


_SORT_COLUMNS = ("Asset", "Action", "Result", "Overlap", "Wrapping")
_SORT_DIRECTIONS = ("Asc", "Desc")
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


def _get_state_dir():
    project_dir = os.path.abspath(os.path.normpath(unreal.Paths.project_dir()))
    state_dir = os.path.join(project_dir, "PEU", "PythonEditorUtility", "State")
    os.makedirs(state_dir, exist_ok=True)
    return state_dir


def _get_status_file_path():
    return os.path.join(_get_state_dir(), "StaticMeshPipelineStatus.txt")


def _get_state_file_path():
    return os.path.join(_get_state_dir(), "StaticMeshPipelineState.json")


def _get_project_dir():
    return os.path.abspath(os.path.normpath(unreal.Paths.project_dir()))


def _load_script_module(module_name: str, script_file_name: str):
    script_path = os.path.join(_get_project_dir(), "Scripts", script_file_name)
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load script module from {script_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_export_module():
    return _load_script_module("bulk_export_static_meshes_runtime_for_peu", "bulk_export_static_meshes.py")


def _load_import_module():
    return _load_script_module("bulk_reimport_static_meshes_runtime_for_peu", "bulk_reimport_static_meshes.py")


def _normalize_sort_column(value):
    normalized = str(value or "").strip()
    return normalized if normalized in _SORT_COLUMNS else "Result"


def _normalize_sort_direction(value):
    normalized = str(value or "").strip()
    return normalized if normalized in _SORT_DIRECTIONS else "Desc"


def _normalize_asset_folder(value, fallback):
    normalized = str(value or fallback or "").strip().replace("\\", "/")
    if not normalized:
        return str(fallback or "")
    if normalized.startswith("/Game"):
        return normalized.rstrip("/") or "/Game"
    return normalized


def _normalize_filesystem_folder(value, fallback):
    candidate = str(value or fallback or "").strip()
    if not candidate:
        return str(fallback or "")
    return os.path.abspath(os.path.normpath(candidate))


def _ensure_default_paths():
    export_module = _load_export_module()
    import_module = _load_import_module()
    if not _UI_STATE["export_source"]:
        _UI_STATE["export_source"] = _normalize_asset_folder(export_module.SOURCE, export_module.SOURCE)
    if not _UI_STATE["export_destination"]:
        _UI_STATE["export_destination"] = _normalize_filesystem_folder(export_module.DESTINATION, export_module.DESTINATION)
    if not _UI_STATE["import_source"]:
        _UI_STATE["import_source"] = _normalize_filesystem_folder(import_module.SOURCE, import_module.SOURCE)
    if not _UI_STATE["import_destination"]:
        _UI_STATE["import_destination"] = _normalize_asset_folder(import_module.DESTINATION, import_module.DESTINATION)


def _load_saved_state():
    _ensure_default_paths()
    try:
        with open(_get_state_file_path(), "r", encoding="utf-8") as state_file:
            payload = json.load(state_file)
    except Exception:
        return

    _UI_STATE["risks_only"] = bool(payload.get("risks_only", False))
    _UI_STATE["sort_column"] = _normalize_sort_column(payload.get("sort_column"))
    _UI_STATE["sort_direction"] = _normalize_sort_direction(payload.get("sort_direction"))
    _UI_STATE["export_source"] = _normalize_asset_folder(payload.get("export_source"), _UI_STATE["export_source"])
    _UI_STATE["export_destination"] = _normalize_filesystem_folder(payload.get("export_destination"), _UI_STATE["export_destination"])
    _UI_STATE["import_source"] = _normalize_filesystem_folder(payload.get("import_source"), _UI_STATE["import_source"])
    _UI_STATE["import_destination"] = _normalize_asset_folder(payload.get("import_destination"), _UI_STATE["import_destination"])
    _UI_STATE["selected_row_keys"] = [str(key) for key in payload.get("selected_row_keys", [])]


def _format_overlap(value) -> str:
    if value is None:
        return "-"
    return f"{float(value):.1f}%"


def _format_wrapping(value: bool) -> str:
    return "Yes" if value else "No"


def _row_key(row: dict[str, object]) -> str:
    return str(row.get("key") or row.get("asset_path") or row.get("source_file") or "")


def _row_to_dict(row: dict[str, object]) -> dict[str, str]:
    return {
        "key": _row_key(row),
        "asset": str(row.get("asset_name") or ""),
        "action": str(row.get("action") or ""),
        "result": str(row.get("result") or ""),
        "overlap": _format_overlap(row.get("overlap_percentage")),
        "wrapping": _format_wrapping(bool(row.get("wrapping_uvs") or False)),
        "asset_path": str(row.get("asset_path") or ""),
        "source_file": str(row.get("source_file") or ""),
        "target_path": str(row.get("target_path") or ""),
        "import_generate_lightmap_uvs": str(row.get("import_generate_lightmap_uvs") or ""),
        "lod0_generate_lightmap_uvs": str(row.get("lod0_generate_lightmap_uvs") or ""),
        "issues": [str(issue) for issue in row.get("issues", [])],
    }


def _rows_by_key(rows: list[dict[str, object]]):
    return {_row_key(row): row for row in rows}


def _sanitize_selected_row_keys(rows: list[dict[str, object]]):
    available = _rows_by_key(rows)
    _UI_STATE["selected_row_keys"] = [key for key in _UI_STATE.get("selected_row_keys", []) if key in available]
    return list(_UI_STATE["selected_row_keys"])


def _get_selected_rows(rows: list[dict[str, object]]):
    available = _rows_by_key(rows)
    return [available[key] for key in _sanitize_selected_row_keys(rows) if key in available]


def _sort_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    sort_column = _UI_STATE["sort_column"]
    reverse = _UI_STATE["sort_direction"] == "Desc"

    def sort_key(row: dict[str, object]):
        if sort_column == "Asset":
            return str(row.get("asset_name") or "").casefold()
        if sort_column == "Action":
            return str(row.get("action") or "").casefold()
        if sort_column == "Result":
            ranking = {"failed": 0, "risk": 1, "ok": 2, "exported": 3}
            return ranking.get(str(row.get("result") or "").lower(), 99)
        if sort_column == "Overlap":
            overlap = row.get("overlap_percentage")
            return -1.0 if overlap is None else float(overlap)
        if sort_column == "Wrapping":
            return 1 if row.get("wrapping_uvs") else 0
        return str(row.get("asset_name") or "").casefold()

    return sorted(rows, key=sort_key, reverse=reverse)


def _filter_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    if not _UI_STATE["risks_only"]:
        return rows

    filtered_rows = []
    for row in rows:
        if str(row.get("result") or "").lower() in {"risk", "failed"}:
            filtered_rows.append(row)
            continue
        if row.get("issues"):
            filtered_rows.append(row)
            continue
        if row.get("overlap_percentage") is not None:
            try:
                if float(row["overlap_percentage"]) > 0.0:
                    filtered_rows.append(row)
                    continue
            except Exception:
                pass
    return filtered_rows


def _default_status_lines():
    _ensure_default_paths()
    return [
        "Static Mesh Pipeline",
        f"Export source: {_UI_STATE['export_source']}",
        f"Export destination: {_UI_STATE['export_destination']}",
        f"Import source: {_UI_STATE['import_source']}",
        f"Import destination: {_UI_STATE['import_destination']}",
        "Use Export All to write project static meshes to the exchange folder.",
        "Use Import/Reimport All to pull FBX/OBJ files back into the project and surface the lightmap audit summary here.",
    ]


def _build_detail_text(rows: list[dict[str, object]], selected_rows: list[dict[str, object]], summary: dict[str, object], report_path: str, operation: str):
    if not rows:
        return "\n".join(_default_status_lines())

    if len(selected_rows) > 1:
        first_row = selected_rows[0]
        return "\n".join(
            (
                f"Selected rows: {len(selected_rows)}",
                f"First asset: {first_row.get('asset_name')}",
                f"First result: {first_row.get('result')}",
                f"Current operation: {operation}",
                f"Report path: {report_path or 'None'}",
            )
        )

    if len(selected_rows) == 1:
        row = selected_rows[0]
        issues = row.get("issues") or []
        lines = [
            f"Asset: {row.get('asset_name')}",
            f"Action: {row.get('action')}",
            f"Result: {row.get('result')}",
            f"Asset Path: {row.get('asset_path')}",
            f"Source File: {row.get('source_file') or 'None'}",
            f"Target Path: {row.get('target_path') or 'None'}",
            f"Overlap: {_format_overlap(row.get('overlap_percentage'))}",
            f"Wrapping UVs: {_format_wrapping(bool(row.get('wrapping_uvs') or False))}",
            f"Import Generate Lightmap UVs: {row.get('import_generate_lightmap_uvs') or '-'}",
            f"LOD0 Generate Lightmap UVs: {row.get('lod0_generate_lightmap_uvs') or '-'}",
        ]
        if issues:
            lines.append("Issues:")
            lines.extend([f"- {issue}" for issue in issues])
        else:
            lines.append("Issues: None")
        return "\n".join(lines)

    return "\n".join(
        (
            f"Current operation: {operation}",
            f"Processed rows: {len(rows)}",
            f"Risks only filter: {_UI_STATE['risks_only']}",
            f"Sort: {_UI_STATE['sort_column']} {_UI_STATE['sort_direction']}",
            f"Report path: {report_path or 'None'}",
            f"Processed: {summary.get('processed', 0)}",
            f"Exported: {summary.get('exported', 0)}",
            f"Imported new: {summary.get('imported_new', 0)}",
            f"Reimported existing: {summary.get('reimported_existing', 0)}",
            f"Failed: {summary.get('failed', 0)}",
            f"Risky: {summary.get('risky', 0)}",
        )
    )


def _write_state(progress_text: str, progress_percent: float, status_lines: list[str], rows: list[dict[str, object]], summary: dict[str, object], operation: str, report_path: str):
    selected_row_keys = _sanitize_selected_row_keys(rows)
    selected_rows = _get_selected_rows(rows)
    detail_text = _build_detail_text(rows, selected_rows, summary, report_path, operation)
    payload = {
        "risks_only": bool(_UI_STATE["risks_only"]),
        "sort_column": _UI_STATE["sort_column"],
        "sort_direction": _UI_STATE["sort_direction"],
        "export_source": _UI_STATE["export_source"],
        "export_destination": _UI_STATE["export_destination"],
        "import_source": _UI_STATE["import_source"],
        "import_destination": _UI_STATE["import_destination"],
        "progress_text": str(progress_text),
        "progress_percent": max(0.0, min(1.0, float(progress_percent))),
        "status_text": "\n".join(str(line) for line in status_lines),
        "operation": str(operation),
        "report_path": str(report_path or ""),
        "summary": summary,
        "rows": [_row_to_dict(row) for row in rows],
        "selected_row_keys": selected_row_keys,
        "detail_text": detail_text,
    }

    with open(_get_state_file_path(), "w", encoding="utf-8") as state_file:
        json.dump(payload, state_file, indent=2)

    with open(_get_status_file_path(), "w", encoding="utf-8") as status_file:
        status_file.write(payload["status_text"])

    for line in payload["status_text"].splitlines():
        unreal.log(line)


def _load_existing_payload() -> dict[str, object]:
    try:
        with open(_get_state_file_path(), "r", encoding="utf-8") as state_file:
            return json.load(state_file)
    except Exception:
        return {}


def _build_summary_from_payload(payload: dict[str, object]) -> dict[str, object]:
    return dict(payload.get("summary") or {})


def refresh_status():
    _load_saved_state()
    payload = _load_existing_payload()
    rows = payload.get("rows") or []
    normalized_rows = []
    for row in rows:
        normalized_rows.append(
            {
                "key": str(row.get("key") or ""),
                "asset_name": str(row.get("asset") or ""),
                "asset_path": str(row.get("asset_path") or ""),
                "source_file": str(row.get("source_file") or ""),
                "target_path": str(row.get("target_path") or ""),
                "action": str(row.get("action") or ""),
                "result": str(row.get("result") or ""),
                "overlap_percentage": None if row.get("overlap") in {None, "", "-"} else str(row.get("overlap")).replace("%", ""),
                "wrapping_uvs": str(row.get("wrapping") or "").lower() == "yes",
                "import_generate_lightmap_uvs": str(row.get("import_generate_lightmap_uvs") or ""),
                "lod0_generate_lightmap_uvs": str(row.get("lod0_generate_lightmap_uvs") or ""),
                "issues": [str(issue) for issue in row.get("issues", [])],
            }
        )

    filtered_rows = _sort_rows(_filter_rows(normalized_rows))
    summary = _build_summary_from_payload(payload)
    _UI_STATE["export_source"] = _normalize_asset_folder(payload.get("export_source"), _UI_STATE["export_source"])
    _UI_STATE["export_destination"] = _normalize_filesystem_folder(payload.get("export_destination"), _UI_STATE["export_destination"])
    _UI_STATE["import_source"] = _normalize_filesystem_folder(payload.get("import_source"), _UI_STATE["import_source"])
    _UI_STATE["import_destination"] = _normalize_asset_folder(payload.get("import_destination"), _UI_STATE["import_destination"])
    status_lines = payload.get("status_text", "").splitlines() if payload.get("status_text") else _default_status_lines()
    progress_text = "Idle"
    progress_percent = 0.0
    _write_state(progress_text, progress_percent, status_lines, filtered_rows, summary, str(payload.get("operation") or "idle"), str(payload.get("report_path") or ""))


def _run_export():
    export_module = _load_export_module()
    result = export_module.run_bulk_export(
        source_folder=_UI_STATE["export_source"],
        destination_root=_UI_STATE["export_destination"],
    )
    summary = {
        "processed": int(result.get("processed", 0)),
        "exported": int(result.get("exported", 0)),
        "imported_new": 0,
        "reimported_existing": 0,
        "failed": int(result.get("failed", 0)),
        "risky": int(result.get("failed", 0)),
        "overlap_warnings": 0,
    }
    rows = _sort_rows(_filter_rows(list(result.get("rows") or [])))
    progress_text = f"Exported {summary['exported']} of {summary['processed']} meshes"
    progress_percent = 1.0 if summary["processed"] else 0.0
    _write_state(progress_text, progress_percent, list(result.get("status_lines") or _default_status_lines()), rows, summary, "export", "")


def _run_import():
    import_module = _load_import_module()
    result = import_module.run_bulk_reimport(
        source_root=_UI_STATE["import_source"],
        destination_root=_UI_STATE["import_destination"],
        show_dialog=False,
    )
    summary = {
        "processed": int(result.get("processed", 0)),
        "exported": 0,
        "imported_new": int(result.get("imported_new", 0)),
        "reimported_existing": int(result.get("reimported_existing", 0)),
        "failed": int(result.get("failed", 0)),
        "risky": int(result.get("risky", 0)),
        "overlap_warnings": int(result.get("overlap_warnings", 0)),
    }
    rows = _sort_rows(_filter_rows(list(result.get("rows") or [])))
    progress_text = f"Imported/Reimported {summary['processed']} meshes"
    progress_percent = 1.0 if summary["processed"] else 0.0
    _write_state(progress_text, progress_percent, list(result.get("status_lines") or _default_status_lines()), rows, summary, "import_reimport", str(result.get("report_path") or ""))


def run_export():
    _load_saved_state()
    _run_export()


def run_import_reimport():
    _load_saved_state()
    _run_import()


def set_risks_only(value: bool):
    _load_saved_state()
    _UI_STATE["risks_only"] = bool(value)
    refresh_status()


def set_sort(column: str, direction: str):
    _load_saved_state()
    _UI_STATE["sort_column"] = _normalize_sort_column(column)
    _UI_STATE["sort_direction"] = _normalize_sort_direction(direction)
    refresh_status()


def set_paths(export_source: str, export_destination: str, import_source: str, import_destination: str):
    _load_saved_state()
    _UI_STATE["export_source"] = _normalize_asset_folder(export_source, _UI_STATE["export_source"])
    _UI_STATE["export_destination"] = _normalize_filesystem_folder(export_destination, _UI_STATE["export_destination"])
    _UI_STATE["import_source"] = _normalize_filesystem_folder(import_source, _UI_STATE["import_source"])
    _UI_STATE["import_destination"] = _normalize_asset_folder(import_destination, _UI_STATE["import_destination"])
    refresh_status()


def set_selected_rows(selected_row_keys: list[str]):
    _load_saved_state()
    _UI_STATE["selected_row_keys"] = [str(key) for key in selected_row_keys]
    refresh_status()


def open_export_folder():
    _load_saved_state()
    os.startfile(_UI_STATE["export_destination"])
    refresh_status()


def open_import_source_folder():
    _load_saved_state()
    os.startfile(_UI_STATE["import_source"])
    refresh_status()


def open_last_audit_report():
    payload = _load_existing_payload()
    report_path = str(payload.get("report_path") or "")
    if report_path and os.path.isfile(report_path):
        os.startfile(report_path)
        refresh_status()
        return

    _write_state(
        "Idle",
        0.0,
        _default_status_lines() + ["No audit report is available yet."],
        [],
        {"processed": 0, "exported": 0, "imported_new": 0, "reimported_existing": 0, "failed": 0, "risky": 0, "overlap_warnings": 0},
        "idle",
        "",
    )


_load_saved_state()