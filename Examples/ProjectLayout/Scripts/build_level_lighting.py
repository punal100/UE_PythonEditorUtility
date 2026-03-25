import importlib.util
import os
import json
import time
from datetime import datetime
from dataclasses import dataclass, field

import unreal


MAP_EXTENSION = ".umap"
CONTENT_ROOT = "/Game"
LIGHTING_QUALITY_OPTIONS = ["Preview", "Medium", "High", "Production", "MAX"]
DEFAULT_LIGHTING_QUALITY = "Production"
LIGHTMAP_DENSITY_DEFAULT_MIN = 0.0
LIGHTMAP_DENSITY_DEFAULT_IDEAL = 0.2
LIGHTMAP_DENSITY_DEFAULT_MAX = 0.8
LIGHTMAP_DENSITY_DEFAULT_COLOR_SCALE = 1.0
LIGHTMAP_DENSITY_DEFAULT_GRAYSCALE_SCALE = 1.0
ERROR_COLORING_SUPPORTED_QUALITIES = {"Preview", "Medium"}
MESSAGE_LOG_NAME_ALIASES = {
    "Lighting Results": "LightingResults",
    "LightingResults": "LightingResults",
    "Map Check": "MapCheck",
    "MapCheck": "MapCheck",
}
_MESSAGE_LOG_WARNING_SHOWN = False
_STATIC_MESH_AUDIT_HELPER_MODULE = None
_STATIC_MESH_AUDIT_SCRIPT_MODULE = None
_STATIC_MESH_AUDIT_CACHE: dict[str, tuple[bool, list[str], dict[str, object]]] = {}
STATIC_MESH_LIGHTMAP_AUDIT_WARNING_LIMIT = 5
_ACTIVE_BUILD_LIGHTING_QT_WINDOW = None
PEU_OPEN_BUILD_LIGHTING_COMMAND = "PEU:OpenBuildLighting"
PEU_OPEN_LIGHTMAP_RESOLUTION_COMMAND = "PEU:OpenLightmapResolution"
LIGHTMAP_WIDGET_EXCLUDED_ACTOR_CLASSES = (
    "InstancedFoliageActor",
    "LandscapeProxy",
    "LandscapeStreamingProxy",
)
LIGHTMAP_WIDGET_EXCLUDED_ACTOR_NAME_TOKENS = (
    "hlod",
    "worldpartitionhlod",
    "lodactor",
)
LIGHTMAP_WIDGET_EXCLUDED_COMPONENT_CLASS_TOKENS = (
    "landscapemeshproxycomponent",
    "meshproxycomponent",
)

# Exact phrases are based on Epic's lightmapping docs plus observed UE editor logs.
LIGHTING_LOG_CATEGORIES = (
    "lightingresults:",
    "logstaticlightingsystem:",
    "mapcheck:",
)

LIGHTING_RELEVANT_PATTERNS = (
    "overlapping lightmap uv warning",
    "wrapping uv warning",
    "object has overlapping uvs.",
    "lightmap uv are overlapping by",
    "object has wrapping uvs.",
    "object has wrapping uv",
    "no importance volume found, so the scene bounding box was used.",
    "no reflection capture actors found",
    "reflection captures need to be rebuilt",
    "enable error coloring to visualize",
)

LIGHTING_WARNING_PATTERNS = (
    "object has overlapping uvs.",
    "lightmap uv are overlapping by",
    "object has wrapping uvs.",
    "object has wrapping uv",
    "no importance volume found, so the scene bounding box was used.",
    "no reflection capture actors found",
    "reflection captures need to be rebuilt",
    "enable error coloring to visualize",
)


@dataclass(frozen=True)
class LevelEntry:
    name: str
    level_path: str
    file_path: str


@dataclass(frozen=True)
class LightingToolOptions:
    lighting_quality: str = DEFAULT_LIGHTING_QUALITY
    with_reflection_captures: bool = False
    open_lightmap_density_view: bool = False
    min_lightmap_density: float = LIGHTMAP_DENSITY_DEFAULT_MIN
    ideal_lightmap_density: float = LIGHTMAP_DENSITY_DEFAULT_IDEAL
    max_lightmap_density: float = LIGHTMAP_DENSITY_DEFAULT_MAX
    lightmap_density_color_scale: float = LIGHTMAP_DENSITY_DEFAULT_COLOR_SCALE
    lightmap_density_grayscale_scale: float = LIGHTMAP_DENSITY_DEFAULT_GRAYSCALE_SCALE
    render_lightmap_density_grayscale: bool = False


@dataclass(frozen=True)
class BuildSelection:
    level_paths: list[str]
    lighting_options: LightingToolOptions = field(default_factory=LightingToolOptions)
    issue_map: dict[str, "LevelPrecheckResult"] | None = None
    precheck_source_label: str = ""
    precheck_generated_at: str | None = None


@dataclass(frozen=True)
class LevelBuildResult:
    level_path: str
    success: bool
    warnings: list[str]
    error: str | None = None
    native_warnings: list[str] | None = None
    native_errors: list[str] | None = None


@dataclass(frozen=True)
class LevelPrecheckResult:
    level_path: str
    blockers: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class StaticMeshLightmapRow:
    level_path: str
    actor_label: str
    actor_path: str
    component_name: str
    component_path: str
    asset_name: str
    asset_path: str
    mobility: str
    asset_lightmap_resolution: int
    override_light_map_res: bool
    overridden_light_map_res: int
    effective_light_map_resolution: int


def normalize_level_path(level_path: str) -> str:
    return level_path.replace("\\", "/")


def get_project_content_dir() -> str:
    return os.path.abspath(os.path.normpath(unreal.Paths.project_content_dir()))


def get_project_dir() -> str:
    return os.path.abspath(os.path.normpath(unreal.Paths.project_dir()))


def get_project_log_dir() -> str:
    if hasattr(unreal.Paths, "project_log_dir"):
        try:
            return os.path.abspath(os.path.normpath(unreal.Paths.project_log_dir()))
        except Exception:
            pass

    return os.path.abspath(os.path.join(get_project_dir(), "Saved", "Logs"))


def get_precheck_cache_path() -> str:
    return os.path.abspath(os.path.join(get_project_dir(), "Saved", "BuildLighting_PrecheckCache.json"))


def get_native_options_path() -> str:
    return os.path.abspath(os.path.join(get_project_dir(), "Saved", "BuildLighting_NativeOptions.json"))


def get_project_name() -> str:
    project_dir = get_project_dir()
    return os.path.basename(os.path.normpath(project_dir))


def get_scripts_dir() -> str:
    return os.path.abspath(os.path.dirname(__file__))


def launch_python_editor_utility_tool(command: str, tool_label: str) -> tuple[bool, str]:
    if not command:
        return False, f"No command was provided for {tool_label}."

    if execute_editor_console_command(command):
        return True, f"Opened {tool_label}."

    return False, f"PythonEditorUtility command was not available for {tool_label}: {command}"


def launch_python_editor_utility_build_lighting_tool() -> tuple[bool, str]:
    return launch_python_editor_utility_tool(PEU_OPEN_BUILD_LIGHTING_COMMAND, "PythonEditorUtility Build Lighting")


def launch_python_editor_utility_lightmap_resolution_tool() -> tuple[bool, str]:
    return launch_python_editor_utility_tool(
        PEU_OPEN_LIGHTMAP_RESOLUTION_COMMAND,
        "PythonEditorUtility Lightmap Resolution",
    )


