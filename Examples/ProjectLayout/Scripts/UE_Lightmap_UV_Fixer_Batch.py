import argparse
import ast
import os
import re
import shutil
import subprocess
import sys

try:
    import bpy
    import bmesh
    from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty, StringProperty

    BLENDER_AVAILABLE = True
except ImportError:
    bpy = None
    bmesh = None
    BoolProperty = None
    EnumProperty = None
    FloatProperty = None
    PointerProperty = None
    StringProperty = None
    BLENDER_AVAILABLE = False

def resolve_script_file(script_file):
    candidate_paths = []

    if script_file:
        candidate_paths.append(script_file)
        candidate_paths.append(os.path.abspath(script_file))

    argv_script = sys.argv[0] if sys.argv else ""
    if argv_script:
        candidate_paths.append(argv_script)
        candidate_paths.append(os.path.abspath(argv_script))

    if BLENDER_AVAILABLE:
        base_name = os.path.basename(script_file or argv_script)
        for text_block in getattr(bpy.data, "texts", []):
            text_path = getattr(text_block, "filepath", "")
            if not text_path:
                continue
            if base_name and os.path.basename(text_path) != base_name:
                continue
            candidate_paths.append(text_path)
            candidate_paths.append(os.path.abspath(text_path))

    for candidate in candidate_paths:
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)

    return os.path.abspath(script_file)


SCRIPT_FILE = resolve_script_file(__file__)
SCRIPT_DIR = os.path.dirname(SCRIPT_FILE)

if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

bl_info = {
    "name": "UE Lightmap UV Fixer Batch",
    "author": "Punal Manalan",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > UE Tools",
    "description": "Bulk import FBX files, fix lightmap UVs, and export them with mirrored folder paths",
    "category": "Import-Export",
}


_MESH_EXCHANGE_ROOT_PARTS = ("_Assets", "Mesh", "UE_Import_Export")
_EXPORT_FROM_UE_FOLDER = "Export_From_UE"
_EXPORT_FROM_BLENDER_FOLDER = "Export_From_Blender_For_Export_From_UE"


