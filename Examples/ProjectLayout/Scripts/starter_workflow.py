def _normalize_workspace_name(workspace_name):
    value = str(workspace_name or "").strip()
    return value or "SampleWorkspace"


def _normalize_template_type(template_type):
    value = str(template_type or "").strip()
    return value or "Operations"


def _normalize_workspace_root(workspace_root):
    value = str(workspace_root or "").strip()
    return value or "<project dir>"


def _normalize_notes(notes):
    value = str(notes or "").strip()
    return value or "Replace this text with project-specific notes."


def build_preview(workspace_name, workspace_root, template_type, include_samples, notes):
    normalized_workspace_name = _normalize_workspace_name(workspace_name)
    normalized_workspace_root = _normalize_workspace_root(workspace_root)
    normalized_template_type = _normalize_template_type(template_type)
    normalized_notes = _normalize_notes(notes)
    sample_label = "include" if include_samples else "skip"

    preview_lines = [
        f"Preview for {normalized_workspace_name}",
        f"Workspace root: {normalized_workspace_root}",
        f"Template: {normalized_template_type}",
        f"Sample content: {sample_label}",
        "",
        "Suggested project-owned changes:",
        "- add or rename UI JSON files under PEU/PythonEditorUtility/UI/",
        "- update controllers under PEU/PythonEditorUtility/Python/PythonEditorUtility/",
        "- wire backend behavior through Scripts/",
        "",
        f"Notes: {normalized_notes}",
    ]

    return {
        "workspace_name": normalized_workspace_name,
        "workspace_root": normalized_workspace_root,
        "template_type": normalized_template_type,
        "include_samples": bool(include_samples),
        "notes": normalized_notes,
        "summary_text": f"Preview ready for {normalized_workspace_name}.",
        "preview_text": "\n".join(preview_lines),
        "result_text": "No project-owned automation has run yet.",
        "progress_percent": 0.55,
    }


def apply_plan(workspace_name, workspace_root, template_type, include_samples, notes):
    normalized_workspace_name = _normalize_workspace_name(workspace_name)
    normalized_workspace_root = _normalize_workspace_root(workspace_root)
    normalized_template_type = _normalize_template_type(template_type)
    normalized_notes = _normalize_notes(notes)
    sample_label = "with sample content" if include_samples else "without sample content"

    result_lines = [
        f"Applied starter plan for {normalized_workspace_name}.",
        f"Workspace root: {normalized_workspace_root}",
        f"Template: {normalized_template_type} {sample_label}.",
        "",
        "This example does not write project files.",
        "Replace starter_workflow.py with your project-owned automation so this button can call real scripts.",
        "",
        f"Notes carried into the project-owned adapter: {normalized_notes}",
    ]

    return {
        "workspace_name": normalized_workspace_name,
        "workspace_root": normalized_workspace_root,
        "template_type": normalized_template_type,
        "include_samples": bool(include_samples),
        "notes": normalized_notes,
        "summary_text": f"Project-owned action routed for {normalized_workspace_name}.",
        "preview_text": "Preview preserved. Run Generate Preview again after you adjust the widgets.",
        "result_text": "\n".join(result_lines),
        "progress_percent": 1.0,
    }


def reset_plan():
    return {
        "workspace_name": "SampleWorkspace",
        "workspace_root": "<project dir>",
        "template_type": "Operations",
        "include_samples": True,
        "notes": "Replace this text with project-specific notes.",
        "summary_text": "Starter actions reset to the neutral defaults.",
        "preview_text": "Generate a preview to inspect the project-owned plan.",
        "result_text": "Apply Starter Plan routes into a project-owned script. Replace that script with your real automation.",
        "progress_percent": 0.0,
    }