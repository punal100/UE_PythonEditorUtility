from copy import deepcopy


_SORT_COLUMNS = ("Asset", "Action", "Result", "Overlap", "Wrapping")
_SORT_DIRECTIONS = ("Asc", "Desc")


def _sample_rows(export_destination: str, import_source: str) -> list[dict]:
    return [
        {
            "key": "SM_WallPanel",
            "asset": "SM_WallPanel",
            "action": "Export",
            "result": "Exported",
            "overlap": "0.0%",
            "wrapping": "No",
            "asset_path": "/Game/Architecture/SM_WallPanel",
            "source_file": export_destination,
            "target_path": "/Game/Architecture/SM_WallPanel",
            "issues": [],
        },
        {
            "key": "SM_WindowFrame",
            "asset": "SM_WindowFrame",
            "action": "Reimport",
            "result": "Risk",
            "overlap": "8.4%",
            "wrapping": "Yes",
            "asset_path": "/Game/Architecture/SM_WindowFrame",
            "source_file": import_source,
            "target_path": "/Game/Architecture/SM_WindowFrame",
            "issues": ["UV channel 1 still overlaps after import."],
        },
        {
            "key": "SM_FloorTile",
            "asset": "SM_FloorTile",
            "action": "Import",
            "result": "OK",
            "overlap": "0.0%",
            "wrapping": "No",
            "asset_path": "/Game/Architecture/SM_FloorTile",
            "source_file": import_source,
            "target_path": "/Game/Architecture/SM_FloorTile",
            "issues": [],
        },
    ]


def _sort_rows(rows: list[dict], sort_column: str, sort_direction: str) -> list[dict]:
    normalized_column = sort_column if sort_column in _SORT_COLUMNS else "Result"
    reverse = sort_direction == "Desc"

    def sort_key(row: dict):
        if normalized_column == "Overlap":
            return float(str(row["overlap"]).replace("%", ""))
        if normalized_column == "Wrapping":
            return 1 if row["wrapping"] == "Yes" else 0
        return str(row[normalized_column.lower()]).casefold()

    return sorted(rows, key=sort_key, reverse=reverse)


def build_pipeline_snapshot(
    export_source: str,
    export_destination: str,
    import_source: str,
    import_destination: str,
    risks_only: bool,
    sort_column: str,
    sort_direction: str,
    selected_row_keys: list[str],
    operation_result: dict | None = None,
) -> dict:
    rows = deepcopy(_sample_rows(export_destination, import_source))
    selected_set = {str(key) for key in selected_row_keys or []}

    if operation_result and operation_result.get("operation") == "Export All":
        rows[0]["result"] = "Exported"
    elif operation_result and operation_result.get("operation") == "Import/Reimport All":
        rows[1]["action"] = "Reimport"
        rows[2]["action"] = "Import"

    if risks_only:
        rows = [row for row in rows if row["result"] == "Risk" or row["issues"]]

    rows = _sort_rows(rows, sort_column, sort_direction if sort_direction in _SORT_DIRECTIONS else "Desc")
    selected_rows = [row for row in rows if row["key"] in selected_set]

    summary = {
        "processed": len(rows),
        "exported": sum(1 for row in rows if row["result"] == "Exported"),
        "imported_new": sum(1 for row in rows if row["action"] == "Import"),
        "reimported_existing": sum(1 for row in rows if row["action"] == "Reimport"),
        "failed": sum(1 for row in rows if row["result"] == "Failed"),
        "risky": sum(1 for row in rows if row["result"] == "Risk"),
    }
    if operation_result:
        summary.update({key: operation_result.get(key, value) for key, value in summary.items()})

    report_path = export_destination
    operation_label = operation_result.get("operation") if operation_result else "Refresh"
    operation_message = operation_result.get("message") if operation_result else "Refreshed the example static mesh audit view."

    detail_lines = [
        f"Operation: {operation_label}",
        f"Export source: {export_source}",
        f"Export destination: {export_destination}",
        f"Import source: {import_source}",
        f"Import destination: {import_destination}",
        f"Risks only: {bool(risks_only)}",
        f"Sort: {sort_column if sort_column in _SORT_COLUMNS else 'Result'} {sort_direction if sort_direction in _SORT_DIRECTIONS else 'Desc'}",
        f"Report path: {report_path}",
        "",
        operation_message,
    ]
    if selected_rows:
        first = selected_rows[0]
        detail_lines.extend(
            [
                "",
                f"Selected asset: {first['asset']}",
                f"Selected result: {first['result']}",
                f"Selected issues: {', '.join(first['issues']) or 'None'}",
            ]
        )

    status_lines = [
        "Static Mesh Pipeline",
        f"Rows: {len(rows)}",
        f"Risks: {summary['risky']}",
        operation_message,
    ]

    return {
        "progress_text": "Completed" if operation_result else "Ready",
        "progress_percent": 1.0 if operation_result else 0.0,
        "status_text": "\n".join(status_lines),
        "detail_text": "\n".join(detail_lines),
        "summary": summary,
        "rows": rows,
        "selected_row_keys": [row["key"] for row in selected_rows],
    }