def iter_candidate_project_paths():
    candidates = [
        SCRIPT_FILE,
        __file__,
        sys.argv[0] if sys.argv else "",
        os.getcwd(),
    ]

    if BLENDER_AVAILABLE:
        blend_file_path = getattr(bpy.data, 'filepath', '')
        if blend_file_path:
            candidates.append(blend_file_path)

        for text_block in getattr(bpy.data, 'texts', []):
            text_path = getattr(text_block, 'filepath', '')
            if text_path:
                candidates.append(text_path)

    seen = set()
    for candidate in candidates:
        if not candidate:
            continue

        normalized = os.path.abspath(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        yield normalized


def iter_parent_dirs(path):
    current = path if os.path.isdir(path) else os.path.dirname(path)
    while current:
        yield current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent


def find_project_root():
    checked_dirs = set()

    for candidate in iter_candidate_project_paths():
        for parent_dir in iter_parent_dirs(candidate):
            if parent_dir in checked_dirs:
                continue
            checked_dirs.add(parent_dir)

            try:
                entries = os.listdir(parent_dir)
            except OSError:
                continue

            uproject_names = sorted(
                entry for entry in entries if entry.lower().endswith('.uproject')
            )
            if not uproject_names:
                continue

            return parent_dir, os.path.splitext(uproject_names[0])[0]

    return None, None


def build_mesh_exchange_dir(project_dir, project_name, exchange_folder):
    if not project_dir or not project_name:
        return ""

    projects_root = os.path.dirname(project_dir)
    return os.path.join(
        projects_root,
        *_MESH_EXCHANGE_ROOT_PARTS,
        exchange_folder,
        project_name,
    )


PROJECT_DIR, PROJECT_NAME = find_project_root()


SOURCE_DIR = build_mesh_exchange_dir(PROJECT_DIR, PROJECT_NAME, _EXPORT_FROM_UE_FOLDER)
DESTINATION_DIR = build_mesh_exchange_dir(PROJECT_DIR, PROJECT_NAME, _EXPORT_FROM_BLENDER_FOLDER)
SOURCE_EXTENSIONS = {".fbx"}
DEFAULT_ISLAND_MARGIN = 0.05
DEFAULT_MERGE_DISTANCE = 0.0001
DEFAULT_IGNORE_COLLISION = True
DEFAULT_MERGE_BY_DISTANCE = True
DEFAULT_APPLY_SCALE = True
DEFAULT_MARK_ACTIVE_FOR_EXPORT = True
DEFAULT_EXPORT_PRESET = "UE Export"
DEFAULT_EXPORT_PRESET_CHOICE = "__AUTO__"
DEFAULT_BLENDER_ENV_VAR = "BLENDER_EXECUTABLE"
EXPORT_PRESET_ITEMS_CACHE = []

COLLISION_PREFIXES = (
    "UCX_",
    "UBX_",
    "USP_",
    "UCP_",
    "MCDCX_",
)


def resolve_blender_executable(explicit_path):
    candidates = []
    if explicit_path:
        candidates.append(explicit_path)

    env_path = os.environ.get(DEFAULT_BLENDER_ENV_VAR, "").strip()
    if env_path:
        candidates.append(env_path)

    for program_name in ("blender", "blender.exe"):
        discovered = shutil.which(program_name)
        if discovered:
            candidates.append(discovered)

    for candidate in candidates:
        normalized = os.path.abspath(os.path.expanduser(candidate))
        if os.path.isfile(normalized):
            return normalized

    raise RuntimeError(
        "Could not find Blender. Pass --blender-exe or set the BLENDER_EXECUTABLE environment variable."
    )


def build_headless_command(args):
    command = [
        resolve_blender_executable(args.blender_exe),
        "--background",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "--python",
        os.path.abspath(__file__),
        "--",
        "--headless",
        "--source-dir",
        os.path.abspath(args.source_dir),
        "--destination-dir",
        os.path.abspath(args.destination_dir),
        "--island-margin",
        str(args.island_margin),
        "--merge-distance",
        str(args.merge_distance),
        "--export-preset-choice",
        args.export_preset_choice,
    ]

    if args.disable_merge_by_distance:
        command.append("--disable-merge-by-distance")
    if args.include_collision:
        command.append("--include-collision")
    if args.disable_apply_scale:
        command.append("--disable-apply-scale")
    if args.disable_mark_active:
        command.append("--disable-mark-active")

    return command


def run_headless_subprocess(args):
    completed = subprocess.run(build_headless_command(args), check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    return completed.returncode


def is_collision_object(obj):
    return obj.type == 'MESH' and obj.name.upper().startswith(COLLISION_PREFIXES)


def normalize_object_name(name):
    return re.sub(r"\.\d{3}$", "", name)


def get_collision_root_name(name):
    normalized_name = normalize_object_name(name)
    upper_name = normalized_name.upper()

    for prefix in COLLISION_PREFIXES:
        if upper_name.startswith(prefix):
            return normalized_name[len(prefix):]

    return normalized_name


def ensure_object_mode():
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')


def clear_scene():
    ensure_object_mode()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    for collection in (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.images,
        bpy.data.armatures,
        bpy.data.actions,
    ):
        for block in list(collection):
            if block.users == 0:
                collection.remove(block)

    if hasattr(bpy.ops.outliner, 'orphans_purge'):
        bpy.ops.outliner.orphans_purge(do_recursive=True)


def list_source_files(source_root):
    file_paths = []

    for root, _, files in os.walk(source_root):
        for file_name in files:
            if os.path.splitext(file_name)[1].lower() in SOURCE_EXTENSIONS:
                file_paths.append(os.path.join(root, file_name))

    return sorted(file_paths, key=str.casefold)


def build_destination_path(source_path, source_root, destination_root):
    relative_path = os.path.relpath(source_path, source_root)
    return os.path.join(destination_root, relative_path)


def list_fbx_export_presets():
    preset_names = []

    for preset_root in bpy.utils.preset_paths(subdir=os.path.join("operator", "export_scene.fbx")):
        if not os.path.isdir(preset_root):
            continue

        for file_name in os.listdir(preset_root):
            if not file_name.lower().endswith('.py'):
                continue
            preset_names.append(os.path.splitext(file_name)[0])

    return sorted(set(preset_names), key=str.casefold)


def get_export_preset_items(_self, _context):
    global EXPORT_PRESET_ITEMS_CACHE

    items = [(DEFAULT_EXPORT_PRESET_CHOICE, "Auto / None", "Use Blender's current FBX defaults")]
    for preset_name in list_fbx_export_presets():
        items.append((preset_name, preset_name, f"Use the {preset_name} FBX export preset"))

    EXPORT_PRESET_ITEMS_CACHE = items
    return EXPORT_PRESET_ITEMS_CACHE


def resolve_export_preset_name(preset_choice):
    if preset_choice == DEFAULT_EXPORT_PRESET_CHOICE:
        return ""
    return preset_choice


def load_fbx_export_preset(preset_name):
    if not preset_name:
        return {}

    preset_file_name = f"{preset_name}.py"
    for preset_root in bpy.utils.preset_paths(subdir=os.path.join("operator", "export_scene.fbx")):
        preset_path = os.path.join(preset_root, preset_file_name)
        if not os.path.isfile(preset_path):
            continue

        with open(preset_path, 'r', encoding='utf-8') as preset_file:
            preset_source = preset_file.read()

        preset_values = {}
        parsed_module = ast.parse(preset_source, filename=preset_path)
        for node in parsed_module.body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue

            target = node.targets[0]
            if not isinstance(target, ast.Attribute):
                continue
            if not isinstance(target.value, ast.Name) or target.value.id != 'op':
                continue
            if target.attr == 'filepath':
                continue

            preset_values[target.attr] = ast.literal_eval(node.value)

        return preset_values

    raise FileNotFoundError(f"FBX export preset not found: {preset_name}")


def find_linked_collision_meshes(visual_objects):
    if not visual_objects:
        return []

    visual_root_names = [normalize_object_name(obj.name) for obj in visual_objects]
    linked_collisions = []

    for obj in bpy.context.scene.objects:
        if not is_collision_object(obj):
            continue

        collision_root = get_collision_root_name(obj.name)
        for visual_root in visual_root_names:
            if collision_root == visual_root or collision_root.startswith(f"{visual_root}_"):
                linked_collisions.append(obj)
                break

    return linked_collisions


def is_valid_export_mesh(obj):
    if obj is None or obj.type != 'MESH' or obj.data is None:
        return False

    return len(obj.data.polygons) > 0


def filter_export_targets(objects_to_export):
    valid_objects = []
    skipped_objects = []

    for obj in objects_to_export:
        if is_valid_export_mesh(obj):
            valid_objects.append(obj)
            continue

        skipped_objects.append(obj)

    return valid_objects, skipped_objects


def get_scene_visual_meshes(ignore_collision):
    visual_meshes = []

    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        if ignore_collision and is_collision_object(obj):
            continue
        visual_meshes.append(obj)

    return visual_meshes


def activate_only(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def ensure_single_user_mesh_data(obj):
    if obj.data.users > 1:
        obj.data = obj.data.copy()


def set_uv_layer_active_flags(mesh_data, uv_layer, mark_active):
    mesh_data.uv_layers.active = uv_layer

    for layer in mesh_data.uv_layers:
        if hasattr(layer, 'active_render'):
            layer.active_render = False

    if mark_active and hasattr(uv_layer, 'active_render'):
        uv_layer.active_render = True


def ensure_lightmap_uv_layer(mesh_data, mark_active):
    if len(mesh_data.uv_layers) == 0:
        mesh_data.uv_layers.new(name="UVmap_0")
    else:
        mesh_data.uv_layers[0].name = "UVmap_0"

    if len(mesh_data.uv_layers) >= 2:
        uv_layer = mesh_data.uv_layers[1]
    else:
        uv_layer = mesh_data.uv_layers.new(name="LightMapUV")

    uv_layer.name = "LightMapUV"
    set_uv_layer_active_flags(mesh_data, uv_layer, mark_active)

    return uv_layer


def finalize_mesh_after_uv_edit(obj, mark_active):
    mesh_data = obj.data
    uv_layer = ensure_lightmap_uv_layer(mesh_data, mark_active)
    set_uv_layer_active_flags(mesh_data, uv_layer, mark_active)
    mesh_data.update()


def prepare_objects_for_export(objects_to_export, mark_active):
    for obj in objects_to_export:
        if obj.type != 'MESH' or obj.data is None or len(obj.data.polygons) == 0:
            continue

        finalize_mesh_after_uv_edit(obj, mark_active)


def clean_and_unwrap_object(obj, island_margin, merge_by_distance, merge_distance, mark_active):
    ensure_single_user_mesh_data(obj)
    activate_only(obj)
    bpy.ops.object.mode_set(mode='EDIT')

    mesh = obj.data
    ensure_lightmap_uv_layer(mesh, mark_active)

    bm = bmesh.from_edit_mesh(mesh)
    for face in bm.faces:
        face.select = True
    bmesh.update_edit_mesh(mesh)

    bpy.ops.mesh.select_all(action='SELECT')

    if merge_by_distance:
        bpy.ops.mesh.remove_doubles(threshold=merge_distance)

    bpy.ops.uv.smart_project(
        island_margin=island_margin,
        area_weight=0.0,
        correct_aspect=True,
        scale_to_bounds=False,
    )

    bpy.ops.object.mode_set(mode='OBJECT')
    finalize_mesh_after_uv_edit(obj, mark_active)


def set_selected_objects(objects_to_select):
    ensure_object_mode()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects_to_select:
        obj.select_set(True)

    if objects_to_select:
        bpy.context.view_layer.objects.active = objects_to_select[0]


def apply_scale_to_objects(objects):
    if not objects:
        return

    set_selected_objects(objects)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)


def import_fbx_file(file_path):
    bpy.ops.import_scene.fbx(filepath=file_path)


def export_fbx_file(file_path, preset_name, objects_to_export, mark_active):
    if not file_path.lower().endswith('.fbx'):
        file_path = f"{file_path}.fbx"

    export_directory = os.path.dirname(file_path)
    if export_directory:
        os.makedirs(export_directory, exist_ok=True)

    export_options = {
        'filepath': file_path,
        'use_selection': True,
    }
    if preset_name:
        try:
            export_options.update(load_fbx_export_preset(preset_name))
        except FileNotFoundError:
            print(f"Warning: FBX export preset not found, using Blender defaults: {preset_name}")
    export_options['filepath'] = file_path
    export_options['use_selection'] = True

    prepare_objects_for_export(objects_to_export, mark_active)
    set_selected_objects(objects_to_export)
    bpy.ops.export_scene.fbx(**export_options)
    return file_path


def process_current_scene(island_margin, merge_by_distance, merge_distance, ignore_collision, apply_scale, mark_active):
    target_meshes = get_scene_visual_meshes(ignore_collision)
    if not target_meshes:
        raise RuntimeError("No visual mesh objects found after import")

    for obj in target_meshes:
        clean_and_unwrap_object(
            obj=obj,
            island_margin=island_margin,
            merge_by_distance=merge_by_distance,
            merge_distance=merge_distance,
            mark_active=mark_active,
        )

    linked_collision_meshes = find_linked_collision_meshes(target_meshes)

    if apply_scale:
        scale_targets = list(target_meshes)
        for collision_obj in linked_collision_meshes:
            if collision_obj not in scale_targets:
                scale_targets.append(collision_obj)
        apply_scale_to_objects(scale_targets)

    export_targets = list(target_meshes)
    for collision_obj in linked_collision_meshes:
        if collision_obj not in export_targets:
            export_targets.append(collision_obj)

    valid_export_targets, skipped_objects = filter_export_targets(export_targets)

    if skipped_objects:
        skipped_names = ", ".join(obj.name for obj in skipped_objects)
        print(f"Skipping invalid export objects: {skipped_names}")

    if not valid_export_targets:
        raise RuntimeError("No valid mesh objects available for export")

    return {
        'mesh_names': [obj.name for obj in target_meshes],
        'collision_names': [obj.name for obj in linked_collision_meshes],
        'skipped_export_names': [obj.name for obj in skipped_objects],
        'export_targets': valid_export_targets,
    }


def process_fbx_batch(source_dir, destination_dir, preset_choice, island_margin, merge_by_distance, merge_distance, ignore_collision, apply_scale, mark_active):
    if not os.path.isdir(source_dir):
        raise FileNotFoundError(f"Source folder does not exist: {source_dir}")

    os.makedirs(destination_dir, exist_ok=True)

    source_files = list_source_files(source_dir)
    if not source_files:
        raise FileNotFoundError(f"No FBX files found in: {source_dir}")

    resolved_preset = resolve_export_preset_name(preset_choice)
    results = []

    for index, source_path in enumerate(source_files, start=1):
        clear_scene()
        import_fbx_file(source_path)

        scene_result = process_current_scene(
            island_margin=island_margin,
            merge_by_distance=merge_by_distance,
            merge_distance=merge_distance,
            ignore_collision=ignore_collision,
            apply_scale=apply_scale,
            mark_active=mark_active,
        )

        destination_path = build_destination_path(source_path, source_dir, destination_dir)
        exported_path = export_fbx_file(destination_path, resolved_preset, scene_result['export_targets'], mark_active)

        result = {
            'index': index,
            'source_path': source_path,
            'exported_path': exported_path,
            'mesh_count': len(scene_result['mesh_names']),
            'collision_count': len(scene_result['collision_names']),
            'skipped_export_count': len(scene_result['skipped_export_names']),
        }
        results.append(result)
        if scene_result['skipped_export_names']:
            skipped_names = ", ".join(scene_result['skipped_export_names'])
            print(f"[{index}/{len(source_files)}] Processed {source_path} -> {exported_path} | Skipped: {skipped_names}")
        else:
            print(f"[{index}/{len(source_files)}] Processed {source_path} -> {exported_path}")

    return results


def parse_cli_args():
    argv = sys.argv
    cli_args = argv[argv.index('--') + 1:] if '--' in argv else argv[1:]

    parser = argparse.ArgumentParser(description='Bulk import FBX files, fix lightmap UVs, and export mirrored results.')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--blender-exe', default='')
    parser.add_argument('--source-dir', default=SOURCE_DIR)
    parser.add_argument('--destination-dir', default=DESTINATION_DIR)
    parser.add_argument('--island-margin', type=float, default=DEFAULT_ISLAND_MARGIN)
    parser.add_argument('--merge-distance', type=float, default=DEFAULT_MERGE_DISTANCE)
    parser.add_argument('--disable-merge-by-distance', action='store_true')
    parser.add_argument('--include-collision', action='store_true')
    parser.add_argument('--disable-apply-scale', action='store_true')
    parser.add_argument('--disable-mark-active', action='store_true')
    parser.add_argument('--export-preset-choice', default=DEFAULT_EXPORT_PRESET_CHOICE)
    return parser.parse_args(cli_args)


if BLENDER_AVAILABLE:
    class UELightmapUVFixerBatchProperties(bpy.types.PropertyGroup):
        source_dir: StringProperty(
            name="Source Folder",
            description="Folder containing FBX files exported from Unreal",
            default=SOURCE_DIR,
            subtype='DIR_PATH',
        )
        destination_dir: StringProperty(
            name="Destination Folder",
            description="Folder where processed FBX files will be exported",
            default=DESTINATION_DIR,
            subtype='DIR_PATH',
        )
        island_margin: FloatProperty(
            name="Island Margin",
            description="Spacing between UV islands to reduce shadow bleeding in Unreal",
            default=DEFAULT_ISLAND_MARGIN,
            min=0.0,
            soft_max=1.0,
            precision=4,
        )
        merge_by_distance: BoolProperty(
            name="Merge By Distance",
            description="Clean hidden duplicate vertices before creating the lightmap UV",
            default=DEFAULT_MERGE_BY_DISTANCE,
        )
        merge_distance: FloatProperty(
            name="Merge Distance",
            description="Distance used when removing overlapping vertices",
            default=DEFAULT_MERGE_DISTANCE,
            min=0.0,
            precision=6,
        )
        ignore_collision: BoolProperty(
            name="Ignore UCX Collision",
            description="Skip Unreal collision helper meshes such as UCX_ objects during unwrap",
            default=DEFAULT_IGNORE_COLLISION,
        )
        apply_scale: BoolProperty(
            name="Apply Scale",
            description="Apply scale to visual meshes and their linked UCX collision meshes before export",
            default=DEFAULT_APPLY_SCALE,
        )
        mark_active_for_export: BoolProperty(
            name="Mark UV Active",
            description="Make the generated lightmap UV the active export UV map",
            default=DEFAULT_MARK_ACTIVE_FOR_EXPORT,
        )
        export_preset_choice: EnumProperty(
            name="Preset List",
            description="Choose an available FBX preset or leave Auto / None to use Blender defaults",
            items=get_export_preset_items,
        )


    class OBJECT_OT_ProcessUELightmapUVBatch(bpy.types.Operator):
        bl_idname = "object.process_ue_lightmap_uv_batch"
        bl_label = "Bulk Import Fix Export"
        bl_description = "Import every FBX in the source folder, fix lightmap UVs, and export to the mirrored destination folder"
        bl_options = {'REGISTER'}

        def execute(self, context):
            props = context.scene.ue_lightmap_uv_fixer_batch_props

            try:
                results = process_fbx_batch(
                    source_dir=bpy.path.abspath(props.source_dir).strip(),
                    destination_dir=bpy.path.abspath(props.destination_dir).strip(),
                    preset_choice=props.export_preset_choice,
                    island_margin=props.island_margin,
                    merge_by_distance=props.merge_by_distance,
                    merge_distance=props.merge_distance,
                    ignore_collision=props.ignore_collision,
                    apply_scale=props.apply_scale,
                    mark_active=props.mark_active_for_export,
                )
            except Exception as exc:
                self.report({'ERROR'}, str(exc))
                return {'CANCELLED'}

            self.report({'INFO'}, f"Processed {len(results)} FBX file(s)")
            return {'FINISHED'}


    class OBJECT_PT_UELightmapUVFixerBatchPanel(bpy.types.Panel):
        bl_label = "UE Lightmap UV Fixer Batch"
        bl_idname = "OBJECT_PT_ue_lightmap_uv_fixer_batch"
        bl_space_type = 'VIEW_3D'
        bl_region_type = 'UI'
        bl_category = 'UE Tools'
        bl_options = {'DEFAULT_CLOSED'}

        def draw(self, context):
            layout = self.layout
            props = context.scene.ue_lightmap_uv_fixer_batch_props

            source_dir = bpy.path.abspath(props.source_dir).strip()
            destination_dir = bpy.path.abspath(props.destination_dir).strip()
            source_exists = bool(source_dir) and os.path.isdir(source_dir)
            destination_exists = bool(destination_dir) and os.path.isdir(destination_dir)
            source_count = len(list_source_files(source_dir)) if source_exists else 0

            box = layout.box()
            box.label(text="Folders", icon='FILE_FOLDER')
            col = box.column(align=True)
            col.prop(props, "source_dir")
            col.prop(props, "destination_dir")
            if source_exists:
                col.label(text=f"Source FBX files: {source_count}", icon='FILE_3D')
            else:
                col.label(text="Source folder not found", icon='ERROR')
            if destination_exists:
                col.label(text="Destination folder ready", icon='CHECKMARK')
            else:
                col.label(text="Destination folder will be created", icon='INFO')

            layout.separator()

            box = layout.box()
            box.label(text="Lightmap UV", icon='UV')
            col = box.column(align=True)
            col.prop(props, "island_margin")
            col.prop(props, "mark_active_for_export")
            col.label(text="UV channel 0 stays texture UV; channel 1 is LightMapUV", icon='GROUP_UVS')
            col.label(text="Only LightMapUV is rebuilt to be non-overlapping", icon='INFO')

            layout.separator()

            box = layout.box()
            box.label(text="Cleanup", icon='MESH_DATA')
            col = box.column(align=True)
            col.prop(props, "merge_by_distance")
            sub = col.column(align=True)
            sub.enabled = props.merge_by_distance
            sub.prop(props, "merge_distance")
            col.prop(props, "ignore_collision")
            col.prop(props, "apply_scale")

            layout.separator()

            box = layout.box()
            box.label(text="Export", icon='EXPORT')
            col = box.column(align=True)
            col.prop(props, "export_preset_choice")
            col.label(text="Subfolder structure is mirrored from Source to Destination", icon='INFO')

            layout.separator()

            box = layout.box()
            box.label(text="Pipeline", icon='INFO')
            box.label(text="1. Import every FBX under Source Folder")
            box.label(text="2. Fix lightmap UVs on visual meshes only")
            box.label(text="3. Apply scale to visual meshes and linked UCX collisions")
            box.label(text="4. Export to Destination with matching subfolders")
            box.label(text="5. Output is ready for the Unreal bulk reimport script")

            layout.separator()

            row = layout.row(align=True)
            row.scale_y = 1.3
            row.operator("object.process_ue_lightmap_uv_batch", text="Bulk Import Fix Export", icon='FILE_REFRESH')


def main():
    args = parse_cli_args()
    if args.headless and not BLENDER_AVAILABLE:
        run_headless_subprocess(args)
        return

    if not BLENDER_AVAILABLE:
        raise RuntimeError("This script must run inside Blender unless --headless is used.")

    results = process_fbx_batch(
        source_dir=args.source_dir,
        destination_dir=args.destination_dir,
        preset_choice=args.export_preset_choice,
        island_margin=args.island_margin,
        merge_by_distance=not args.disable_merge_by_distance,
        merge_distance=args.merge_distance,
        ignore_collision=not args.include_collision,
        apply_scale=not args.disable_apply_scale,
        mark_active=not args.disable_mark_active,
    )
    print(f"Processed {len(results)} FBX file(s)")


if BLENDER_AVAILABLE:
    classes = (
        UELightmapUVFixerBatchProperties,
        OBJECT_OT_ProcessUELightmapUVBatch,
        OBJECT_PT_UELightmapUVFixerBatchPanel,
    )


    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        bpy.types.Scene.ue_lightmap_uv_fixer_batch_props = PointerProperty(type=UELightmapUVFixerBatchProperties)
        initialize_runtime_defaults()


    def initialize_runtime_defaults():
        scene = bpy.context.scene
        if scene is None or not hasattr(scene, 'ue_lightmap_uv_fixer_batch_props'):
            return

        props = scene.ue_lightmap_uv_fixer_batch_props
        if not props.export_preset_choice:
            preset_names = list_fbx_export_presets()
            if DEFAULT_EXPORT_PRESET in preset_names:
                props.export_preset_choice = DEFAULT_EXPORT_PRESET
            else:
                props.export_preset_choice = DEFAULT_EXPORT_PRESET_CHOICE


    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
        del bpy.types.Scene.ue_lightmap_uv_fixer_batch_props


if __name__ == '__main__':
    if '--' in sys.argv or not BLENDER_AVAILABLE:
        main()
    elif BLENDER_AVAILABLE:
        register()