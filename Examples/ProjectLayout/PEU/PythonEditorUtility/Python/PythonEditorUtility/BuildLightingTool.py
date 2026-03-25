import importlib.util
import os

import unreal


def _get_status_file_path():
    project_dir = os.path.abspath(os.path.normpath(unreal.Paths.project_dir()))
    state_dir = os.path.join(project_dir, "PEU", "PythonEditorUtility", "State")
    os.makedirs(state_dir, exist_ok=True)
    return os.path.join(state_dir, "BuildLightingStatus.txt")


def _load_backend_module():
    project_dir = os.path.abspath(os.path.normpath(unreal.Paths.project_dir()))
    script_path = os.path.join(project_dir, "Scripts", "build_level_lighting.py")
    spec = importlib.util.spec_from_file_location("build_level_lighting_backend", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load build lighting backend from {script_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _log_lines(lines):
    for line in lines:
        unreal.log(str(line))


def _set_status(lines):
    if isinstance(lines, str):
        text = lines
        iterable = [lines]
    else:
        iterable = [str(line) for line in lines]
        text = "\n".join(iterable)

    with open(_get_status_file_path(), "w", encoding="utf-8") as status_file:
        status_file.write(text)

    _log_lines(iterable)


def refresh_status():
    backend = _load_backend_module()
    levels = backend.discover_levels()
    current_level = backend.get_current_open_level_path()
    options, options_path = backend.load_native_lighting_options()
    lines = [
        "Build Lighting",
        "",
        f"Discovered levels: {len(levels)}",
        f"Current open level: {current_level or 'None'}",
        f"Options file: {options_path}",
    ]
    lines.extend(backend.describe_lighting_options(options))
    _set_status(lines)


def run_precheck():
    backend = _load_backend_module()
    levels = backend.discover_levels()
    issue_map = backend.scan_levels_for_prebuild_issues(levels)
    generated_at = backend.save_precheck_cache(levels, issue_map)
    lines = ["Build Lighting", "", f"Precheck snapshot: {generated_at}"]
    if not issue_map:
        lines.append("No levels found for precheck.")
        _set_status(lines)
        return
    for level_path, result in issue_map.items():
        if result.blockers:
            lines.append(f"BLOCKED {level_path}: {'; '.join(result.blockers)}")
        if result.warnings:
            lines.append(f"WARN {level_path}: {'; '.join(result.warnings)}")
    _set_status(lines)


def build_lighting():
    backend = _load_backend_module()
    levels = backend.discover_levels()
    current_level = backend.get_current_open_level_path()
    if not levels:
        _set_status(["Build Lighting", "", "Build not started: no project levels discovered."])
        return
    options, _options_path = backend.load_native_lighting_options()
    issue_map = backend.scan_levels_for_prebuild_issues(levels)
    generated_at = backend.save_precheck_cache(levels, issue_map)
    selection = backend.BuildSelection([entry.level_path for entry in levels], options, dict(issue_map), "python_editor_utility", generated_at)
    _set_status(["Build Lighting", "", "Starting lighting build..."])
    backend.execute_build_selection(selection, current_level)
    refresh_status()


def audit_static_meshes():
    _load_backend_module().run_static_mesh_lightmap_audit()
    refresh_status()


def open_lightmap_resolution_inspector():
    backend = _load_backend_module()
    success, message = backend.launch_python_editor_utility_lightmap_resolution_tool()
    if success:
        _set_status(["Build Lighting", "", message])
        return

    fallback_message = (
        "Lightmap Resolution\n\n"
        "PythonEditorUtility could not open the Lightmap Resolution tab automatically.\n"
        "Use Window > Python Editor Utility > Lightmap Resolution, or use the native Unreal dialog at Build > Lighting Info > LightMap Resolution Adjustment.\n\n"
        f"{backend.get_native_lighting_tools_message()}"
    )
    if hasattr(unreal, "EditorDialog"):
        unreal.EditorDialog.show_message("Lightmap Resolution", fallback_message, unreal.AppMsgType.OK)
    _set_status(["Build Lighting", "", fallback_message])


def open_options_file():
    backend = _load_backend_module()
    options_path = backend.get_native_options_path()
    if not os.path.isfile(options_path):
        backend.load_native_lighting_options()
    os.startfile(options_path)
    _set_status(["Build Lighting", "", f"Opened options file: {options_path}"])


def apply_density_settings():
    backend = _load_backend_module()
    options, _options_path = backend.load_native_lighting_options()
    success, message = backend.apply_lightmap_density_settings(options)
    if success:
        _set_status(["Build Lighting", "", message])
    else:
        _set_status(["Build Lighting", "", message])


def activate_lightmap_density_view():
    _result, message = _load_backend_module().activate_lightmap_density_view()
    _set_status(["Build Lighting", "", message])


def activate_lighting_only_view():
    _result, message = _load_backend_module().activate_lighting_only_view()
    _set_status(["Build Lighting", "", message])


def activate_lit_view():
    _result, message = _load_backend_module().activate_lit_view()
    _set_status(["Build Lighting", "", message])


def show_native_lighting_actions():
    message = _load_backend_module().get_native_lighting_tools_message()
    _set_status(["Build Lighting", "", message])