def load_script_module(module_name: str, script_file_name: str):
    script_path = os.path.join(get_scripts_dir(), script_file_name)
    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")

    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load Python module spec from {script_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_static_mesh_audit_helper_module():
    global _STATIC_MESH_AUDIT_HELPER_MODULE

    if _STATIC_MESH_AUDIT_HELPER_MODULE is None:
        _STATIC_MESH_AUDIT_HELPER_MODULE = load_script_module(
            "bulk_reimport_static_meshes_runtime_for_build_lighting",
            "bulk_reimport_static_meshes.py",
        )

    return _STATIC_MESH_AUDIT_HELPER_MODULE


def get_static_mesh_audit_script_module():
    global _STATIC_MESH_AUDIT_SCRIPT_MODULE

    if _STATIC_MESH_AUDIT_SCRIPT_MODULE is None:
        _STATIC_MESH_AUDIT_SCRIPT_MODULE = load_script_module(
            "audit_static_mesh_lightmaps_runtime_for_build_lighting",
            "audit_static_mesh_lightmaps.py",
        )

    return _STATIC_MESH_AUDIT_SCRIPT_MODULE


def normalize_asset_path(asset_path: str) -> str:
    normalized = normalize_level_path(asset_path.strip())
    if "." in normalized:
        normalized = normalized.split(".", 1)[0]
    return normalized


def is_content_asset_path(asset_path: str) -> bool:
    normalized_asset_path = normalize_asset_path(asset_path)
    return normalized_asset_path.startswith("/Game/")


def get_actor_static_mesh_components(actor) -> list:
    if actor is None or not hasattr(unreal, "StaticMeshComponent"):
        return []

    try:
        components = list(actor.get_components_by_class(unreal.StaticMeshComponent))
    except Exception:
        return []

    spline_mesh_component_class = getattr(unreal, "SplineMeshComponent", None)
    if spline_mesh_component_class is None:
        return components

    filtered_components = []
    for component in components:
        try:
            if isinstance(component, spline_mesh_component_class):
                continue
        except Exception:
            pass

        if not should_show_component_in_lightmap_widget(actor, component):
            continue

        filtered_components.append(component)

    return filtered_components


def get_component_static_mesh(component):
    if component is None:
        return None

    for getter in (
        lambda: component.get_editor_property("static_mesh"),
        lambda: component.static_mesh,
    ):
        try:
            static_mesh = getter()
        except Exception:
            continue

        if isinstance(static_mesh, unreal.StaticMesh):
            return static_mesh

    return None


def get_component_owner(component):
    if component is None:
        return None

    actor_type = getattr(unreal, "Actor", None)

    for getter in (
        lambda: component.get_owner(),
        lambda: component.get_outer(),
    ):
        try:
            candidate = getter()
        except Exception:
            continue

        if candidate is None:
            continue

        if actor_type is None:
            return candidate

        try:
            if isinstance(candidate, actor_type):
                return candidate
        except Exception:
            continue

    return None


def get_object_path_name(obj) -> str | None:
    if obj is None:
        return None

    for getter in (
        lambda: obj.get_path_name(),
        lambda: obj.get_name(),
    ):
        try:
            candidate = getter()
            if candidate:
                return str(candidate)
        except Exception:
            continue

    return None


def get_object_class_name(obj) -> str:
    if obj is None:
        return ""

    for getter in (
        lambda: obj.get_class().get_name(),
        lambda: obj.get_class().get_path_name(),
        lambda: type(obj).__name__,
    ):
        try:
            candidate = getter()
            if candidate:
                return str(candidate)
        except Exception:
            continue

    return ""


def get_actor_label(actor) -> str:
    if actor is None:
        return ""

    for getter in (
        lambda: actor.get_actor_label(),
        lambda: actor.get_name(),
    ):
        try:
            candidate = getter()
            if candidate:
                return str(candidate)
        except Exception:
            continue

    return ""


def actor_is_instance_of(actor, class_name: str) -> bool:
    if actor is None:
        return False

    actor_class = getattr(unreal, class_name, None)
    if actor_class is None:
        return False

    try:
        return isinstance(actor, actor_class)
    except Exception:
        return False


def is_hidden_in_editor(actor) -> bool:
    if actor is None:
        return False

    for getter in (
        lambda: actor.is_hidden_ed(),
        lambda: actor.is_temporarily_hidden_in_editor(),
        lambda: actor.get_editor_property("hidden"),
        lambda: actor.get_editor_property("is_temporarily_hidden_in_editor"),
    ):
        try:
            return bool(getter())
        except Exception:
            continue

    return False


def is_editor_only_actor(actor) -> bool:
    return bool(get_bool_editor_property(actor, ("is_editor_only_actor", "is_editor_only")) or False)


def text_contains_any_token(value: str, tokens: tuple[str, ...]) -> bool:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return False

    return any(token in normalized for token in tokens)


def is_generated_hlod_actor(actor) -> bool:
    actor_identity = "\n".join(
        (
            get_actor_label(actor),
            get_object_path_name(actor) or "",
            get_object_class_name(actor),
        )
    )
    return text_contains_any_token(actor_identity, LIGHTMAP_WIDGET_EXCLUDED_ACTOR_NAME_TOKENS)


def should_show_actor_in_lightmap_widget(actor) -> bool:
    if actor is None:
        return False

    if is_editor_only_actor(actor) or is_hidden_in_editor(actor):
        return False

    for class_name in LIGHTMAP_WIDGET_EXCLUDED_ACTOR_CLASSES:
        if actor_is_instance_of(actor, class_name):
            return False

    if is_generated_hlod_actor(actor):
        return False

    return bool(get_object_path_name(actor))


def should_show_component_in_lightmap_widget(actor, component) -> bool:
    if component is None:
        return False

    if not should_show_actor_in_lightmap_widget(get_component_owner(component) or actor):
        return False

    component_identity = "\n".join(
        (
            str(component.get_name()),
            get_object_path_name(component) or "",
            get_object_class_name(component),
        )
    )
    return not text_contains_any_token(component_identity, LIGHTMAP_WIDGET_EXCLUDED_COMPONENT_CLASS_TOKENS)


def format_editor_enum_name(value) -> str:
    if value is None:
        return "Unknown"

    enum_name = getattr(value, "name", None)
    if enum_name:
        return str(enum_name)

    text = str(value)
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    if ":" in text:
        text = text.split(":", 1)[0]
    text = text.strip("<>")
    return text


def get_component_static_mesh_asset_path(component) -> str | None:
    if component is None:
        return None

    static_mesh = get_component_static_mesh(component)
    if static_mesh is None or not isinstance(static_mesh, unreal.StaticMesh):
        return None

    for getter in (
        lambda: static_mesh.get_path_name(),
        lambda: static_mesh.get_name(),
    ):
        try:
            candidate = getter()
            if candidate and str(candidate).startswith("/"):
                return normalize_asset_path(str(candidate))
        except Exception:
            continue

    return None


def get_level_static_mesh_asset_paths(actors: list) -> list[str]:
    asset_paths: set[str] = set()

    for actor in actors:
        for component in get_actor_static_mesh_components(actor):
            asset_path = get_component_static_mesh_asset_path(component)
            if asset_path:
                asset_paths.add(asset_path)

    return sorted(asset_paths, key=str.casefold)


def build_static_mesh_lightmap_row(level_path: str, actor, component) -> StaticMeshLightmapRow | None:
    display_actor = get_component_owner(component) or actor
    if not should_show_component_in_lightmap_widget(display_actor, component):
        return None

    static_mesh = get_component_static_mesh(component)
    asset_path = get_component_static_mesh_asset_path(component)
    if static_mesh is None or not asset_path:
        return None

    resolved_level_path = get_actor_level_path(display_actor) or get_actor_level_path(actor) or level_path

    asset_resolution = get_int_editor_property(static_mesh, ("light_map_resolution",)) or 0
    override_enabled = bool(get_bool_editor_property(component, ("override_light_map_res",)) or False)
    override_resolution = get_int_editor_property(component, ("overridden_light_map_res",)) or 0
    effective_resolution = override_resolution if override_enabled and override_resolution > 0 else asset_resolution

    mobility_value = None
    try:
        mobility_value = component.get_editor_property("mobility")
    except Exception:
        mobility_value = None

    return StaticMeshLightmapRow(
        level_path=normalize_asset_level_path(resolved_level_path),
        actor_label=get_actor_label(display_actor),
        actor_path=get_object_path_name(display_actor) or "",
        component_name=str(component.get_name()),
        component_path=get_object_path_name(component) or "",
        asset_name=str(static_mesh.get_name()),
        asset_path=asset_path,
        mobility=format_editor_enum_name(mobility_value),
        asset_lightmap_resolution=int(asset_resolution),
        override_light_map_res=override_enabled,
        overridden_light_map_res=int(override_resolution),
        effective_light_map_resolution=int(effective_resolution),
    )


def collect_level_static_mesh_lightmap_rows(level_path: str, actors: list) -> list[StaticMeshLightmapRow]:
    rows: list[StaticMeshLightmapRow] = []
    normalized_level_path = normalize_asset_level_path(level_path)

    for actor in actors:
        if not should_show_actor_in_lightmap_widget(actor):
            continue

        actor_level_path = get_actor_level_path(actor)
        if actor_level_path is not None and not are_level_paths_equal(actor_level_path, normalized_level_path):
            continue

        for component in get_actor_static_mesh_components(actor):
            row = build_static_mesh_lightmap_row(normalized_level_path, actor, component)
            if row is not None:
                rows.append(row)

    rows.sort(key=lambda row: (row.level_path.lower(), row.actor_label.lower(), row.component_name.lower(), row.asset_name.lower()))
    return rows


def collect_selected_level_static_mesh_lightmap_rows(level_paths: list[str]) -> list[StaticMeshLightmapRow]:
    rows: list[StaticMeshLightmapRow] = []
    original_level_path = get_current_open_level_path()
    original_loaded_level_paths = get_loaded_level_paths_in_editor_world()
    normalized_level_paths: list[str] = []

    for level_path in level_paths:
        normalized_level_path = normalize_asset_level_path(level_path)
        if normalized_level_path not in normalized_level_paths:
            normalized_level_paths.append(normalized_level_path)

    try:
        for level_path in normalized_level_paths:
            if level_path in original_loaded_level_paths:
                rows.extend(collect_level_static_mesh_lightmap_rows(level_path, get_all_level_actors()))
                continue

            ensure_level_loaded(level_path)
            rows.extend(collect_level_static_mesh_lightmap_rows(level_path, get_all_level_actors()))
    finally:
        restore_original_level(original_level_path, "lightmap inspector")

    rows.sort(key=lambda row: (row.level_path.lower(), row.actor_label.lower(), row.component_name.lower(), row.asset_name.lower()))
    return rows


def find_actor_by_path(actor_path: str):
    normalized_target = str(actor_path or "")
    if not normalized_target:
        return None

    for actor in get_all_level_actors():
        if get_object_path_name(actor) == normalized_target:
            return actor

    return None


def get_actor_level_path(actor) -> str | None:
    if actor is None:
        return None

    for getter in (
        lambda: actor.get_level().get_path_name(),
        lambda: actor.get_level().get_outer().get_path_name(),
        lambda: actor.get_outer().get_path_name(),
        lambda: actor.get_path_name().split(":", 1)[0],
    ):
        try:
            candidate = getter()
            if candidate:
                return normalize_asset_level_path(str(candidate))
        except Exception:
            continue

    return None


def find_actor_by_path_in_level(actor_path: str, level_path: str | None):
    actor = find_actor_by_path(actor_path)
    if actor is None:
        return None

    if not level_path:
        return actor

    actor_level_path = get_actor_level_path(actor)
    if actor_level_path is None:
        return actor

    if are_level_paths_equal(actor_level_path, level_path):
        return actor

    return None


def find_or_load_actor_by_path(level_path: str, actor_path: str):
    actor = find_actor_by_path_in_level(actor_path, level_path)
    if actor is not None:
        return actor, False

    ensure_level_loaded(level_path)
    return find_actor_by_path_in_level(actor_path, level_path), True


def find_static_mesh_component_on_actor(actor, component_name: str):
    if actor is None:
        return None

    for component in get_actor_static_mesh_components(actor):
        try:
            if str(component.get_name()) == component_name:
                return component
        except Exception:
            continue

    return None


def focus_static_mesh_lightmap_row(level_path: str, actor_path: str) -> tuple[bool, str]:
    try:
        actor, _loaded_level = find_or_load_actor_by_path(level_path, actor_path)
        if actor is None:
            return False, f"Could not find actor in {level_path}: {actor_path}"

        editor_actor_subsystem = getattr(unreal, "EditorActorSubsystem", None)
        if editor_actor_subsystem is not None:
            try:
                subsystem = unreal.get_editor_subsystem(editor_actor_subsystem)
                if subsystem is not None and hasattr(subsystem, "set_selected_level_actors"):
                    subsystem.set_selected_level_actors([actor])
            except Exception:
                pass

        invalidate_level_viewports()
        return True, f"Opened {level_path} and selected {get_actor_label(actor)}."
    except Exception as error:
        return False, f"Could not focus actor for {level_path}: {error}"


def sync_content_browser_to_asset(asset_path: str) -> tuple[bool, str]:
    normalized_asset_path = normalize_asset_path(asset_path)
    if hasattr(unreal, "EditorAssetLibrary") and hasattr(unreal.EditorAssetLibrary, "sync_browser_to_objects"):
        try:
            unreal.EditorAssetLibrary.sync_browser_to_objects([normalized_asset_path])
            return True, f"Selected asset in Content Browser: {normalized_asset_path}"
        except Exception as error:
            return False, f"Could not select asset in Content Browser: {error}"

    return False, "Content Browser sync is not available in this editor session."


def set_static_mesh_asset_lightmap_resolution(asset_path: str, lightmap_resolution: int) -> tuple[bool, str]:
    normalized_asset_path = normalize_asset_path(asset_path)
    resolution = int(lightmap_resolution)
    if resolution <= 0:
        return False, "Lightmap resolution must be greater than zero."

    if not is_content_asset_path(normalized_asset_path):
        return False, f"Apply To Asset only supports project assets under /Game: {normalized_asset_path}"

    static_mesh = unreal.load_asset(normalized_asset_path)
    if static_mesh is None or not isinstance(static_mesh, unreal.StaticMesh):
        return False, f"Could not load static mesh asset: {normalized_asset_path}"

    if not set_editor_property_value(static_mesh, ("light_map_resolution",), resolution):
        return False, f"Could not set light map resolution on asset: {normalized_asset_path}"

    invalidate_level_viewports()
    return True, f"Set static mesh asset lightmap resolution to {resolution}: {normalized_asset_path}"


def set_level_static_mesh_component_lightmap_resolution(
    level_path: str,
    actor_path: str,
    component_name: str,
    lightmap_resolution: int,
) -> tuple[bool, str]:
    resolution = int(lightmap_resolution)
    if resolution <= 0:
        return False, "Lightmap resolution must be greater than zero."

    original_level_path = get_current_open_level_path()

    try:
        actor, loaded_level = find_or_load_actor_by_path(level_path, actor_path)
        if actor is None:
            return False, f"Could not find actor in {level_path}: {actor_path}"

        component = find_static_mesh_component_on_actor(actor, component_name)
        if component is None:
            return False, f"Could not find static mesh component on actor: {component_name}"

        override_set = set_editor_property_value(component, ("override_light_map_res",), True)
        resolution_set = set_editor_property_value(component, ("overridden_light_map_res",), resolution)
        if not override_set or not resolution_set:
            return False, f"Could not set component lightmap override for {component_name}"

        if loaded_level:
            save_current_level()

        invalidate_level_viewports()
        return True, f"Set level override to {resolution} on {component_name} in {level_path}"
    except Exception as error:
        return False, f"Could not set component lightmap override in {level_path}: {error}"
    finally:
        restore_original_level(original_level_path, "component lightmap resolution update")


def _group_static_mesh_component_targets_by_level(
    targets: list[tuple[str, str, str]],
) -> dict[str, list[tuple[str, str]]]:
    grouped_targets: dict[str, list[tuple[str, str]]] = {}

    for level_path, actor_path, component_name in targets:
        normalized_level_path = normalize_asset_level_path(level_path)
        grouped_targets.setdefault(normalized_level_path, []).append((str(actor_path), str(component_name)))

    return grouped_targets


def _format_static_mesh_component_batch_level_summaries(
    level_stats: dict[str, dict[str, int]],
) -> list[str]:
    summary_lines: list[str] = []

    for level_path in sorted(level_stats.keys(), key=str.casefold):
        stats = level_stats[level_path]
        summary_lines.append(
            f"{level_path}: {stats['success']} updated, {stats['failed']} failed"
        )

    return summary_lines


def set_level_static_mesh_component_lightmap_resolution_batch(
    targets: list[tuple[str, str, str]],
    lightmap_resolution: int,
    progress_callback=None,
) -> tuple[int, list[str], list[str], bool]:
    resolution = int(lightmap_resolution)
    if resolution <= 0:
        return 0, ["Lightmap resolution must be greater than zero."], [], False

    grouped_targets = _group_static_mesh_component_targets_by_level(targets)
    if not grouped_targets:
        return 0, ["No static mesh component targets were provided."], [], False

    total_targets = sum(len(level_targets) for level_targets in grouped_targets.values())
    success_count = 0
    processed_count = 0
    cancelled = False
    result_lines: list[str] = []
    level_stats = {
        level_path: {"success": 0, "failed": 0}
        for level_path in grouped_targets.keys()
    }
    original_level_path = get_current_open_level_path()
    original_loaded_level_paths = get_loaded_level_paths_in_editor_world()
    ordered_level_paths = sorted(
        grouped_targets.keys(),
        key=lambda level_path: (level_path not in original_loaded_level_paths, level_path.casefold()),
    )

    if progress_callback is not None:
        try:
            progress_callback(0, total_targets, "Preparing instance lightmap update...")
        except Exception:
            pass

    try:
        with unreal.ScopedSlowTask(total_targets, "Changing static mesh lightmap overrides") as slow_task:
            slow_task.make_dialog(True)

            for level_path in ordered_level_paths:
                level_targets = grouped_targets[level_path]
                if hasattr(slow_task, "should_cancel") and slow_task.should_cancel():
                    cancelled = True
                    result_lines.append("Cancelled instance lightmap update.")
                    break

                level_was_loaded = False
                if level_targets:
                    first_actor_path, _first_component_name = level_targets[0]
                    _first_actor, level_was_loaded = find_or_load_actor_by_path(level_path, first_actor_path)

                if progress_callback is not None:
                    try:
                        load_action = "Using loaded" if not level_was_loaded else "Loaded"
                        progress_callback(processed_count, total_targets, f"{load_action} {level_path}. Applying {len(level_targets)} instance changes...")
                    except Exception:
                        pass

                for actor_path, component_name in level_targets:
                    if hasattr(slow_task, "should_cancel") and slow_task.should_cancel():
                        cancelled = True
                        result_lines.append("Cancelled instance lightmap update.")
                        break

                    slow_task.enter_progress_frame(1, f"Apply {component_name} in {level_path}")

                    actor = find_actor_by_path_in_level(actor_path, level_path)
                    if actor is None:
                        level_stats[level_path]["failed"] += 1
                        result_lines.append(f"Could not find actor in {level_path}: {actor_path}")
                        processed_count += 1
                        if progress_callback is not None:
                            try:
                                progress_callback(processed_count, total_targets, f"Processed {processed_count}/{total_targets}: {level_path}")
                            except Exception:
                                pass
                        continue

                    component = find_static_mesh_component_on_actor(actor, component_name)
                    if component is None:
                        level_stats[level_path]["failed"] += 1
                        result_lines.append(f"Could not find static mesh component on actor: {component_name}")
                        processed_count += 1
                        if progress_callback is not None:
                            try:
                                progress_callback(processed_count, total_targets, f"Processed {processed_count}/{total_targets}: {level_path}")
                            except Exception:
                                pass
                        continue

                    override_set = set_editor_property_value(component, ("override_light_map_res",), True)
                    resolution_set = set_editor_property_value(component, ("overridden_light_map_res",), resolution)
                    if not override_set or not resolution_set:
                        level_stats[level_path]["failed"] += 1
                        result_lines.append(f"Could not set component lightmap override for {component_name}")
                        processed_count += 1
                        if progress_callback is not None:
                            try:
                                progress_callback(processed_count, total_targets, f"Processed {processed_count}/{total_targets}: {level_path}")
                            except Exception:
                                pass
                        continue

                    level_stats[level_path]["success"] += 1
                    success_count += 1
                    processed_count += 1
                    result_lines.append(f"Set level override to {resolution} on {component_name} in {level_path}")
                    if progress_callback is not None:
                        try:
                            progress_callback(processed_count, total_targets, f"Processed {processed_count}/{total_targets}: {level_path}")
                        except Exception:
                            pass

                if cancelled:
                    break

                if level_stats[level_path]["success"] > 0:
                    save_dirty_content()

        invalidate_level_viewports()
    except Exception as error:
        result_lines.append(f"Batch component lightmap update failed: {error}")
    finally:
        restore_original_level(original_level_path, "batched component lightmap resolution update")

    if progress_callback is not None:
        try:
            final_processed = processed_count if cancelled else total_targets
            progress_callback(final_processed, total_targets, f"Finished instance lightmap update. {success_count}/{processed_count or total_targets} rows applied.")
        except Exception:
            pass

    return success_count, result_lines, _format_static_mesh_component_batch_level_summaries(level_stats), cancelled


def clear_level_static_mesh_component_lightmap_resolution_override(
    level_path: str,
    actor_path: str,
    component_name: str,
) -> tuple[bool, str]:
    original_level_path = get_current_open_level_path()

    try:
        actor, loaded_level = find_or_load_actor_by_path(level_path, actor_path)
        if actor is None:
            return False, f"Could not find actor in {level_path}: {actor_path}"

        component = find_static_mesh_component_on_actor(actor, component_name)
        if component is None:
            return False, f"Could not find static mesh component on actor: {component_name}"

        override_set = set_editor_property_value(component, ("override_light_map_res",), False)
        resolution_set = set_editor_property_value(component, ("overridden_light_map_res",), 0)
        if not override_set or not resolution_set:
            return False, f"Could not clear component lightmap override for {component_name}"

        if loaded_level:
            save_current_level()

        invalidate_level_viewports()
        return True, f"Cleared level override on {component_name} in {level_path}"
    except Exception as error:
        return False, f"Could not clear component lightmap override in {level_path}: {error}"
    finally:
        restore_original_level(original_level_path, "component lightmap override reset")


def clear_level_static_mesh_component_lightmap_resolution_override_batch(
    targets: list[tuple[str, str, str]],
    progress_callback=None,
) -> tuple[int, list[str], list[str], bool]:
    grouped_targets = _group_static_mesh_component_targets_by_level(targets)
    if not grouped_targets:
        return 0, ["No static mesh component targets were provided."], [], False

    total_targets = sum(len(level_targets) for level_targets in grouped_targets.values())
    success_count = 0
    processed_count = 0
    cancelled = False
    result_lines: list[str] = []
    level_stats = {
        level_path: {"success": 0, "failed": 0}
        for level_path in grouped_targets.keys()
    }
    original_level_path = get_current_open_level_path()
    original_loaded_level_paths = get_loaded_level_paths_in_editor_world()
    ordered_level_paths = sorted(
        grouped_targets.keys(),
        key=lambda level_path: (level_path not in original_loaded_level_paths, level_path.casefold()),
    )

    if progress_callback is not None:
        try:
            progress_callback(0, total_targets, "Preparing instance override reset...")
        except Exception:
            pass

    try:
        with unreal.ScopedSlowTask(total_targets, "Clearing static mesh lightmap overrides") as slow_task:
            slow_task.make_dialog(True)

            for level_path in ordered_level_paths:
                level_targets = grouped_targets[level_path]
                if hasattr(slow_task, "should_cancel") and slow_task.should_cancel():
                    cancelled = True
                    result_lines.append("Cancelled instance override reset.")
                    break

                level_was_loaded = False
                if level_targets:
                    first_actor_path, _first_component_name = level_targets[0]
                    _first_actor, level_was_loaded = find_or_load_actor_by_path(level_path, first_actor_path)

                if progress_callback is not None:
                    try:
                        load_action = "Using loaded" if not level_was_loaded else "Loaded"
                        progress_callback(processed_count, total_targets, f"{load_action} {level_path}. Clearing {len(level_targets)} instance overrides...")
                    except Exception:
                        pass

                for actor_path, component_name in level_targets:
                    if hasattr(slow_task, "should_cancel") and slow_task.should_cancel():
                        cancelled = True
                        result_lines.append("Cancelled instance override reset.")
                        break

                    slow_task.enter_progress_frame(1, f"Clear {component_name} in {level_path}")

                    actor = find_actor_by_path_in_level(actor_path, level_path)
                    if actor is None:
                        level_stats[level_path]["failed"] += 1
                        result_lines.append(f"Could not find actor in {level_path}: {actor_path}")
                        processed_count += 1
                        if progress_callback is not None:
                            try:
                                progress_callback(processed_count, total_targets, f"Processed {processed_count}/{total_targets}: {level_path}")
                            except Exception:
                                pass
                        continue

                    component = find_static_mesh_component_on_actor(actor, component_name)
                    if component is None:
                        level_stats[level_path]["failed"] += 1
                        result_lines.append(f"Could not find static mesh component on actor: {component_name}")
                        processed_count += 1
                        if progress_callback is not None:
                            try:
                                progress_callback(processed_count, total_targets, f"Processed {processed_count}/{total_targets}: {level_path}")
                            except Exception:
                                pass
                        continue

                    override_set = set_editor_property_value(component, ("override_light_map_res",), False)
                    resolution_set = set_editor_property_value(component, ("overridden_light_map_res",), 0)
                    if not override_set or not resolution_set:
                        level_stats[level_path]["failed"] += 1
                        result_lines.append(f"Could not clear component lightmap override for {component_name}")
                        processed_count += 1
                        if progress_callback is not None:
                            try:
                                progress_callback(processed_count, total_targets, f"Processed {processed_count}/{total_targets}: {level_path}")
                            except Exception:
                                pass
                        continue

                    level_stats[level_path]["success"] += 1
                    success_count += 1
                    processed_count += 1
                    result_lines.append(f"Cleared level override on {component_name} in {level_path}")
                    if progress_callback is not None:
                        try:
                            progress_callback(processed_count, total_targets, f"Processed {processed_count}/{total_targets}: {level_path}")
                        except Exception:
                            pass

                if cancelled:
                    break

                if level_stats[level_path]["success"] > 0:
                    save_dirty_content()

        invalidate_level_viewports()
    except Exception as error:
        result_lines.append(f"Batch component lightmap override reset failed: {error}")
    finally:
        restore_original_level(original_level_path, "batched component lightmap override reset")

    if progress_callback is not None:
        try:
            final_processed = processed_count if cancelled else total_targets
            progress_callback(final_processed, total_targets, f"Finished instance override reset. {success_count}/{processed_count or total_targets} rows cleared.")
        except Exception:
            pass

    return success_count, result_lines, _format_static_mesh_component_batch_level_summaries(level_stats), cancelled


def clear_static_mesh_audit_cache() -> None:
    _STATIC_MESH_AUDIT_CACHE.clear()


def get_cached_static_mesh_lightmap_audit(asset_path: str) -> tuple[bool, list[str], dict[str, object]]:
    normalized_asset_path = normalize_asset_path(asset_path)
    cached_result = _STATIC_MESH_AUDIT_CACHE.get(normalized_asset_path)
    if cached_result is not None:
        return cached_result

    helper_module = get_static_mesh_audit_helper_module()
    result = helper_module.audit_static_mesh_lightmap_settings(normalized_asset_path)
    _STATIC_MESH_AUDIT_CACHE[normalized_asset_path] = result
    return result


def format_static_mesh_audit_warning(audit_data: dict[str, object]) -> str:
    overlap_percentage = audit_data.get("overlap_percentage")
    overlap_text = "Unknown"
    if overlap_percentage is not None:
        overlap_text = f"{float(overlap_percentage):.1f}%"

    return (
        f"Static mesh lightmap risk: {audit_data['asset_name']} "
        f"(Overlap={overlap_text}, "
        f"Import Generate Lightmap UVs={audit_data['import_generate_lightmap_uvs']}, "
        f"LOD0 Generate Lightmap UVs={audit_data['lod0_generate_lightmap_u_vs']})"
    )


def collect_static_mesh_lightmap_warnings(level_path: str, actors: list) -> list[str]:
    del level_path

    asset_paths = get_level_static_mesh_asset_paths(actors)
    if not asset_paths:
        return []

    helper_module = get_static_mesh_audit_helper_module()
    risky_entries: list[dict[str, object]] = []
    warnings: list[str] = []

    for asset_path in asset_paths:
        try:
            _audit_ok, _audit_lines, audit_data = get_cached_static_mesh_lightmap_audit(asset_path)
        except Exception as error:
            warnings.append(f"Static mesh lightmap audit failed for {asset_path}: {error}")
            continue

        if audit_data.get("issues") or audit_data.get("has_overlap_warning"):
            risky_entries.append(audit_data)

    if not risky_entries:
        return warnings

    risky_entries.sort(key=helper_module.get_audit_sort_key)
    for audit_data in risky_entries[:STATIC_MESH_LIGHTMAP_AUDIT_WARNING_LIMIT]:
        warnings.append(format_static_mesh_audit_warning(audit_data))

    remaining_count = len(risky_entries) - STATIC_MESH_LIGHTMAP_AUDIT_WARNING_LIMIT
    if remaining_count > 0:
        warnings.append(f"Additional static mesh lightmap risks: {remaining_count} more mesh(es)")

    return warnings


def run_static_mesh_lightmap_audit() -> None:
    try:
        audit_module = get_static_mesh_audit_script_module()
        audit_module.main()
    except Exception as error:
        message = f"Static mesh lightmap audit failed: {error}"
        unreal.log_error(message)
        if hasattr(unreal, "EditorDialog"):
            unreal.EditorDialog.show_message("Build Lighting", message, unreal.AppMsgType.OK)


def clear_precheck_cache() -> bool:
    cache_path = get_precheck_cache_path()
    if not os.path.isfile(cache_path):
        return False

    os.remove(cache_path)
    return True


def get_active_editor_log_path() -> str | None:
    log_dir = get_project_log_dir()
    if not os.path.isdir(log_dir):
        return None

    project_name = get_project_name().lower()
    candidates: list[str] = []
    for file_name in os.listdir(log_dir):
        lower_name = file_name.lower()
        if not lower_name.endswith(".log"):
            continue
        if "backup" in lower_name:
            continue
        if not lower_name.startswith(project_name):
            continue
        candidates.append(os.path.join(log_dir, file_name))

    if not candidates:
        return None

    candidates.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    return candidates[0]


def get_log_offset(log_path: str | None) -> int:
    if log_path is None or not os.path.isfile(log_path):
        return 0

    return os.path.getsize(log_path)


def extract_new_log_lines(log_path: str | None, start_offset: int) -> list[str]:
    if log_path is None or not os.path.isfile(log_path):
        return []

    with open(log_path, "r", encoding="utf-8", errors="replace") as handle:
        handle.seek(start_offset)
        return [line.rstrip("\r\n") for line in handle.readlines()]


def is_lighting_relevant_log_line(log_line: str) -> bool:
    lowered_line = log_line.lower()

    if any(pattern in lowered_line for pattern in LIGHTING_RELEVANT_PATTERNS):
        return True

    if any(category in lowered_line for category in LIGHTING_LOG_CATEGORIES):
        return "lighting" in lowered_line or "lightmap" in lowered_line or "reflection capture" in lowered_line

    return False


def classify_native_lighting_log_line(log_line: str) -> str | None:
    lowered_line = log_line.lower()

    if not is_lighting_relevant_log_line(log_line):
        return None

    if "error:" in lowered_line:
        return "error"

    if "warning:" in lowered_line:
        return "warning"

    if any(pattern in lowered_line for pattern in LIGHTING_WARNING_PATTERNS):
        return "warning"

    return None


def collect_native_warning_error_lines(log_lines: list[str]) -> tuple[list[str], list[str]]:
    native_warnings: list[str] = []
    native_errors: list[str] = []

    for line in log_lines:
        normalized_line = line.strip()
        if not normalized_line:
            continue

        classification = classify_native_lighting_log_line(normalized_line)
        if classification == "warning":
            native_warnings.append(normalized_line)
        elif classification == "error":
            native_errors.append(normalized_line)

    return native_warnings, native_errors


def discover_levels() -> list[LevelEntry]:
    content_dir = get_project_content_dir()
    levels: list[LevelEntry] = []

    for root, _, files in os.walk(content_dir):
        for file_name in files:
            if not file_name.lower().endswith(MAP_EXTENSION):
                continue

            file_path = os.path.join(root, file_name)
            relative_path = os.path.relpath(file_path, content_dir)
            package_path = os.path.splitext(relative_path)[0].replace(os.sep, "/")
            level_path = normalize_level_path(f"{CONTENT_ROOT}/{package_path}")

            levels.append(
                LevelEntry(
                    name=os.path.splitext(file_name)[0],
                    level_path=level_path,
                    file_path=file_path,
                )
            )

    levels.sort(key=lambda entry: entry.level_path.lower())
    return levels


def save_dirty_content() -> None:
    if not hasattr(unreal, "EditorLoadingAndSavingUtils"):
        return

    utils = unreal.EditorLoadingAndSavingUtils

    for call in (
        lambda: utils.save_dirty_packages(True, True),
        lambda: utils.save_dirty_packages(False, True),
        lambda: utils.save_dirty_packages_with_dialog(True, True),
    ):
        try:
            call()
            return
        except Exception:
            continue


def sanitize_file_name(value: str) -> str:
    sanitized = []
    for character in value:
        if character.isalnum() or character in ("-", "_"):
            sanitized.append(character)
        else:
            sanitized.append("_")

    return "".join(sanitized)


def normalize_asset_level_path(level_path: str) -> str:
    normalized = normalize_level_path(level_path.strip())
    if "." in normalized:
        normalized = normalized.split(".", 1)[0]
    return normalized


def are_level_paths_equal(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False

    return normalize_asset_level_path(left) == normalize_asset_level_path(right)


def get_current_open_level_path() -> str | None:
    if not hasattr(unreal, "EditorLevelLibrary"):
        return None

    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
    except Exception:
        return None

    if world is None:
        return None

    for candidate_getter in (
        lambda: world.get_path_name(),
        lambda: world.get_outer().get_path_name(),
    ):
        try:
            candidate = candidate_getter()
            if candidate:
                return normalize_asset_level_path(candidate)
        except Exception:
            continue

    return None


def get_loaded_level_paths_in_editor_world() -> set[str]:
    loaded_level_paths: set[str] = set()
    current_open_level = get_current_open_level_path()
    if current_open_level:
        loaded_level_paths.add(current_open_level)

    for actor in get_all_level_actors():
        actor_level_path = get_actor_level_path(actor)
        if actor_level_path:
            loaded_level_paths.add(actor_level_path)

    return loaded_level_paths


def find_open_level_conflicts(level_paths: list[str]) -> list[str]:
    current_open_level = get_current_open_level_path()
    if current_open_level is None:
        return []

    conflicting_levels: list[str] = []
    for level_path in level_paths:
        if normalize_asset_level_path(level_path) == current_open_level:
            conflicting_levels.append(level_path)

    return conflicting_levels


def show_blocking_message(title: str, message: str) -> None:
    unreal.log_error(message)
    if hasattr(unreal, "EditorDialog"):
        unreal.EditorDialog.show_message(title, message, unreal.AppMsgType.OK)


def show_confirmation_dialog(title: str, message: str) -> bool:
    if not hasattr(unreal, "EditorDialog"):
        unreal.log_warning(message)
        return False

    try:
        result = unreal.EditorDialog.show_message(title, message, unreal.AppMsgType.YES_NO)
    except Exception:
        unreal.log_warning(message)
        return False

    yes_value = getattr(getattr(unreal, "AppReturnType", object), "YES", None)
    if yes_value is not None:
        try:
            return result == yes_value
        except Exception:
            pass

    return str(result).upper().endswith("YES")


def get_selected_level_paths_from_editor(levels: list[LevelEntry]) -> list[str]:
    discovered_level_paths = {entry.level_path for entry in levels}
    selected_level_paths: list[str] = []

    editor_utility_library = getattr(unreal, "EditorUtilityLibrary", None)
    if editor_utility_library is None:
        return selected_level_paths

    selected_objects = []
    for method_name in ("get_selected_asset_data", "get_selected_assets"):
        method = getattr(editor_utility_library, method_name, None)
        if method is None:
            continue
        try:
            selected_objects = list(method())
            if selected_objects:
                break
        except Exception:
            continue

    for selected_object in selected_objects:
        candidate_paths: list[str] = []
        for getter in (
            lambda obj=selected_object: obj.get_asset().get_path_name(),
            lambda obj=selected_object: obj.get_path_name(),
            lambda obj=selected_object: str(obj.get_editor_property("package_name")),
            lambda obj=selected_object: str(obj.package_name),
            lambda obj=selected_object: str(obj.get_editor_property("object_path")),
        ):
            try:
                candidate = getter()
                if candidate:
                    candidate_paths.append(normalize_asset_level_path(str(candidate)))
            except Exception:
                continue

        for candidate_path in candidate_paths:
            if candidate_path in discovered_level_paths and candidate_path not in selected_level_paths:
                selected_level_paths.append(candidate_path)
                break

    return selected_level_paths


def load_level(level_path: str) -> None:
    normalized_level_path = normalize_asset_level_path(level_path)

    if hasattr(unreal.EditorLevelLibrary, "load_level"):
        unreal.EditorLevelLibrary.load_level(normalized_level_path)
        return

    if hasattr(unreal, "LevelEditorSubsystem"):
        subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if subsystem is not None and hasattr(subsystem, "load_level"):
            subsystem.load_level(normalized_level_path)
            return

    raise RuntimeError("No supported Unreal Python API was found to load levels.")


def ensure_level_loaded(level_path: str) -> bool:
    normalized_level_path = normalize_asset_level_path(level_path)
    current_level_path = get_current_open_level_path()
    if are_level_paths_equal(current_level_path, normalized_level_path):
        return False

    load_level(normalized_level_path)
    return True


def restore_original_level(original_level_path: str | None, context_label: str) -> None:
    if original_level_path is None:
        return

    try:
        ensure_level_loaded(original_level_path)
    except Exception as error:
        mirror_runtime_line(
            "Lighting Results",
            f"Could not restore previously open level {original_level_path} after {context_label}: {error}",
            "warning",
        )


def get_level_editor_subsystem():
    if not hasattr(unreal, "LevelEditorSubsystem"):
        return None

    try:
        return unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    except Exception:
        return None


def resolve_lighting_quality_enum(lighting_quality: str):
    if not hasattr(unreal, "LightingBuildQuality"):
        raise RuntimeError("Unreal Python does not expose LightingBuildQuality.")

    enum_candidates = {
        "Preview": ("QUALITY_PREVIEW", "Preview", "Quality_Preview"),
        "Medium": ("QUALITY_MEDIUM", "Medium", "Quality_Medium"),
        "High": ("QUALITY_HIGH", "High", "Quality_High"),
        "Production": ("QUALITY_PRODUCTION", "Production", "Quality_Production"),
        "MAX": ("QUALITY_MAX", "MAX", "Quality_MAX"),
    }

    for attribute_name in enum_candidates[lighting_quality]:
        enum_value = getattr(unreal.LightingBuildQuality, attribute_name, None)
        if enum_value is not None:
            return enum_value

    raise RuntimeError(f"Could not resolve LightingBuildQuality enum value for {lighting_quality}.")


def build_light_maps_for_current_level(options: LightingToolOptions) -> bool:
    subsystem = get_level_editor_subsystem()
    if subsystem is None or not hasattr(subsystem, "build_light_maps"):
        raise RuntimeError("LevelEditorSubsystem.BuildLightMaps is not available in Unreal Python.")

    normalized_options = normalize_lighting_options(options)
    quality_enum = resolve_lighting_quality_enum(normalized_options.lighting_quality)
    return bool(subsystem.build_light_maps(quality_enum, normalized_options.with_reflection_captures))


def save_current_level() -> None:
    if hasattr(unreal.EditorLevelLibrary, "save_current_level"):
        try:
            unreal.EditorLevelLibrary.save_current_level()
            return
        except Exception:
            pass

    save_dirty_content()


def get_all_level_actors() -> list:
    if not hasattr(unreal, "EditorLevelLibrary"):
        return []

    try:
        return list(unreal.EditorLevelLibrary.get_all_level_actors())
    except Exception:
        return []


def get_actor_class_names(actors: list) -> set[str]:
    class_names: set[str] = set()

    for actor in actors:
        try:
            class_names.add(actor.get_class().get_name())
        except Exception:
            continue

    return class_names


def get_world_settings():
    if not hasattr(unreal, "EditorLevelLibrary"):
        return None

    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
    except Exception:
        return None

    if world is None:
        return None

    for getter in (
        lambda: world.get_world_settings(),
        lambda: unreal.EditorLevelLibrary.get_game_world().get_world_settings() if hasattr(unreal.EditorLevelLibrary, "get_game_world") else None,
    ):
        try:
            world_settings = getter()
            if world_settings is not None:
                return world_settings
        except Exception:
            continue

    return None


def get_bool_editor_property(obj, property_names: tuple[str, ...]) -> bool | None:
    if obj is None:
        return None

    for property_name in property_names:
        try:
            return bool(obj.get_editor_property(property_name))
        except Exception:
            continue

    return None


def get_float_editor_property(obj, property_names: tuple[str, ...]) -> float | None:
    if obj is None:
        return None

    for property_name in property_names:
        try:
            return float(obj.get_editor_property(property_name))
        except Exception:
            continue

    return None


def get_int_editor_property(obj, property_names: tuple[str, ...]) -> int | None:
    if obj is None:
        return None

    for property_name in property_names:
        try:
            return int(obj.get_editor_property(property_name))
        except Exception:
            continue

    return None


def _notify_object_pre_edit(obj) -> None:
    if obj is None:
        return

    modify_method = getattr(obj, "modify", None)
    if callable(modify_method):
        try:
            modify_method()
        except Exception:
            pass


def _notify_object_post_edit(obj) -> None:
    if obj is None:
        return

    post_edit_change_method = getattr(obj, "post_edit_change", None)
    if callable(post_edit_change_method):
        try:
            post_edit_change_method()
        except Exception:
            pass

    mark_package_dirty_method = getattr(obj, "mark_package_dirty", None)
    if callable(mark_package_dirty_method):
        try:
            mark_package_dirty_method()
        except Exception:
            pass


def set_editor_property_value(obj, property_names: tuple[str, ...], value) -> bool:
    if obj is None:
        return False

    owner = None
    owner_getter = getattr(obj, "get_owner", None)
    if callable(owner_getter):
        try:
            owner = owner_getter()
        except Exception:
            owner = None

    _notify_object_pre_edit(owner)
    _notify_object_pre_edit(obj)

    for property_name in property_names:
        try:
            obj.set_editor_property(property_name, value)
            _notify_object_post_edit(obj)
            _notify_object_post_edit(owner)
            return True
        except Exception:
            continue

    return False


def save_config_object(obj) -> None:
    if obj is None:
        return

    for method_name in ("save_config", "update_default_config_file"):
        method = getattr(obj, method_name, None)
        if method is None:
            continue

        try:
            method()
            return
        except Exception:
            continue


def invalidate_level_viewports() -> None:
    subsystem = get_level_editor_subsystem()
    if subsystem is not None and hasattr(subsystem, "editor_invalidate_viewports"):
        try:
            subsystem.editor_invalidate_viewports()
            return
        except Exception:
            pass

    if hasattr(unreal, "EditorLevelLibrary") and hasattr(unreal.EditorLevelLibrary, "editor_invalidate_viewports"):
        try:
            unreal.EditorLevelLibrary.editor_invalidate_viewports()
        except Exception:
            pass


def get_engine_settings_object():
    if not hasattr(unreal, "get_default_object"):
        return None

    for class_name in ("UnrealEdEngine", "EditorEngine", "Engine"):
        engine_class = getattr(unreal, class_name, None)
        if engine_class is None:
            continue

        try:
            return unreal.get_default_object(engine_class)
        except Exception:
            continue

    return None


def get_editor_world():
    if hasattr(unreal, "EditorLevelLibrary") and hasattr(unreal.EditorLevelLibrary, "get_editor_world"):
        try:
            return unreal.EditorLevelLibrary.get_editor_world()
        except Exception:
            return None

    return None


def prepare_active_viewport_for_view_mode() -> None:
    subsystem = get_level_editor_subsystem()
    if subsystem is not None:
        try:
            if hasattr(subsystem, "editor_set_game_view"):
                subsystem.editor_set_game_view(False)
        except Exception:
            pass

    elif hasattr(unreal, "EditorLevelLibrary") and hasattr(unreal.EditorLevelLibrary, "editor_set_game_view"):
        try:
            unreal.EditorLevelLibrary.editor_set_game_view(False)
        except Exception:
            pass

    if hasattr(unreal, "PythonBPLib"):
        try:
            if hasattr(unreal.PythonBPLib, "set_level_viewport_is_in_game_view"):
                unreal.PythonBPLib.set_level_viewport_is_in_game_view(False)
        except Exception:
            pass


def set_editor_viewport_view_mode(view_mode_name: str) -> bool:
    automation_library = getattr(unreal, "AutomationLibrary", None)
    view_mode_index = getattr(unreal, "ViewModeIndex", None)
    if automation_library is None or view_mode_index is None:
        return False

    view_mode_value = getattr(view_mode_index, view_mode_name, None)
    if view_mode_value is None:
        return False

    try:
        automation_library.set_editor_viewport_view_mode(view_mode_value)
        if hasattr(unreal, "PythonBPLib") and hasattr(unreal.PythonBPLib, "viewport_redraw"):
            try:
                unreal.PythonBPLib.viewport_redraw()
            except Exception:
                pass
        return True
    except Exception:
        return False


def execute_editor_console_command(command: str) -> bool:
    if hasattr(unreal, "PythonBPLib") and hasattr(unreal.PythonBPLib, "execute_console_command"):
        try:
            unreal.PythonBPLib.execute_console_command(command)
            return True
        except Exception:
            pass

    if hasattr(unreal, "SystemLibrary") and hasattr(unreal.SystemLibrary, "execute_console_command"):
        world = get_editor_world()
        if world is not None:
            try:
                unreal.SystemLibrary.execute_console_command(world, command)
                return True
            except Exception:
                pass

    return False


def try_editor_console_commands(commands: list[str]) -> tuple[bool, str | None]:
    for command in commands:
        if execute_editor_console_command(command):
            return True, command

    return False, None


def activate_view_mode(
    automation_view_mode_name: str | None,
    commands: list[str],
    success_message: str,
    failure_message: str,
) -> tuple[bool, str]:
    prepare_active_viewport_for_view_mode()

    if automation_view_mode_name and set_editor_viewport_view_mode(automation_view_mode_name):
        invalidate_level_viewports()
        unreal.log(f"View mode API succeeded: {automation_view_mode_name}")
        return True, success_message

    succeeded, used_command = try_editor_console_commands(commands)
    if succeeded:
        invalidate_level_viewports()
        if used_command is not None:
            unreal.log(f"View mode command succeeded: {used_command}")
        return True, success_message

    return False, f"{failure_message} Tried: {', '.join(commands)}"


def normalize_lighting_options(options: LightingToolOptions) -> LightingToolOptions:
    min_density = max(0.0, float(options.min_lightmap_density))
    ideal_density = max(min_density, float(options.ideal_lightmap_density))
    max_density = max(ideal_density + 0.01, float(options.max_lightmap_density))
    color_scale = max(0.01, float(options.lightmap_density_color_scale))
    grayscale_scale = max(0.01, float(options.lightmap_density_grayscale_scale))

    return LightingToolOptions(
        lighting_quality=options.lighting_quality,
        with_reflection_captures=bool(options.with_reflection_captures),
        open_lightmap_density_view=bool(options.open_lightmap_density_view),
        min_lightmap_density=min_density,
        ideal_lightmap_density=ideal_density,
        max_lightmap_density=max_density,
        lightmap_density_color_scale=color_scale,
        lightmap_density_grayscale_scale=grayscale_scale,
        render_lightmap_density_grayscale=bool(options.render_lightmap_density_grayscale),
    )


def lighting_options_to_dict(options: LightingToolOptions) -> dict[str, object]:
    normalized_options = normalize_lighting_options(options)
    return {
        "lighting_quality": normalized_options.lighting_quality,
        "with_reflection_captures": normalized_options.with_reflection_captures,
        "open_lightmap_density_view": normalized_options.open_lightmap_density_view,
        "min_lightmap_density": normalized_options.min_lightmap_density,
        "ideal_lightmap_density": normalized_options.ideal_lightmap_density,
        "max_lightmap_density": normalized_options.max_lightmap_density,
        "lightmap_density_color_scale": normalized_options.lightmap_density_color_scale,
        "lightmap_density_grayscale_scale": normalized_options.lightmap_density_grayscale_scale,
        "render_lightmap_density_grayscale": normalized_options.render_lightmap_density_grayscale,
    }


def load_native_lighting_options() -> tuple[LightingToolOptions, str]:
    options_path = get_native_options_path()
    default_options = get_current_lighting_tool_options()

    if not os.path.isfile(options_path):
        os.makedirs(os.path.dirname(options_path), exist_ok=True)
        with open(options_path, "w", encoding="utf-8", errors="strict") as handle:
            json.dump(lighting_options_to_dict(default_options), handle, indent=2)
        return default_options, options_path

    try:
        with open(options_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as error:
        unreal.log_warning(f"Could not read native lighting options from {options_path}: {error}")
        return default_options, options_path

    if not isinstance(payload, dict):
        unreal.log_warning(f"Ignoring invalid native lighting options payload in {options_path}")
        return default_options, options_path

    options = LightingToolOptions(
        lighting_quality=str(payload.get("lighting_quality", default_options.lighting_quality)),
        with_reflection_captures=bool(payload.get("with_reflection_captures", default_options.with_reflection_captures)),
        open_lightmap_density_view=bool(payload.get("open_lightmap_density_view", default_options.open_lightmap_density_view)),
        min_lightmap_density=float(payload.get("min_lightmap_density", default_options.min_lightmap_density)),
        ideal_lightmap_density=float(payload.get("ideal_lightmap_density", default_options.ideal_lightmap_density)),
        max_lightmap_density=float(payload.get("max_lightmap_density", default_options.max_lightmap_density)),
        lightmap_density_color_scale=float(payload.get("lightmap_density_color_scale", default_options.lightmap_density_color_scale)),
        lightmap_density_grayscale_scale=float(payload.get("lightmap_density_grayscale_scale", default_options.lightmap_density_grayscale_scale)),
        render_lightmap_density_grayscale=bool(payload.get("render_lightmap_density_grayscale", default_options.render_lightmap_density_grayscale)),
    )
    return normalize_lighting_options(options), options_path


def get_current_lighting_tool_options() -> LightingToolOptions:
    engine_settings = get_engine_settings_object()

    return LightingToolOptions(
        lighting_quality=DEFAULT_LIGHTING_QUALITY,
        with_reflection_captures=False,
        open_lightmap_density_view=False,
        min_lightmap_density=get_float_editor_property(
            engine_settings,
            ("min_light_map_density", "MinLightMapDensity"),
        ) or LIGHTMAP_DENSITY_DEFAULT_MIN,
        ideal_lightmap_density=get_float_editor_property(
            engine_settings,
            ("ideal_light_map_density", "IdealLightMapDensity"),
        ) or LIGHTMAP_DENSITY_DEFAULT_IDEAL,
        max_lightmap_density=get_float_editor_property(
            engine_settings,
            ("max_light_map_density", "MaxLightMapDensity"),
        ) or LIGHTMAP_DENSITY_DEFAULT_MAX,
        lightmap_density_color_scale=get_float_editor_property(
            engine_settings,
            ("render_light_map_density_color_scale", "RenderLightMapDensityColorScale"),
        ) or LIGHTMAP_DENSITY_DEFAULT_COLOR_SCALE,
        lightmap_density_grayscale_scale=get_float_editor_property(
            engine_settings,
            ("render_light_map_density_grayscale_scale", "RenderLightMapDensityGrayscaleScale"),
        ) or LIGHTMAP_DENSITY_DEFAULT_GRAYSCALE_SCALE,
        render_lightmap_density_grayscale=bool(
            get_bool_editor_property(
                engine_settings,
                ("b_render_light_map_density_grayscale", "render_light_map_density_grayscale", "bRenderLightMapDensityGrayscale"),
            )
        ),
    )


def apply_lightmap_density_settings(options: LightingToolOptions) -> tuple[bool, str]:
    normalized_options = normalize_lighting_options(options)
    engine_settings = get_engine_settings_object()
    if engine_settings is None:
        return False, "Could not access engine lighting density settings from Unreal Python."

    updates = (
        (("min_light_map_density", "MinLightMapDensity"), normalized_options.min_lightmap_density),
        (("ideal_light_map_density", "IdealLightMapDensity"), normalized_options.ideal_lightmap_density),
        (("max_light_map_density", "MaxLightMapDensity"), normalized_options.max_lightmap_density),
        (("render_light_map_density_color_scale", "RenderLightMapDensityColorScale"), normalized_options.lightmap_density_color_scale),
        (("render_light_map_density_grayscale_scale", "RenderLightMapDensityGrayscaleScale"), normalized_options.lightmap_density_grayscale_scale),
        (("b_render_light_map_density_grayscale", "render_light_map_density_grayscale", "bRenderLightMapDensityGrayscale"), normalized_options.render_lightmap_density_grayscale),
    )

    failed_properties: list[str] = []
    for property_names, value in updates:
        if not set_editor_property_value(engine_settings, property_names, value):
            failed_properties.append(property_names[-1])

    if failed_properties:
        return False, "Could not update engine lighting density properties: " + ", ".join(failed_properties)

    save_config_object(engine_settings)
    invalidate_level_viewports()
    return True, "Lightmap density settings applied."


def activate_lightmap_density_view() -> tuple[bool, str]:
    return activate_view_mode(
        "VMI_LIGHTMAP_DENSITY",
        [
            "viewmode lightmapdensity",
            "viewmode VMI_LightmapDensity",
        ],
        "Lightmap Density view activated.",
        "Could not switch the active viewport to Lightmap Density view.",
    )


def activate_lighting_only_view() -> tuple[bool, str]:
    return activate_view_mode(
        "VMI_LIGHTING_ONLY",
        [
            "viewmode lightingonly",
            "viewmode VMI_LightingOnly",
        ],
        "Lighting Only view activated.",
        "Could not switch the active viewport to Lighting Only view.",
    )


def activate_lit_view() -> tuple[bool, str]:
    return activate_view_mode(
        "VMI_LIT",
        [
            "viewmode lit",
            "viewmode VMI_Lit",
        ],
        "Lit view activated.",
        "Could not switch the active viewport back to Lit view.",
    )


def get_native_lighting_tools_message() -> str:
    supported_qualities = ", ".join(sorted(ERROR_COLORING_SUPPORTED_QUALITIES))
    return (
        "Native Unreal lighting actions that are not exposed reliably through UE 5.7 Python:\n"
        "- Use Error Coloring\n"
        "- Show Lighting Stats / Statistics window\n"
        "- Static Mesh Lighting Info window\n"
        "- LightMap Resolution Adjustment dialog\n\n"
        "Menu path: Build > Lighting Info.\n"
        f"Error coloring only visualizes correctly when Lighting Quality is {supported_qualities}."
    )


def describe_lighting_options(options: LightingToolOptions) -> list[str]:
    normalized_options = normalize_lighting_options(options)
    return [
        f"Lighting quality: {normalized_options.lighting_quality}",
        f"Build reflection captures: {'Enabled' if normalized_options.with_reflection_captures else 'Disabled'}",
        f"Open Lightmap Density view: {'Enabled' if normalized_options.open_lightmap_density_view else 'Disabled'}",
        (
            "Lightmap Density: "
            f"min={normalized_options.min_lightmap_density:.2f}, "
            f"ideal={normalized_options.ideal_lightmap_density:.2f}, "
            f"max={normalized_options.max_lightmap_density:.2f}, "
            f"color_scale={normalized_options.lightmap_density_color_scale:.2f}, "
            f"grayscale_scale={normalized_options.lightmap_density_grayscale_scale:.2f}, "
            f"render_grayscale={'Enabled' if normalized_options.render_lightmap_density_grayscale else 'Disabled'}"
        ),
    ]


def level_has_lightmass_importance_volume(actors: list | None = None) -> bool:
    if actors is None:
        actors = get_all_level_actors()

    class_names = get_actor_class_names(actors)
    return "LightmassImportanceVolume" in class_names


def collect_prebuild_result(level_path: str) -> LevelPrecheckResult:
    blockers: list[str] = []
    warnings: list[str] = []
    actors = get_all_level_actors()
    class_names = get_actor_class_names(actors)

    if not level_has_lightmass_importance_volume(actors):
        blockers.append("Lightmass Importance Volume not found")

    world_settings = get_world_settings()
    force_no_precomputed_lighting = get_bool_editor_property(
        world_settings,
        ("force_no_precomputed_lighting", "b_force_no_precomputed_lighting"),
    )
    if force_no_precomputed_lighting:
        blockers.append("Force No Precomputed Lighting is enabled")

    light_actor_classes = {"DirectionalLight", "SkyLight", "PointLight", "SpotLight", "RectLight"}
    if not any(class_name in light_actor_classes for class_name in class_names):
        warnings.append("No common light actors found")

    if "SphereReflectionCapture" not in class_names and "BoxReflectionCapture" not in class_names:
        warnings.append("No reflection capture actors found")

    warnings.extend(collect_static_mesh_lightmap_warnings(level_path, actors))

    return LevelPrecheckResult(level_path=level_path, blockers=blockers, warnings=warnings)


def summarize_precheck_counts(levels: list[LevelEntry], issue_map: dict[str, LevelPrecheckResult]) -> tuple[int, int, int]:
    blocked_count = 0
    warning_count = 0

    for entry in levels:
        result = issue_map.get(entry.level_path)
        if result is None:
            continue

        if result.blockers:
            blocked_count += 1
        elif result.warnings:
            warning_count += 1

    return len(levels), blocked_count, warning_count


def get_level_sort_key(entry: LevelEntry, issue_map: dict[str, LevelPrecheckResult]) -> tuple[int, str]:
    result = issue_map.get(entry.level_path)
    if result is not None:
        if result.blockers:
            return (0, entry.level_path.lower())
        if result.warnings:
            return (1, entry.level_path.lower())

    return (2, entry.level_path.lower())


def serialize_precheck_result(result: LevelPrecheckResult) -> dict:
    return {
        "level_path": result.level_path,
        "blockers": list(result.blockers),
        "warnings": list(result.warnings),
    }


def deserialize_precheck_result(data: dict) -> LevelPrecheckResult:
    return LevelPrecheckResult(
        level_path=str(data.get("level_path", "")),
        blockers=[str(value) for value in data.get("blockers", [])],
        warnings=[str(value) for value in data.get("warnings", [])],
    )


def save_precheck_cache(levels: list[LevelEntry], issue_map: dict[str, LevelPrecheckResult]) -> str:
    cache_path = get_precheck_cache_path()
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    generated_at = datetime.now().isoformat(timespec="seconds")

    payload = {
        "generated_at": generated_at,
        "levels": {
            entry.level_path: serialize_precheck_result(
                issue_map.get(entry.level_path, LevelPrecheckResult(entry.level_path, [], []))
            )
            for entry in levels
        },
    }

    with open(cache_path, "w", encoding="utf-8", errors="strict") as handle:
        json.dump(payload, handle, indent=2)

    return generated_at


def load_precheck_cache(levels: list[LevelEntry]) -> tuple[dict[str, LevelPrecheckResult] | None, str | None]:
    cache_path = get_precheck_cache_path()
    if not os.path.isfile(cache_path):
        return None, None

    try:
        with open(cache_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as error:
        unreal.log_warning(f"Could not read precheck cache {cache_path}: {error}")
        return None, None

    cached_levels = payload.get("levels")
    if not isinstance(cached_levels, dict):
        unreal.log_warning(f"Ignoring invalid precheck cache structure in {cache_path}")
        return None, None

    expected_level_paths = {entry.level_path for entry in levels}
    cached_level_paths = {str(level_path) for level_path in cached_levels.keys()}
    if expected_level_paths != cached_level_paths:
        unreal.log(f"Ignoring stale precheck cache in {cache_path} because the level list changed")
        return None, None

    issue_map: dict[str, LevelPrecheckResult] = {}
    for level_path in expected_level_paths:
        issue_map[level_path] = deserialize_precheck_result(cached_levels[level_path])

    generated_at = payload.get("generated_at")
    return issue_map, str(generated_at) if generated_at else None


def has_precheck_run(precheck_source_label: str) -> bool:
    return precheck_source_label not in ("", "not run")


def scan_levels_for_prebuild_issues(levels: list[LevelEntry]) -> dict[str, LevelPrecheckResult]:
    issue_map: dict[str, LevelPrecheckResult] = {}
    original_level_path = get_current_open_level_path()
    total_levels = len(levels)
    clear_static_mesh_audit_cache()

    try:
        for index, level in enumerate(levels, start=1):
            try:
                mirror_runtime_line("Lighting Results", f"[Precheck {index}/{total_levels}] Loading level: {level.level_path}", "info")
                ensure_level_loaded(level.level_path)
                result = collect_prebuild_result(level.level_path)
                for blocker in result.blockers:
                    mirror_runtime_line("Lighting Results", f"[Precheck {index}/{total_levels}] {level.level_path}: {blocker}", "warning")
                for warning in result.warnings:
                    mirror_runtime_line("Lighting Results", f"[Precheck {index}/{total_levels}] {level.level_path}: {warning}", "warning")
            except Exception as error:
                result = LevelPrecheckResult(
                    level_path=level.level_path,
                    blockers=[f"Precheck failed: {error}"],
                    warnings=[],
                )
                mirror_runtime_line("Lighting Results", f"Precheck failed for {level.level_path}: {error}", "error")

            issue_map[level.level_path] = result
    finally:
        restore_original_level(original_level_path, "precheck")

    return issue_map


def format_level_label(entry: LevelEntry, issue_map: dict[str, LevelPrecheckResult]) -> str:
    result = issue_map.get(entry.level_path)
    if result is None or (not result.blockers and not result.warnings):
        return f"{entry.name}    {entry.level_path}"

    tags: list[str] = []
    if result.blockers:
        tags.append("BLOCKED: " + "; ".join(result.blockers))
    if result.warnings:
        tags.append("WARN: " + "; ".join(result.warnings))

    return f"{entry.name}    {entry.level_path}    [{' | '.join(tags)}]"


def get_selected_level_issues(level_paths: list[str], issue_map: dict[str, LevelPrecheckResult]) -> list[str]:
    invalid_levels: list[str] = []
    for level_path in level_paths:
        result = issue_map.get(level_path)
        if result is not None and result.blockers:
            invalid_levels.append(f"{level_path}: {'; '.join(result.blockers)}")

    return invalid_levels


def log_lines_to_output(lines: list[str], severity: str) -> None:
    log_function = unreal.log
    if severity == "warning":
        log_function = unreal.log_warning
    elif severity == "error":
        log_function = unreal.log_error

    for line in lines:
        prefixed_line = f"[Lighting Results] {line}" if line else "[Lighting Results]"
        try:
            print(prefixed_line)
        except Exception:
            pass

        log_function(line)


def append_lines_to_mirror_log(log_name: str, lines: list[str], severity: str) -> str:
    log_dir = get_project_log_dir()
    os.makedirs(log_dir, exist_ok=True)
    mirror_log_path = os.path.join(log_dir, "LightingResults_Mirror.log")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(mirror_log_path, "a", encoding="utf-8", errors="strict") as handle:
        handle.write(f"[{timestamp}] [{severity.upper()}] [{log_name}]\n")
        for line in lines:
            if line:
                handle.write(line + "\n")
        handle.write("\n")

    return mirror_log_path


def get_message_log_targets(log_name: str, severity: str) -> list[str]:
    canonical_name = MESSAGE_LOG_NAME_ALIASES.get(log_name, log_name)
    targets: list[str] = []

    if canonical_name:
        targets.append(canonical_name)

    if canonical_name == "LightingResults" and severity in ("warning", "error"):
        targets.append("MapCheck")

    deduplicated_targets: list[str] = []
    for target in targets:
        if target not in deduplicated_targets:
            deduplicated_targets.append(target)

    return deduplicated_targets


def get_message_log_open_args(severity: str):
    severity_enum = None
    if hasattr(unreal, "MessageSeverity"):
        severity_enum_name = "INFO"
        if severity == "warning":
            severity_enum_name = "WARNING"
        elif severity == "error":
            severity_enum_name = "ERROR"
        severity_enum = getattr(unreal.MessageSeverity, severity_enum_name, None)

    if severity_enum is None:
        return [tuple(), tuple()]

    return [
        (severity_enum, True),
        (severity_enum,),
        tuple(),
    ]


def log_lines_to_message_log(log_name: str, lines: list[str], severity: str) -> None:
    global _MESSAGE_LOG_WARNING_SHOWN

    if not hasattr(unreal, "MessageLog"):
        if not _MESSAGE_LOG_WARNING_SHOWN:
            unreal.log_warning(
                "Unreal Python in this editor session does not expose a writable Message Log API. Lighting warnings will only be mirrored to Output Log, popup summaries, and Saved/Logs/LightingResults_Mirror.log."
            )
            _MESSAGE_LOG_WARNING_SHOWN = True
        return

    log_method_name = "info"
    if severity == "warning":
        log_method_name = "warning"
    elif severity == "error":
        log_method_name = "error"

    for target_log_name in get_message_log_targets(log_name, severity):
        try:
            message_log = unreal.MessageLog(target_log_name)
        except Exception:
            if not _MESSAGE_LOG_WARNING_SHOWN:
                unreal.log_warning(
                    "Unreal Python could not open the editor Message Log listing. Lighting warnings will only be mirrored to Output Log, popup summaries, and Saved/Logs/LightingResults_Mirror.log."
                )
                _MESSAGE_LOG_WARNING_SHOWN = True
            continue

        log_method = getattr(message_log, log_method_name, None)
        if log_method is None:
            continue

        try:
            if hasattr(message_log, "new_page"):
                message_log.new_page(target_log_name)

            for line in lines:
                if line:
                    log_method(line)

            if hasattr(message_log, "open"):
                for open_args in get_message_log_open_args(severity):
                    try:
                        message_log.open(*open_args)
                        break
                    except Exception:
                        continue
        except Exception:
            continue


def mirror_summary_to_logs(log_name: str, lines: list[str], severity: str) -> None:
    log_lines_to_output(lines, severity)
    log_lines_to_message_log(log_name, lines, severity)
    append_lines_to_mirror_log(log_name, lines, severity)


def mirror_runtime_line(log_name: str, line: str, severity: str) -> None:
    mirror_summary_to_logs(log_name, [line], severity)


def show_precheck_summary(
    levels: list[LevelEntry],
    issue_map: dict[str, LevelPrecheckResult],
    precheck_source_label: str,
    precheck_generated_at: str | None,
    force_show: bool = False,
) -> None:
    problematic_levels = [entry for entry in levels if issue_map.get(entry.level_path) and (issue_map[entry.level_path].blockers or issue_map[entry.level_path].warnings)]
    if not problematic_levels and not force_show:
        return

    log_dir = get_project_log_dir()
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(log_dir, f"BuildLighting_Precheck_{timestamp}.log")

    lines = [
        f"Precheck found issues in {len(problematic_levels)} level(s)." if problematic_levels else "Precheck found no blocking or warning issues.",
        "Blocked levels cannot be built. Warning-only levels remain selectable.",
        f"Precheck source: {precheck_source_label}",
        f"Precheck log: {log_path}",
        f"Mirror log: {os.path.join(get_project_log_dir(), 'LightingResults_Mirror.log')}",
        "",
    ]

    if precheck_generated_at:
        timestamp_label = "Cache generated" if precheck_source_label == "cache" else "Last scan"
        lines.insert(3, f"{timestamp_label}: {precheck_generated_at}")

    for entry in problematic_levels:
        result = issue_map[entry.level_path]
        if result.blockers:
            lines.append(f"{entry.level_path} [BLOCKED]: {'; '.join(result.blockers)}")
        if result.warnings:
            lines.append(f"{entry.level_path} [WARN]: {'; '.join(result.warnings)}")

    message = "\n".join(lines)

    with open(log_path, "w", encoding="utf-8", errors="strict") as handle:
        handle.write(message)

    mirror_summary_to_logs("Lighting Results", lines, "warning")
    if hasattr(unreal, "EditorDialog"):
        unreal.EditorDialog.show_message("Lighting Precheck", message, unreal.AppMsgType.OK)


def write_build_summary_log(results: list[LevelBuildResult], options: LightingToolOptions) -> str:
    log_dir = get_project_log_dir()
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(log_dir, f"BuildLighting_Summary_{timestamp}.log")

    successes = [result.level_path for result in results if result.success]
    failures = [result for result in results if not result.success]
    warnings = [result for result in results if result.warnings]
    native_warnings = [result for result in results if result.native_warnings]
    native_errors = [result for result in results if result.native_errors]

    lines = describe_lighting_options(options)
    lines.extend(
        [
            f"Successful: {len(successes)}",
            f"Failed: {len(failures)}",
            "",
        ]
    )

    if successes:
        lines.append("Successful Levels:")
        lines.extend(successes)
        lines.append("")

    if warnings:
        lines.append("Warnings:")
        for result in warnings:
            lines.append(f"{result.level_path}: {'; '.join(result.warnings)}")
        lines.append("")

    if native_warnings:
        lines.append("Native Unreal Warnings:")
        for result in native_warnings:
            lines.append(result.level_path)
            lines.extend(result.native_warnings or [])
            lines.append("")

    if native_errors:
        lines.append("Native Unreal Errors:")
        for result in native_errors:
            lines.append(result.level_path)
            lines.extend(result.native_errors or [])
            lines.append("")

    if failures:
        lines.append("Failures:")
        for result in failures:
            lines.append(f"{result.level_path}: {result.error}")

    with open(log_path, "w", encoding="utf-8", errors="strict") as handle:
        handle.write("\n".join(lines))

    return log_path


def build_levels_in_editor(level_paths: list[str], options: LightingToolOptions) -> list[LevelBuildResult]:
    results: list[LevelBuildResult] = []
    normalized_options = normalize_lighting_options(options)

    save_dirty_content()
    total_levels = len(level_paths)

    density_applied, density_message = apply_lightmap_density_settings(normalized_options)
    if density_applied:
        mirror_runtime_line("Lighting Results", density_message, "info")
    else:
        mirror_runtime_line("Lighting Results", density_message, "warning")

    for index, level_path in enumerate(level_paths, start=1):
        warnings: list[str] = []
        native_warnings: list[str] = []
        native_errors: list[str] = []
        try:
            mirror_runtime_line("Lighting Results", f"[{index}/{total_levels}] Loading level: {level_path}", "info")
            ensure_level_loaded(level_path)
            precheck_result = collect_prebuild_result(level_path)
            warnings = list(precheck_result.warnings)

            for warning in warnings:
                mirror_runtime_line("Lighting Results", f"[{index}/{total_levels}] {level_path}: {warning}", "warning")

            if precheck_result.blockers:
                raise RuntimeError("; ".join(precheck_result.blockers))

            mirror_runtime_line(
                "Lighting Results",
                f"[{index}/{total_levels}] Building lighting in editor: {level_path} ({normalized_options.lighting_quality})",
                "info",
            )
            editor_log_path = get_active_editor_log_path()
            editor_log_offset = get_log_offset(editor_log_path)

            build_succeeded = build_light_maps_for_current_level(normalized_options)
            if not build_succeeded:
                raise RuntimeError("LevelEditorSubsystem.BuildLightMaps returned False.")

            native_log_lines = extract_new_log_lines(editor_log_path, editor_log_offset)
            native_warnings, native_errors = collect_native_warning_error_lines(native_log_lines)
            for native_warning in native_warnings:
                mirror_runtime_line("Lighting Results", f"[{index}/{total_levels}] {level_path} native warning: {native_warning}", "warning")
            for native_error in native_errors:
                mirror_runtime_line("Lighting Results", f"[{index}/{total_levels}] {level_path} native error: {native_error}", "error")

            save_current_level()
            results.append(
                LevelBuildResult(
                    level_path=level_path,
                    success=True,
                    warnings=warnings,
                    native_warnings=native_warnings,
                    native_errors=native_errors,
                )
            )
            mirror_runtime_line("Lighting Results", f"[{index}/{total_levels}] Finished lighting build: {level_path}", "info")
        except Exception as error:
            mirror_runtime_line("Lighting Results", f"Lighting build failed for {level_path}: {error}", "error")
            results.append(
                LevelBuildResult(
                    level_path=level_path,
                    success=False,
                    warnings=warnings,
                    error=str(error),
                    native_warnings=native_warnings,
                    native_errors=native_errors,
                )
            )

    return results


def show_build_summary(results: list[LevelBuildResult], options: LightingToolOptions) -> None:
    normalized_options = normalize_lighting_options(options)
    summary_log_path = write_build_summary_log(results, normalized_options)
    successes = [result.level_path for result in results if result.success]
    failures = [result for result in results if not result.success]
    warnings = [result for result in results if result.warnings]
    native_warnings = [result for result in results if result.native_warnings]
    native_errors = [result for result in results if result.native_errors]

    lines = [
        f"Finished in-editor lighting build for {len(successes)} level(s).",
        f"Failed: {len(failures)} level(s).",
        f"Summary log: {summary_log_path}",
        f"Mirror log: {os.path.join(get_project_log_dir(), 'LightingResults_Mirror.log')}",
    ]
    lines.extend([""] + describe_lighting_options(normalized_options))

    if successes:
        lines.append("")
        lines.append("Successful:")
        lines.extend(successes)

    if warnings:
        lines.append("")
        lines.append(f"Warnings: {len(warnings)} level(s)")
        for result in warnings:
            lines.append(f"{result.level_path}: {'; '.join(result.warnings)}")

    if native_warnings:
        lines.append("")
        lines.append(f"Native Unreal Warnings: {len(native_warnings)} level(s)")
        for result in native_warnings:
            lines.append(result.level_path)
            lines.extend(result.native_warnings or [])

    if native_errors:
        lines.append("")
        lines.append(f"Native Unreal Errors: {len(native_errors)} level(s)")
        for result in native_errors:
            lines.append(result.level_path)
            lines.extend(result.native_errors or [])

    if failures:
        lines.append("")
        lines.append("Build Failures:")
        for result in failures:
            lines.append(f"{result.level_path}: {result.error}")

    summary = "\n".join(lines)
    summary_severity = "error" if failures else "warning" if warnings else "info"
    mirror_summary_to_logs("Lighting Results", lines, summary_severity)
    if hasattr(unreal, "EditorDialog"):
        unreal.EditorDialog.show_message("Build Lighting", summary, unreal.AppMsgType.OK)


def execute_build_selection(build_selection: BuildSelection, original_level_path: str | None) -> None:
    if not build_selection.level_paths:
        unreal.log("Build lighting cancelled.")
        return

    try:
        results = build_levels_in_editor(
            build_selection.level_paths,
            build_selection.lighting_options,
        )
    finally:
        restore_original_level(original_level_path, "build")

    if build_selection.lighting_options.open_lightmap_density_view:
        activate_lightmap_density_view()

    show_build_summary(results, build_selection.lighting_options)


def launch_build_for_selection(build_selection: BuildSelection, original_level_path: str | None) -> None:
    execute_build_selection(build_selection, original_level_path)


def build_levels_without_custom_ui(levels: list[LevelEntry], original_level_path: str | None) -> None:
    options, options_path = load_native_lighting_options()
    selected_level_paths = get_selected_level_paths_from_editor(levels)

    if not selected_level_paths and original_level_path is not None:
        normalized_original_level_path = normalize_asset_level_path(original_level_path)
        if any(entry.level_path == normalized_original_level_path for entry in levels):
            selected_level_paths = [normalized_original_level_path]

    if not selected_level_paths:
        show_blocking_message(
            "Build Lighting",
            "PySide2/PySide6 is unavailable, so the tool switched to native no-window mode. "
            "Select one or more map assets in the Content Browser, or open a map, then run the script again. "
            f"Lighting options are read from {options_path}.",
        )
        return

    selected_entries = [entry for entry in levels if entry.level_path in selected_level_paths]
    issue_map = scan_levels_for_prebuild_issues(selected_entries)
    generated_at = save_precheck_cache(selected_entries, issue_map)
    invalid_levels = get_selected_level_issues(selected_level_paths, issue_map)

    summary_lines = [
        "Running in native no-window mode because PySide2/PySide6 is unavailable.",
        "Selected levels:",
    ]
    summary_lines.extend(selected_level_paths)
    summary_lines.append("")
    summary_lines.extend(describe_lighting_options(options))
    summary_lines.append(f"Options file: {options_path}")
    summary_lines.append(f"Precheck snapshot: {generated_at}")

    warning_levels = [
        issue_map[level_path]
        for level_path in selected_level_paths
        if issue_map.get(level_path) is not None and issue_map[level_path].warnings
    ]
    if warning_levels:
        summary_lines.append("")
        summary_lines.append("Warnings:")
        for result in warning_levels:
            summary_lines.append(f"{result.level_path}: {'; '.join(result.warnings)}")

    if invalid_levels:
        summary_lines.append("")
        summary_lines.append("Blocked levels:")
        summary_lines.extend(invalid_levels)
        show_blocking_message("Build Lighting", "\n".join(summary_lines))
        return

    summary_lines.append("")
    summary_lines.append("Proceed with lighting build?")
    if not show_confirmation_dialog("Build Lighting", "\n".join(summary_lines)):
        unreal.log("Build lighting cancelled.")
        return

    execute_build_selection(
        BuildSelection(
            selected_level_paths,
            options,
            dict(issue_map),
            "fresh scan",
            generated_at,
        ),
        original_level_path,
    )


class BuildLightingQtController:
    def __init__(
        self,
        levels: list[LevelEntry],
        issue_map: dict[str, LevelPrecheckResult],
        precheck_source_label: str,
        precheck_generated_at: str | None,
        original_level_path: str | None,
        qt_modules,
    ) -> None:
        self.levels = levels
        self.current_issue_map = dict(issue_map)
        self.current_precheck_source_label = precheck_source_label
        self.current_precheck_generated_at = precheck_generated_at
        self.original_level_path = original_level_path
        self.QtCore = qt_modules.QtCore
        self.QtGui = qt_modules.QtGui
        self.QtWidgets = qt_modules.QtWidgets
        self.app = self.QtWidgets.QApplication.instance()
        if self.app is None:
            self.app = self.QtWidgets.QApplication([])

        self.dialog = self.QtWidgets.QDialog()
        self.dialog.setAttribute(self.QtCore.Qt.WA_DeleteOnClose, True)
        self.dialog.setWindowTitle("Build Level Lighting")
        self.dialog.resize(820, 680)
        self.dialog.setModal(False)
        self.dialog.setWindowModality(self.QtCore.Qt.NonModal)
        self.dialog.setWindowFlag(self.QtCore.Qt.Tool, True)
        self.dialog.destroyed.connect(self._on_destroyed)

        self._build_ui()
        self.update_legend()
        self.populate()

    def _build_ui(self) -> None:
        layout = self.QtWidgets.QVBoxLayout(self.dialog)
        scroll_area = self.QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(self.QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(self.QtCore.Qt.ScrollBarAsNeeded)
        layout.addWidget(scroll_area)

        content_widget = self.QtWidgets.QWidget()
        scroll_area.setWidget(content_widget)
        content_layout = self.QtWidgets.QVBoxLayout(content_widget)

        instructions = self.QtWidgets.QLabel(
            "Run Precheck first, then review issues, configure lighting build and density options, audit static meshes if needed, and build lighting."
        )
        instructions.setWordWrap(True)
        content_layout.addWidget(instructions)

        self.legend_label = self.QtWidgets.QLabel()
        self.legend_label.setWordWrap(True)
        content_layout.addWidget(self.legend_label)

        self.search_box = self.QtWidgets.QLineEdit()
        self.search_box.setPlaceholderText("Filter levels...")
        content_layout.addWidget(self.search_box)

        self.hide_blocked_checkbox = self.QtWidgets.QCheckBox("Only buildable levels")
        self.hide_blocked_checkbox.setChecked(False)
        content_layout.addWidget(self.hide_blocked_checkbox)

        self.list_widget = self.QtWidgets.QListWidget()
        self.list_widget.setSelectionMode(self.QtWidgets.QAbstractItemView.ExtendedSelection)
        self.list_widget.setMinimumHeight(240)
        self.list_widget.setVerticalScrollBarPolicy(self.QtCore.Qt.ScrollBarAlwaysOn)
        content_layout.addWidget(self.list_widget)

        button_layout = self.QtWidgets.QHBoxLayout()
        self.select_all_button = self.QtWidgets.QPushButton("Select All")
        self.clear_button = self.QtWidgets.QPushButton("Clear")
        self.refresh_button = self.QtWidgets.QPushButton("Refresh")
        self.rescan_button = self.QtWidgets.QPushButton("Rescan Levels")
        self.load_cached_button = self.QtWidgets.QPushButton("Load Cached Precheck")
        self.clear_cache_button = self.QtWidgets.QPushButton("Clear Cache")
        self.run_precheck_button = self.QtWidgets.QPushButton("Run Precheck")
        self.audit_mesh_button = self.QtWidgets.QPushButton("Audit Static Meshes")
        self.build_button = self.QtWidgets.QPushButton("Build Lighting")
        self.cancel_button = self.QtWidgets.QPushButton("Close")

        for button in (
            self.select_all_button,
            self.clear_button,
            self.refresh_button,
            self.rescan_button,
            self.load_cached_button,
            self.clear_cache_button,
            self.run_precheck_button,
            self.audit_mesh_button,
            self.build_button,
            self.cancel_button,
        ):
            button_layout.addWidget(button)

        content_layout.addLayout(button_layout)

        self.current_lighting_options = get_current_lighting_tool_options()

        quality_layout = self.QtWidgets.QHBoxLayout()
        quality_label = self.QtWidgets.QLabel("Lighting Quality")
        self.quality_combo = self.QtWidgets.QComboBox()
        self.quality_combo.addItems(LIGHTING_QUALITY_OPTIONS)
        self.quality_combo.setCurrentText(self.current_lighting_options.lighting_quality)
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_combo, 1)
        content_layout.addLayout(quality_layout)

        build_options_layout = self.QtWidgets.QHBoxLayout()
        self.reflection_captures_checkbox = self.QtWidgets.QCheckBox("Build Reflection Captures")
        self.reflection_captures_checkbox.setChecked(self.current_lighting_options.with_reflection_captures)
        self.open_density_view_checkbox = self.QtWidgets.QCheckBox("Open Lightmap Density View After Build")
        self.open_density_view_checkbox.setChecked(self.current_lighting_options.open_lightmap_density_view)
        build_options_layout.addWidget(self.reflection_captures_checkbox)
        build_options_layout.addWidget(self.open_density_view_checkbox)
        build_options_layout.addStretch(1)
        content_layout.addLayout(build_options_layout)

        density_group = self.QtWidgets.QGroupBox("Lightmap Density Rendering Options")
        density_form = self.QtWidgets.QFormLayout(density_group)

        def make_density_spinbox(value: float):
            spin_box = self.QtWidgets.QDoubleSpinBox()
            spin_box.setDecimals(2)
            spin_box.setRange(0.0, 999.0)
            spin_box.setSingleStep(0.05)
            spin_box.setValue(value)
            return spin_box

        self.min_density_spin = make_density_spinbox(self.current_lighting_options.min_lightmap_density)
        self.ideal_density_spin = make_density_spinbox(self.current_lighting_options.ideal_lightmap_density)
        self.max_density_spin = make_density_spinbox(self.current_lighting_options.max_lightmap_density)
        self.color_scale_spin = make_density_spinbox(self.current_lighting_options.lightmap_density_color_scale)
        self.grayscale_scale_spin = make_density_spinbox(self.current_lighting_options.lightmap_density_grayscale_scale)
        self.render_grayscale_checkbox = self.QtWidgets.QCheckBox("Render Grayscale")
        self.render_grayscale_checkbox.setChecked(self.current_lighting_options.render_lightmap_density_grayscale)

        density_form.addRow("Minimum Density", self.min_density_spin)
        density_form.addRow("Ideal Density", self.ideal_density_spin)
        density_form.addRow("Maximum Density", self.max_density_spin)
        density_form.addRow("Color Scale", self.color_scale_spin)
        density_form.addRow("Grayscale Scale", self.grayscale_scale_spin)
        density_form.addRow("", self.render_grayscale_checkbox)

        density_button_layout = self.QtWidgets.QHBoxLayout()
        self.apply_density_button = self.QtWidgets.QPushButton("Apply Density Settings")
        self.density_view_button = self.QtWidgets.QPushButton("Lightmap Density View")
        self.lighting_only_button = self.QtWidgets.QPushButton("Lighting Only View")
        self.native_lighting_button = self.QtWidgets.QPushButton("Native Lighting Actions")
        for button in (
            self.apply_density_button,
            self.density_view_button,
            self.lighting_only_button,
            self.native_lighting_button,
        ):
            density_button_layout.addWidget(button)
        density_form.addRow("", density_button_layout)
        content_layout.addWidget(density_group)

        self.search_box.textChanged.connect(self.populate)
        self.hide_blocked_checkbox.stateChanged.connect(lambda _state: self.populate(self.search_box.text()))
        self.select_all_button.clicked.connect(self.list_widget.selectAll)
        self.clear_button.clicked.connect(self.list_widget.clearSelection)
        self.refresh_button.clicked.connect(lambda: self.populate(self.search_box.text()))
        self.rescan_button.clicked.connect(self.on_rescan)
        self.load_cached_button.clicked.connect(self.on_load_cached_precheck)
        self.clear_cache_button.clicked.connect(self.on_clear_cache)
        self.run_precheck_button.clicked.connect(self.on_run_precheck)
        self.audit_mesh_button.clicked.connect(run_static_mesh_lightmap_audit)
        self.apply_density_button.clicked.connect(self.on_apply_density_settings)
        self.density_view_button.clicked.connect(self.on_lightmap_density_view)
        self.lighting_only_button.clicked.connect(self.on_lighting_only_view)
        self.native_lighting_button.clicked.connect(self.on_native_lighting_actions)
        self.build_button.clicked.connect(self.on_build)
        self.cancel_button.clicked.connect(self.dialog.close)

    def show(self) -> None:
        self.dialog.show()
        if hasattr(unreal, "parent_external_window_to_slate"):
            try:
                unreal.parent_external_window_to_slate(int(self.dialog.winId()))
            except Exception:
                pass
        self.dialog.raise_()
        self.dialog.activateWindow()

    def _on_destroyed(self, *_args) -> None:
        global _ACTIVE_BUILD_LIGHTING_QT_WINDOW
        if _ACTIVE_BUILD_LIGHTING_QT_WINDOW is self:
            _ACTIVE_BUILD_LIGHTING_QT_WINDOW = None

    def collect_lighting_options_from_controls(self) -> LightingToolOptions:
        return normalize_lighting_options(
            LightingToolOptions(
                lighting_quality=self.quality_combo.currentText(),
                with_reflection_captures=self.reflection_captures_checkbox.isChecked(),
                open_lightmap_density_view=self.open_density_view_checkbox.isChecked(),
                min_lightmap_density=self.min_density_spin.value(),
                ideal_lightmap_density=self.ideal_density_spin.value(),
                max_lightmap_density=self.max_density_spin.value(),
                lightmap_density_color_scale=self.color_scale_spin.value(),
                lightmap_density_grayscale_scale=self.grayscale_scale_spin.value(),
                render_lightmap_density_grayscale=self.render_grayscale_checkbox.isChecked(),
            )
        )

    def update_legend(self) -> None:
        if not has_precheck_run(self.current_precheck_source_label):
            self.legend_label.setText(
                "Precheck has not been run yet. Press Run Precheck or Load Cached Precheck before building lighting."
            )
            self.rescan_button.setEnabled(False)
            return

        self.rescan_button.setEnabled(True)
        total_levels, blocked_count, warning_count = summarize_precheck_counts(self.levels, self.current_issue_map)
        timestamp_suffix = f"    Snapshot: {self.current_precheck_generated_at}" if self.current_precheck_generated_at else ""
        self.legend_label.setText(
            f"Levels: {total_levels}    Blocked: {blocked_count}    Warning: {warning_count}    "
            f"Source: {self.current_precheck_source_label}{timestamp_suffix}    Red = blocked, Amber = warning-only"
        )

    def build_groups(self, filter_text: str) -> list[tuple[str, list[LevelEntry]]]:
        if not has_precheck_run(self.current_precheck_source_label):
            entries = []
            for entry in self.levels:
                searchable = f"{entry.name} {entry.level_path}".lower()
                if filter_text and filter_text not in searchable:
                    continue
                entries.append(entry)
            return [("Unscanned", entries)] if entries else []

        grouped: dict[str, list[LevelEntry]] = {
            "Blocked": [],
            "Warnings": [],
            "Buildable": [],
        }

        for entry in sorted(self.levels, key=lambda current_entry: get_level_sort_key(current_entry, self.current_issue_map)):
            result = self.current_issue_map.get(entry.level_path)
            if self.hide_blocked_checkbox.isChecked() and result is not None and result.blockers:
                continue

            searchable = f"{entry.name} {entry.level_path}".lower()
            if filter_text and filter_text not in searchable:
                continue

            if result is not None and result.blockers:
                grouped["Blocked"].append(entry)
            elif result is not None and result.warnings:
                grouped["Warnings"].append(entry)
            else:
                grouped["Buildable"].append(entry)

        return [(group_name, grouped[group_name]) for group_name in ("Blocked", "Warnings", "Buildable") if grouped[group_name]]

    def add_header_item(self, group_name: str, count: int) -> None:
        header_item = self.QtWidgets.QListWidgetItem(f"{group_name} ({count})")
        header_font = header_item.font()
        header_font.setBold(True)
        header_item.setFont(header_font)
        header_item.setForeground(self.QtGui.QBrush(self.QtGui.QColor("#111827")))
        header_item.setBackground(self.QtGui.QBrush(self.QtGui.QColor("#e5e7eb")))
        header_item.setFlags(self.QtCore.Qt.NoItemFlags)
        self.list_widget.addItem(header_item)

    def populate(self, filter_text: str = "") -> None:
        self.list_widget.clear()
        normalized_filter = filter_text.strip().lower()

        for group_name, entries in self.build_groups(normalized_filter):
            self.add_header_item(group_name, len(entries))
            for entry in entries:
                result = self.current_issue_map.get(entry.level_path)
                item = self.QtWidgets.QListWidgetItem(format_level_label(entry, self.current_issue_map))
                item.setData(self.QtCore.Qt.UserRole, entry.level_path)

                if result is not None and result.blockers:
                    item.setForeground(self.QtGui.QBrush(self.QtGui.QColor("#9b1c1c")))
                    item.setBackground(self.QtGui.QBrush(self.QtGui.QColor("#fde8e8")))
                    item.setFlags(item.flags() & ~self.QtCore.Qt.ItemIsSelectable & ~self.QtCore.Qt.ItemIsEnabled)
                elif result is not None and result.warnings:
                    item.setForeground(self.QtGui.QBrush(self.QtGui.QColor("#92400e")))
                    item.setBackground(self.QtGui.QBrush(self.QtGui.QColor("#fef3c7")))

                self.list_widget.addItem(item)

    def show_info_message(self, title: str, message: str) -> None:
        self.QtWidgets.QMessageBox.information(self.dialog, title, message)

    def on_apply_density_settings(self) -> None:
        lighting_options = self.collect_lighting_options_from_controls()
        success, message = apply_lightmap_density_settings(lighting_options)
        if success and lighting_options.open_lightmap_density_view:
            _, view_message = activate_lightmap_density_view()
            message = f"{message}\n{view_message}"
        self.show_info_message("Lighting Options", message)

    def on_lightmap_density_view(self) -> None:
        _, message = activate_lightmap_density_view()
        self.show_info_message("Lighting Options", message)

    def on_lighting_only_view(self) -> None:
        _, message = activate_lighting_only_view()
        self.show_info_message("Lighting Options", message)

    def on_native_lighting_actions(self) -> None:
        self.show_info_message("Lighting Options", get_native_lighting_tools_message())

    def on_run_precheck(self) -> None:
        self.current_issue_map = scan_levels_for_prebuild_issues(self.levels)
        self.current_precheck_generated_at = save_precheck_cache(self.levels, self.current_issue_map)
        self.current_precheck_source_label = "fresh scan"
        self.update_legend()
        self.populate(self.search_box.text())
        show_precheck_summary(
            self.levels,
            self.current_issue_map,
            self.current_precheck_source_label,
            self.current_precheck_generated_at,
            force_show=True,
        )

    def on_load_cached_precheck(self) -> None:
        cached_issue_map, cached_generated_at = load_precheck_cache(self.levels)
        if cached_issue_map is None:
            self.QtWidgets.QMessageBox.information(self.dialog, "Build Lighting", "No valid cached precheck data was found.")
            return

        self.current_issue_map = cached_issue_map
        self.current_precheck_source_label = "cache"
        self.current_precheck_generated_at = cached_generated_at
        self.update_legend()
        self.populate(self.search_box.text())
        show_precheck_summary(
            self.levels,
            self.current_issue_map,
            self.current_precheck_source_label,
            self.current_precheck_generated_at,
            force_show=True,
        )

    def on_rescan(self) -> None:
        self.current_issue_map = scan_levels_for_prebuild_issues(self.levels)
        self.current_precheck_generated_at = save_precheck_cache(self.levels, self.current_issue_map)
        self.current_precheck_source_label = "fresh scan"
        self.update_legend()
        self.populate(self.search_box.text())

    def on_clear_cache(self) -> None:
        removed = clear_precheck_cache()
        if not has_precheck_run(self.current_precheck_source_label):
            self.current_precheck_source_label = "not run"
            self.current_precheck_generated_at = None
        self.update_legend()

        message = "Precheck cache cleared." if removed else "Precheck cache file was not present."
        self.QtWidgets.QMessageBox.information(self.dialog, "Build Lighting", message)

    def on_build(self) -> None:
        selection: list[str] = []

        if not has_precheck_run(self.current_precheck_source_label):
            self.QtWidgets.QMessageBox.warning(self.dialog, "Build Lighting", "Run Precheck first.")
            return

        for item in self.list_widget.selectedItems():
            level_path = item.data(self.QtCore.Qt.UserRole)
            if level_path:
                selection.append(level_path)

        if not selection:
            self.QtWidgets.QMessageBox.warning(self.dialog, "Build Lighting", "Select at least one level.")
            return

        invalid_levels = get_selected_level_issues(selection, self.current_issue_map)
        if invalid_levels:
            self.QtWidgets.QMessageBox.warning(
                self.dialog,
                "Build Lighting",
                "These selected levels have known precheck issues and cannot be built:\n\n" + "\n".join(invalid_levels),
            )
            return

        build_selection = BuildSelection(
            selection,
            self.collect_lighting_options_from_controls(),
            dict(self.current_issue_map),
            self.current_precheck_source_label,
            self.current_precheck_generated_at,
        )

        self.dialog.close()
        self.QtCore.QTimer.singleShot(
            0,
            lambda selection_to_build=build_selection, original_level_path=self.original_level_path: launch_build_for_selection(
                selection_to_build,
                original_level_path,
            ),
        )


def launch_build_lighting_qt(
    levels: list[LevelEntry],
    issue_map: dict[str, LevelPrecheckResult],
    precheck_source_label: str,
    precheck_generated_at: str | None,
    original_level_path: str | None,
) -> bool:
    global _ACTIVE_BUILD_LIGHTING_QT_WINDOW

    qt_modules = None
    for module_name in ("PySide6", "PySide2"):
        try:
            qt_modules = __import__(module_name, fromlist=["QtCore", "QtGui", "QtWidgets"])
            break
        except ImportError:
            continue

    if qt_modules is None:
        return False

    if _ACTIVE_BUILD_LIGHTING_QT_WINDOW is not None:
        try:
            _ACTIVE_BUILD_LIGHTING_QT_WINDOW.dialog.raise_()
            _ACTIVE_BUILD_LIGHTING_QT_WINDOW.dialog.activateWindow()
            return True
        except Exception:
            _ACTIVE_BUILD_LIGHTING_QT_WINDOW = None

    _ACTIVE_BUILD_LIGHTING_QT_WINDOW = BuildLightingQtController(
        levels,
        issue_map,
        precheck_source_label,
        precheck_generated_at,
        original_level_path,
        qt_modules,
    )
    _ACTIVE_BUILD_LIGHTING_QT_WINDOW.show()
    return True


def choose_levels_with_qt(
    levels: list[LevelEntry],
    issue_map: dict[str, LevelPrecheckResult],
    precheck_source_label: str,
    precheck_generated_at: str | None,
) -> BuildSelection | None:
    del levels, issue_map, precheck_source_label, precheck_generated_at
    return None


def choose_levels_with_tk(
    levels: list[LevelEntry],
    issue_map: dict[str, LevelPrecheckResult],
    precheck_source_label: str,
    precheck_generated_at: str | None,
) -> BuildSelection | None:
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError:
        return None

    selected_levels: list[str] = []

    root = tk.Tk()
    root.title("Build Level Lighting")
    root.geometry("840x720")
    root.minsize(760, 560)

    current_lighting_options = get_current_lighting_tool_options()
    selected_quality = tk.StringVar(master=root, value=current_lighting_options.lighting_quality)
    reflection_captures_var = tk.BooleanVar(master=root, value=current_lighting_options.with_reflection_captures)
    open_density_view_var = tk.BooleanVar(master=root, value=current_lighting_options.open_lightmap_density_view)
    min_density_var = tk.DoubleVar(master=root, value=current_lighting_options.min_lightmap_density)
    ideal_density_var = tk.DoubleVar(master=root, value=current_lighting_options.ideal_lightmap_density)
    max_density_var = tk.DoubleVar(master=root, value=current_lighting_options.max_lightmap_density)
    color_scale_var = tk.DoubleVar(master=root, value=current_lighting_options.lightmap_density_color_scale)
    grayscale_scale_var = tk.DoubleVar(master=root, value=current_lighting_options.lightmap_density_grayscale_scale)
    render_grayscale_var = tk.BooleanVar(master=root, value=current_lighting_options.render_lightmap_density_grayscale)
    filter_var = tk.StringVar()
    buildable_only_var = tk.BooleanVar(master=root, value=False)
    row_entries: list[LevelEntry | None] = []
    selected_lighting_options = current_lighting_options
    current_issue_map = dict(issue_map)
    current_precheck_source_label = precheck_source_label
    current_precheck_generated_at = precheck_generated_at

    legend_var = tk.StringVar(master=root)
    content_container = tk.Frame(root)
    content_container.pack(fill="both", expand=True)

    page_canvas = tk.Canvas(content_container, highlightthickness=0)
    page_scrollbar = tk.Scrollbar(content_container, orient="vertical", command=page_canvas.yview)
    page_canvas.configure(yscrollcommand=page_scrollbar.set)
    page_scrollbar.pack(side="right", fill="y")
    page_canvas.pack(side="left", fill="both", expand=True)

    content_frame = tk.Frame(page_canvas)
    canvas_window = page_canvas.create_window((0, 0), window=content_frame, anchor="nw")

    def on_content_configure(_event) -> None:
        page_canvas.configure(scrollregion=page_canvas.bbox("all"))

    def on_canvas_configure(event) -> None:
        page_canvas.itemconfigure(canvas_window, width=event.width)

    def on_mousewheel(event) -> None:
        delta = event.delta
        if delta == 0:
            return

        page_canvas.yview_scroll(int(-delta / 120), "units")

    content_frame.bind("<Configure>", on_content_configure)
    page_canvas.bind("<Configure>", on_canvas_configure)
    page_canvas.bind_all("<MouseWheel>", on_mousewheel)

    list_frame = tk.Frame(content_frame)
    listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED, width=120, height=14)
    listbox_scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
    listbox.configure(yscrollcommand=listbox_scrollbar.set)

    def update_legend() -> None:
        if not has_precheck_run(current_precheck_source_label):
            legend_var.set("Precheck has not been run yet. Press Run Precheck or Load Cached Precheck before building lighting.")
            return

        total_levels, blocked_count, warning_count = summarize_precheck_counts(levels, current_issue_map)
        timestamp_suffix = f"    Snapshot: {current_precheck_generated_at}" if current_precheck_generated_at else ""
        legend_var.set(
            f"Levels: {total_levels}    Blocked: {blocked_count}    Warning: {warning_count}    "
            f"Source: {current_precheck_source_label}{timestamp_suffix}    Red = blocked, Amber = warning-only"
        )

    def build_groups(filter_text: str) -> list[tuple[str, list[LevelEntry]]]:
        if not has_precheck_run(current_precheck_source_label):
            entries = []
            for entry in levels:
                searchable = f"{entry.name} {entry.level_path}".lower()
                if filter_text and filter_text not in searchable:
                    continue
                entries.append(entry)
            return [("Unscanned", entries)] if entries else []

        grouped: dict[str, list[LevelEntry]] = {
            "Blocked": [],
            "Warnings": [],
            "Buildable": [],
        }

        for entry in sorted(levels, key=lambda current_entry: get_level_sort_key(current_entry, current_issue_map)):
            result = current_issue_map.get(entry.level_path)
            if buildable_only_var.get() and result is not None and result.blockers:
                continue

            searchable = f"{entry.name} {entry.level_path}".lower()
            if filter_text and filter_text not in searchable:
                continue

            if result is not None and result.blockers:
                grouped["Blocked"].append(entry)
            elif result is not None and result.warnings:
                grouped["Warnings"].append(entry)
            else:
                grouped["Buildable"].append(entry)

        return [(group_name, grouped[group_name]) for group_name in ("Blocked", "Warnings", "Buildable") if grouped[group_name]]

    def populate(*_args) -> None:
        filter_text = filter_var.get().strip().lower()
        listbox.delete(0, tk.END)
        row_entries.clear()

        for group_name, entries in build_groups(filter_text):
            listbox.insert(tk.END, f"{group_name} ({len(entries)})")
            header_index = listbox.size() - 1
            listbox.itemconfig(header_index, foreground="#111827", background="#e5e7eb")
            row_entries.append(None)

            for entry in entries:
                result = current_issue_map.get(entry.level_path)
                listbox.insert(tk.END, format_level_label(entry, current_issue_map))
                inserted_index = listbox.size() - 1
                if result is not None and result.blockers:
                    listbox.itemconfig(inserted_index, foreground="#9b1c1c", background="#fde8e8")
                elif result is not None and result.warnings:
                    listbox.itemconfig(inserted_index, foreground="#92400e", background="#fef3c7")
                row_entries.append(entry)

    def build_selected() -> None:
        nonlocal selected_lighting_options
        if not has_precheck_run(current_precheck_source_label):
            messagebox.showwarning("Build Lighting", "Run Precheck first.")
            return

        selected_indices = listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Build Lighting", "Select at least one level.")
            return

        selected_levels[:] = [
            row_entries[index].level_path
            for index in selected_indices
            if row_entries[index] is not None
        ]

        if not selected_levels:
            messagebox.showwarning("Build Lighting", "Select at least one level.")
            return

        invalid_levels = get_selected_level_issues(selected_levels, current_issue_map)
        if invalid_levels:
            messagebox.showwarning(
                "Build Lighting",
                "These selected levels have known precheck issues and cannot be built:\n\n" + "\n".join(invalid_levels),
            )
            selected_levels.clear()
            return

        selected_lighting_options = collect_lighting_options_from_controls()
        root.destroy()

    def run_precheck() -> None:
        nonlocal current_issue_map, current_precheck_source_label, current_precheck_generated_at
        current_issue_map = scan_levels_for_prebuild_issues(levels)
        current_precheck_generated_at = save_precheck_cache(levels, current_issue_map)
        current_precheck_source_label = "fresh scan"
        rescan_button.configure(state="normal")
        update_legend()
        populate()
        show_precheck_summary(levels, current_issue_map, current_precheck_source_label, current_precheck_generated_at, force_show=True)

    def load_cached_precheck() -> None:
        nonlocal current_issue_map, current_precheck_source_label, current_precheck_generated_at
        cached_issue_map, cached_generated_at = load_precheck_cache(levels)
        if cached_issue_map is None:
            messagebox.showinfo("Build Lighting", "No valid cached precheck data was found.")
            return

        current_issue_map = cached_issue_map
        current_precheck_source_label = "cache"
        current_precheck_generated_at = cached_generated_at
        rescan_button.configure(state="normal")
        update_legend()
        populate()
        show_precheck_summary(levels, current_issue_map, current_precheck_source_label, current_precheck_generated_at, force_show=True)

    def cancel() -> None:
        selected_levels.clear()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", cancel)

    label = tk.Label(content_frame, text="Run Precheck first, then review issues, configure lighting build and density options, audit static meshes if needed, and build lighting.", wraplength=760, justify="left")
    label.pack(anchor="w", padx=12, pady=(12, 6))

    tk.Label(content_frame, textvariable=legend_var, wraplength=760, justify="left").pack(anchor="w", padx=12, pady=(0, 8))

    quality_frame = tk.Frame(content_frame)
    quality_frame.pack(fill="x", padx=12, pady=(0, 8))

    tk.Label(quality_frame, text="Lighting Quality").pack(side="left")
    quality_menu = tk.OptionMenu(quality_frame, selected_quality, *LIGHTING_QUALITY_OPTIONS)
    quality_menu.pack(side="left", padx=(8, 0))

    build_options_frame = tk.Frame(content_frame)
    build_options_frame.pack(fill="x", padx=12, pady=(0, 8))
    tk.Checkbutton(build_options_frame, text="Build Reflection Captures", variable=reflection_captures_var).pack(side="left")
    tk.Checkbutton(build_options_frame, text="Open Lightmap Density View After Build", variable=open_density_view_var).pack(side="left", padx=(12, 0))

    density_frame = tk.LabelFrame(content_frame, text="Lightmap Density Rendering Options")
    density_frame.pack(fill="x", padx=12, pady=(0, 8))

    density_rows = (
        ("Minimum Density", min_density_var),
        ("Ideal Density", ideal_density_var),
        ("Maximum Density", max_density_var),
        ("Color Scale", color_scale_var),
        ("Grayscale Scale", grayscale_scale_var),
    )

    for row_index, (label_text, variable) in enumerate(density_rows):
        tk.Label(density_frame, text=label_text).grid(row=row_index, column=0, sticky="w", padx=(8, 8), pady=(6, 0))
        tk.Entry(density_frame, textvariable=variable, width=12).grid(row=row_index, column=1, sticky="w", pady=(6, 0))

    tk.Checkbutton(density_frame, text="Render Grayscale", variable=render_grayscale_var).grid(row=len(density_rows), column=0, columnspan=2, sticky="w", padx=8, pady=(6, 0))

    density_tools_frame = tk.Frame(density_frame)
    density_tools_frame.grid(row=len(density_rows) + 1, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 8))

    def collect_lighting_options_from_controls() -> LightingToolOptions:
        return normalize_lighting_options(
            LightingToolOptions(
                lighting_quality=selected_quality.get(),
                with_reflection_captures=reflection_captures_var.get(),
                open_lightmap_density_view=open_density_view_var.get(),
                min_lightmap_density=min_density_var.get(),
                ideal_lightmap_density=ideal_density_var.get(),
                max_lightmap_density=max_density_var.get(),
                lightmap_density_color_scale=color_scale_var.get(),
                lightmap_density_grayscale_scale=grayscale_scale_var.get(),
                render_lightmap_density_grayscale=render_grayscale_var.get(),
            )
        )

    def show_lighting_info(message: str) -> None:
        messagebox.showinfo("Lighting Options", message)

    def on_apply_density_settings() -> None:
        lighting_options = collect_lighting_options_from_controls()
        success, message = apply_lightmap_density_settings(lighting_options)
        if success and lighting_options.open_lightmap_density_view:
            _, view_message = activate_lightmap_density_view()
            message = f"{message}\n{view_message}"
        show_lighting_info(message)

    def on_lightmap_density_view() -> None:
        _, message = activate_lightmap_density_view()
        show_lighting_info(message)

    def on_lighting_only_view() -> None:
        _, message = activate_lighting_only_view()
        show_lighting_info(message)

    def on_native_lighting_actions() -> None:
        show_lighting_info(get_native_lighting_tools_message())

    tk.Button(density_tools_frame, text="Apply Density Settings", command=on_apply_density_settings).pack(side="left")
    tk.Button(density_tools_frame, text="Lightmap Density View", command=on_lightmap_density_view).pack(side="left", padx=(8, 0))
    tk.Button(density_tools_frame, text="Lighting Only View", command=on_lighting_only_view).pack(side="left", padx=(8, 0))
    tk.Button(density_tools_frame, text="Native Lighting Actions", command=on_native_lighting_actions).pack(side="left", padx=(8, 0))

    tk.Checkbutton(content_frame, text="Only buildable levels", variable=buildable_only_var, command=populate).pack(anchor="w", padx=12, pady=(0, 8))

    entry = tk.Entry(content_frame, textvariable=filter_var)
    entry.pack(fill="x", padx=12, pady=(0, 8))

    list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))
    listbox.pack(side="left", fill="both", expand=True)
    listbox_scrollbar.pack(side="right", fill="y")

    button_frame = tk.Frame(content_frame)
    button_frame.pack(fill="x", padx=12, pady=(0, 12))

    def on_rescan() -> None:
        nonlocal current_issue_map, current_precheck_source_label, current_precheck_generated_at
        current_issue_map = scan_levels_for_prebuild_issues(levels)
        current_precheck_generated_at = save_precheck_cache(levels, current_issue_map)
        current_precheck_source_label = "fresh scan"
        rescan_button.configure(state="normal")
        update_legend()
        populate()

    def on_clear_cache() -> None:
        nonlocal current_precheck_source_label, current_precheck_generated_at
        removed = clear_precheck_cache()
        if not has_precheck_run(current_precheck_source_label):
            current_precheck_source_label = "not run"
            current_precheck_generated_at = None
        update_legend()

        message = "Precheck cache cleared." if removed else "Precheck cache file was not present."
        messagebox.showinfo("Build Lighting", message)

    tk.Button(button_frame, text="Select All", command=lambda: listbox.select_set(0, tk.END)).pack(side="left")
    tk.Button(button_frame, text="Clear", command=lambda: listbox.selection_clear(0, tk.END)).pack(side="left", padx=(8, 0))
    tk.Button(button_frame, text="Refresh", command=populate).pack(side="left", padx=(8, 0))
    rescan_button = tk.Button(button_frame, text="Rescan Levels", command=on_rescan)
    rescan_button.pack(side="left", padx=(8, 0))
    tk.Button(button_frame, text="Load Cached Precheck", command=load_cached_precheck).pack(side="left", padx=(8, 0))
    tk.Button(button_frame, text="Clear Cache", command=on_clear_cache).pack(side="left", padx=(8, 0))
    tk.Button(button_frame, text="Run Precheck", command=run_precheck).pack(side="left", padx=(8, 0))
    tk.Button(button_frame, text="Audit Static Meshes", command=run_static_mesh_lightmap_audit).pack(side="left", padx=(8, 0))
    tk.Button(button_frame, text="Build Lighting", command=build_selected).pack(side="right")
    tk.Button(button_frame, text="Cancel", command=cancel).pack(side="right", padx=(0, 8))

    filter_var.trace_add("write", populate)
    update_legend()
    if not has_precheck_run(current_precheck_source_label):
        rescan_button.configure(state="disabled")
    populate()

    while True:
        try:
            root.update_idletasks()
            root.update()
        except tk.TclError:
            break

        time.sleep(0.01)

    try:
        page_canvas.unbind_all("<MouseWheel>")
    except tk.TclError:
        pass

    return BuildSelection(
        selected_levels,
        selected_lighting_options,
        dict(current_issue_map),
        current_precheck_source_label,
        current_precheck_generated_at,
    )


