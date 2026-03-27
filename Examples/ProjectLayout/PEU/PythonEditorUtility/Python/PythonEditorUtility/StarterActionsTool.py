import json
import os

import unreal

from .ProjectIntegration import get_default_workspace_root, get_state_dir, get_state_file_path, get_status_file_path, load_script_module


_STATUS_FILE_NAME = "StarterActionsStatus.txt"
_STATE_FILE_NAME = "StarterActionsState.json"
_DEFAULT_STATE = {
    "workspace_name": "SampleWorkspace",
    "workspace_root": "",
    "template_type": "Operations",
    "include_samples": True,
    "notes": "Replace this text with project-specific notes.",
    "summary_text": "Use project-owned widgets and scripts to preview or apply an integration workflow without editing plugin source.",
    "preview_text": "Generate a preview to inspect the project-owned plan.",
    "result_text": "Apply Starter Plan routes into a project-owned script. Replace that script with your real automation.",
    "progress_percent": 0.0,
}


def _get_state_file_path():
    return get_state_file_path(_STATE_FILE_NAME)


def _get_status_file_path():
    return get_status_file_path(_STATUS_FILE_NAME)


def _load_backend_module():
    return load_script_module("starter_workflow_backend", "starter_workflow.py")


def _read_state():
    if not os.path.isfile(_get_state_file_path()):
        return dict(_DEFAULT_STATE)

    try:
        with open(_get_state_file_path(), "r", encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return dict(_DEFAULT_STATE)

    merged = dict(_DEFAULT_STATE)
    merged.update(state)
    return merged


def _write_state(overrides=None):
    state = _read_state()
    if overrides:
        state.update(overrides)

    os.makedirs(get_state_dir(), exist_ok=True)
    with open(_get_state_file_path(), "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)

    status_lines = [
        str(state["summary_text"]),
        "",
        str(state["preview_text"]),
        "",
        str(state["result_text"]),
    ]
    with open(_get_status_file_path(), "w", encoding="utf-8") as handle:
        handle.write("\n".join(status_lines))

    for line in status_lines:
        if line:
            unreal.log(line)


def _coerce_workspace_name(workspace_name):
    value = str(workspace_name or "").strip()
    return value or _DEFAULT_STATE["workspace_name"]


def _coerce_template_type(template_type):
    value = str(template_type or "").strip()
    return value or _DEFAULT_STATE["template_type"]


def _coerce_workspace_root(workspace_root):
    value = str(workspace_root or "").strip()
    return value or get_default_workspace_root()


def _coerce_notes(notes):
    value = str(notes or "").strip()
    return value or _DEFAULT_STATE["notes"]


def bootstrap(json_path):
    json_label = os.path.basename(str(json_path or "").strip()) or "the tool definition"
    _write_state(
        {
            "summary_text": "Starter actions are ready. This tab demonstrates project-owned controller logic and widget placeholders.",
            "preview_text": f"InitPyCmd loaded {json_label}.",
            "result_text": "Apply Starter Plan routes into a project-owned script. Replace that script with your real automation.",
            "progress_percent": 0.1,
        }
    )


def refresh_status():
    _write_state({"summary_text": _read_state()["summary_text"]})


def set_workspace_name(workspace_name):
    _write_state({"workspace_name": _coerce_workspace_name(workspace_name), "summary_text": "Workspace name updated from a bound text widget."})


def set_workspace_root(workspace_root):
    normalized_root = _coerce_workspace_root(workspace_root)
    _write_state({"workspace_root": normalized_root, "summary_text": f"Workspace root updated to {normalized_root}."})


def use_project_root():
    normalized_root = get_default_workspace_root()
    _write_state({"workspace_root": normalized_root, "summary_text": f"Workspace root reset to the project directory: {normalized_root}."})


def set_template_type(template_type):
    _write_state({"template_type": _coerce_template_type(template_type), "summary_text": "Template selection updated from a bound combo box."})


def set_include_samples(include_samples):
    _write_state({"include_samples": bool(include_samples), "summary_text": "Sample-content preference updated from a bound check box."})


def set_notes(notes):
    _write_state({"notes": _coerce_notes(notes), "summary_text": "Notes updated from a bound text widget."})


def generate_preview(workspace_name, workspace_root, template_type, include_samples, notes):
    payload = _load_backend_module().build_preview(
        workspace_name=_coerce_workspace_name(workspace_name),
        workspace_root=_coerce_workspace_root(workspace_root),
        template_type=_coerce_template_type(template_type),
        include_samples=bool(include_samples),
        notes=_coerce_notes(notes),
    )
    _write_state(payload)


def apply_changes(workspace_name, workspace_root, template_type, include_samples, notes):
    payload = _load_backend_module().apply_plan(
        workspace_name=_coerce_workspace_name(workspace_name),
        workspace_root=_coerce_workspace_root(workspace_root),
        template_type=_coerce_template_type(template_type),
        include_samples=bool(include_samples),
        notes=_coerce_notes(notes),
    )
    _write_state(payload)


def reset_form():
    _write_state(_load_backend_module().reset_plan())