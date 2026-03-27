import os


def _list_named_files(directory_path, extension):
    if not os.path.isdir(directory_path):
        return []
    return sorted(name for name in os.listdir(directory_path) if name.endswith(extension))


def collect_overview(json_path, integration_root, scripts_dir, state_dir):
    ui_dir = os.path.join(integration_root, "UI")
    controller_dir = os.path.join(integration_root, "Python", "PythonEditorUtility")
    ui_files = _list_named_files(ui_dir, ".json")
    controller_files = [name for name in _list_named_files(controller_dir, ".py") if name != "__init__.py"]
    script_files = _list_named_files(scripts_dir, ".py")

    json_label = os.path.basename(json_path) if json_path else "(default refresh_status path)"
    detail_lines = [
        "This neutral starter keeps project behavior in project-owned content.",
        "",
        f"InitPyCmd source: {json_label}",
        f"Integration root: {integration_root}",
        f"State folder: {state_dir}",
        "",
        "Discovered UI definitions:",
    ]
    detail_lines.extend(f"- {name}" for name in ui_files)
    detail_lines.append("")
    detail_lines.append("Project-owned controllers:")
    detail_lines.extend(f"- {name}" for name in controller_files)
    detail_lines.append("")
    detail_lines.append("Project-owned scripts:")
    detail_lines.extend(f"- {name}" for name in script_files)
    detail_lines.append("")
    detail_lines.append("Replace these files in your project integration layer. Do not modify plugin source.")

    return {
        "headline": "Standalone host ready",
        "summary_text": "This starter demonstrates dynamic discovery, InitPyCmd, state binding, and project-owned adapter calls.",
        "tool_count_text": f"Starter tools discovered: {len(ui_files)}",
        "contract_text": "Do not modify plugin source. Replace the project-owned UI, controllers, and scripts in your own project.",
        "detail_text": "\n".join(detail_lines),
        "progress_percent": 0.5 if ui_files else 0.0,
        "status_lines": [
            "Starter overview refreshed.",
            f"UI definitions: {len(ui_files)}",
            f"Controllers: {len(controller_files)}",
            f"Scripts: {len(script_files)}",
        ],
    }


def make_reset_payload(integration_root, scripts_dir, state_dir):
    return collect_overview("", integration_root, scripts_dir, state_dir)