def choose_levels(
    levels: list[LevelEntry],
    issue_map: dict[str, LevelPrecheckResult],
    precheck_source_label: str,
    precheck_generated_at: str | None,
) -> BuildSelection:
    raise RuntimeError(
        "A non-blocking in-editor window requires PySide2 or PySide6. "
        "Tkinter is intentionally disabled here because it blocks the Unreal Editor thread."
    )


def main() -> None:
    levels = discover_levels()
    if not levels:
        message = f"No level files were found under {get_project_content_dir()}"
        unreal.log_warning(message)

        if hasattr(unreal, "EditorDialog"):
            unreal.EditorDialog.show_message("Build Lighting", message, unreal.AppMsgType.OK)
        return

    issue_map: dict[str, LevelPrecheckResult] = {}
    precheck_source_label = "not run"
    precheck_generated_at = None
    original_level_path = get_current_open_level_path()

    peu_launched, peu_message = launch_python_editor_utility_build_lighting_tool()
    if peu_launched:
        unreal.log(peu_message)
        return

    unreal.log_warning(peu_message)

    if launch_build_lighting_qt(
        levels,
        issue_map,
        precheck_source_label,
        precheck_generated_at,
        original_level_path,
    ):
        unreal.log("Build lighting tool opened as a modeless window.")
        return

    build_levels_without_custom_ui(levels, original_level_path)


if __name__ == "__main__":
    main()