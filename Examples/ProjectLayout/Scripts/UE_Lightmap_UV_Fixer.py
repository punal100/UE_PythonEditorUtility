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
    from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty

    BLENDER_AVAILABLE = True
except ImportError:
    bpy = None
    bmesh = None
    BoolProperty = None
    EnumProperty = None
    FloatProperty = None
    PointerProperty = None
    BLENDER_AVAILABLE = False


bl_info = {
    "name": "UE Lightmap UV Fixer",
    "author": "Punal Manalan",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > UE Tools",
    "description": "Generate clean lightmap UVs for Unreal static meshes using Smart UV Project",
    "category": "UV",
}


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


def resolve_cli_export_preset(args):
    if args.export_preset_choice != DEFAULT_EXPORT_PRESET_CHOICE:
        return resolve_export_preset_name(args.export_preset_choice)
    if args.export_preset:
        return args.export_preset
    return ""


def validate_headless_args(args):
    if not args.input_fbx:
        raise RuntimeError("Headless single-file mode requires --input-fbx")
    if not args.output_fbx:
        raise RuntimeError("Headless single-file mode requires --output-fbx")


def build_headless_command(args):
    validate_headless_args(args)
    blender_executable = resolve_blender_executable(args.blender_exe)

    command = [
        blender_executable,
        "--background",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "--python",
        os.path.abspath(__file__),
        "--",
        "--headless",
        "--input-fbx",
        os.path.abspath(args.input_fbx),
        "--output-fbx",
        os.path.abspath(args.output_fbx),
        "--island-margin",
        str(args.island_margin),
        "--merge-distance",
        str(args.merge_distance),
        "--export-preset",
        resolve_cli_export_preset(args),
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


def get_selected_visual_meshes():
    return [obj for obj in bpy.context.selected_objects if obj.type == 'MESH' and not is_collision_object(obj)]


def get_blend_directory():
    if bpy.data.filepath:
        return os.path.dirname(bpy.data.filepath)
    return bpy.path.abspath("//")


def build_default_export_path(mesh_objects):
    if not mesh_objects:
        return ""

    first_mesh_name = normalize_object_name(mesh_objects[0].name)
    export_directory = get_blend_directory()
    if not export_directory:
        return f"{first_mesh_name}.fbx"

    return os.path.join(export_directory, f"{first_mesh_name}.fbx")


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

    items = [(DEFAULT_EXPORT_PRESET_CHOICE, "Auto / None", "Open Blender's native FBX exporter with its current defaults")]

    for preset_name in list_fbx_export_presets():
        items.append((preset_name, preset_name, f"Use the {preset_name} FBX export preset"))

    EXPORT_PRESET_ITEMS_CACHE = items
    return EXPORT_PRESET_ITEMS_CACHE


def resolve_export_preset_name(preset_choice):
    if preset_choice == DEFAULT_EXPORT_PRESET_CHOICE:
        return ""
    return preset_choice


def get_selected_meshes(ignore_collision):
    selected_meshes = []

    for obj in bpy.context.selected_objects:
        if obj.type != 'MESH':
            continue
        if ignore_collision and is_collision_object(obj):
            continue
        selected_meshes.append(obj)

    return selected_meshes


def get_selected_export_targets(ignore_collision=True):
    visual_meshes = get_selected_meshes(ignore_collision)
    if not visual_meshes:
        raise RuntimeError("Select at least one visual mesh to export")

    export_targets = list(visual_meshes)
    for collision_obj in find_linked_collision_meshes(visual_meshes):
        if collision_obj not in export_targets:
            export_targets.append(collision_obj)

    valid_export_targets, skipped_objects = filter_export_targets(export_targets)
    if skipped_objects:
        skipped_names = ", ".join(obj.name for obj in skipped_objects)
        print(f"Skipping invalid export objects: {skipped_names}")

    if not valid_export_targets:
        raise RuntimeError("No valid mesh objects available for export")

    return visual_meshes, valid_export_targets


def set_selected_objects(objects_to_select):
    ensure_object_mode()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects_to_select:
        obj.select_set(True)

    if objects_to_select:
        bpy.context.view_layer.objects.active = objects_to_select[0]


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


def apply_scale_to_objects(objects):
    if not objects:
        return

    ensure_object_mode()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)

    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)


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


def import_fbx_file(file_path):
    bpy.ops.import_scene.fbx(filepath=file_path)


def export_processed_meshes(export_path, preset_name, objects_to_export, mark_active):
    if not export_path:
        export_path = build_default_export_path(objects_to_export)

    if not export_path:
        raise RuntimeError("Choose an export FBX file path or select a visual mesh named SM_*")

    if not export_path.lower().endswith('.fbx'):
        export_path = f"{export_path}.fbx"

    export_directory = os.path.dirname(export_path)
    if export_directory:
        os.makedirs(export_directory, exist_ok=True)

    prepare_objects_for_export(objects_to_export, mark_active)
    set_selected_objects(objects_to_export)

    export_options = {
        'filepath': export_path,
        'use_selection': True,
    }
    if preset_name.strip():
        try:
            export_options.update(load_fbx_export_preset(preset_name.strip()))
        except FileNotFoundError:
            print(f"Warning: FBX export preset not found, using Blender defaults: {preset_name.strip()}")
    export_options['filepath'] = export_path
    export_options['use_selection'] = True

    bpy.ops.export_scene.fbx(**export_options)
    return export_path


def process_selected_meshes(
    island_margin,
    merge_by_distance,
    merge_distance,
    ignore_collision,
    apply_scale,
    mark_active,
):
    ensure_object_mode()

    original_selection = list(bpy.context.selected_objects)
    original_active = bpy.context.view_layer.objects.active
    target_meshes = get_selected_meshes(ignore_collision)

    if not target_meshes:
        raise RuntimeError("Select at least one visual mesh to process")

    processed_names = []
    for obj in target_meshes:
        clean_and_unwrap_object(
            obj=obj,
            island_margin=island_margin,
            merge_by_distance=merge_by_distance,
            merge_distance=merge_distance,
            mark_active=mark_active,
        )
        processed_names.append(obj.name)

    linked_collision_meshes = find_linked_collision_meshes(target_meshes)

    if apply_scale:
        scale_targets = list(target_meshes)
        for collision_obj in linked_collision_meshes:
            if collision_obj not in scale_targets:
                scale_targets.append(collision_obj)
        apply_scale_to_objects(scale_targets)

    ensure_object_mode()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in original_selection:
        if obj.name in bpy.data.objects:
            bpy.data.objects[obj.name].select_set(True)

    if original_active and original_active.name in bpy.data.objects:
        bpy.context.view_layer.objects.active = bpy.data.objects[original_active.name]

    return {
        'processed_names': processed_names,
        'linked_collision_names': [obj.name for obj in linked_collision_meshes],
    }


def process_headless_file(
    input_fbx,
    output_fbx,
    preset_name,
    island_margin,
    merge_by_distance,
    merge_distance,
    ignore_collision,
    apply_scale,
    mark_active,
):
    if not os.path.isfile(input_fbx):
        raise FileNotFoundError(f"Input FBX does not exist: {input_fbx}")

    clear_scene()
    import_fbx_file(input_fbx)

    target_meshes = get_selected_meshes(ignore_collision)
    if not target_meshes:
        target_meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and (not ignore_collision or not is_collision_object(obj))]

    if not target_meshes:
        raise RuntimeError("No visual mesh objects found after import")

    result = process_selected_meshes(
        island_margin=island_margin,
        merge_by_distance=merge_by_distance,
        merge_distance=merge_distance,
        ignore_collision=ignore_collision,
        apply_scale=apply_scale,
        mark_active=mark_active,
    )

    _visual_meshes, export_targets = get_selected_export_targets(ignore_collision=ignore_collision)
    exported_path = export_processed_meshes(output_fbx, preset_name, export_targets, mark_active)
    result['exported_path'] = exported_path
    return result


def parse_cli_args():
    argv = sys.argv
    cli_args = argv[argv.index('--') + 1:] if '--' in argv else argv[1:]

    parser = argparse.ArgumentParser(description='Generate Unreal-friendly lightmap UVs with Smart UV Project.')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--blender-exe', default='')
    parser.add_argument('--input-fbx', default='')
    parser.add_argument('--output-fbx', default='')
    parser.add_argument('--island-margin', type=float, default=DEFAULT_ISLAND_MARGIN)
    parser.add_argument('--merge-distance', type=float, default=DEFAULT_MERGE_DISTANCE)
    parser.add_argument('--disable-merge-by-distance', action='store_true')
    parser.add_argument('--include-collision', action='store_true')
    parser.add_argument('--disable-apply-scale', action='store_true')
    parser.add_argument('--disable-mark-active', action='store_true')
    parser.add_argument('--export-preset', default=DEFAULT_EXPORT_PRESET)
    parser.add_argument('--export-preset-choice', default=DEFAULT_EXPORT_PRESET_CHOICE)
    return parser.parse_args(cli_args)


if BLENDER_AVAILABLE:
    class UELightmapUVFixerProperties(bpy.types.PropertyGroup):
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
            description="Skip Unreal collision helper meshes such as UCX_ objects",
            default=DEFAULT_IGNORE_COLLISION,
        )
        apply_scale: BoolProperty(
            name="Apply Scale",
            description="Apply scale to the processed visual meshes and their linked UCX collision meshes",
            default=DEFAULT_APPLY_SCALE,
        )
        mark_active_for_export: BoolProperty(
            name="Mark UV Active",
            description="Make the generated lightmap UV the active render/export UV map",
            default=DEFAULT_MARK_ACTIVE_FOR_EXPORT,
        )
        export_preset_choice: EnumProperty(
            name="Preset List",
            description="Choose an available FBX preset or leave Auto / None to use Blender's current FBX defaults",
            items=get_export_preset_items,
        )


    class OBJECT_OT_FixUELightmapUVs(bpy.types.Operator):
        bl_idname = "object.fix_ue_lightmap_uvs"
        bl_label = "Fix Selected Meshes"
        bl_description = "Generate clean non-overlapping lightmap UVs for the selected Unreal meshes"
        bl_options = {'REGISTER', 'UNDO'}

        def execute(self, context):
            props = context.scene.ue_lightmap_uv_fixer_props

            try:
                result = process_selected_meshes(
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

            self.report({'INFO'}, f"Fixed lightmap UVs for {len(result['processed_names'])} mesh object(s)")
            return {'FINISHED'}


    class OBJECT_OT_ExportUEFBXMesh(bpy.types.Operator):
        bl_idname = "object.export_ue_fbx_mesh"
        bl_label = "Export FBX Mesh"
        bl_description = "Export the selected visual mesh and its linked UCX collision meshes to FBX"
        bl_options = {'REGISTER'}

        def invoke(self, context, _event):
            try:
                visual_meshes, export_targets = get_selected_export_targets(ignore_collision=True)
            except Exception as exc:
                self.report({'ERROR'}, str(exc))
                return {'CANCELLED'}

            panel_props = context.scene.ue_lightmap_uv_fixer_props
            resolved_export_preset = resolve_export_preset_name(panel_props.export_preset_choice)
            export_options = {
                'filepath': build_default_export_path(visual_meshes),
                'use_selection': True,
            }
            if resolved_export_preset:
                try:
                    export_options.update(load_fbx_export_preset(resolved_export_preset))
                except FileNotFoundError:
                    print(f"Warning: FBX export preset not found, using Blender defaults: {resolved_export_preset}")
            export_options['filepath'] = build_default_export_path(visual_meshes)
            export_options['use_selection'] = True

            prepare_objects_for_export(export_targets, panel_props.mark_active_for_export)
            set_selected_objects(export_targets)
            return bpy.ops.export_scene.fbx('INVOKE_DEFAULT', **export_options)


    class OBJECT_PT_UELightmapUVFixerPanel(bpy.types.Panel):
        bl_label = "UE Lightmap UV Fixer"
        bl_idname = "OBJECT_PT_ue_lightmap_uv_fixer"
        bl_space_type = 'VIEW_3D'
        bl_region_type = 'UI'
        bl_category = 'UE Tools'
        bl_options = {'DEFAULT_CLOSED'}

        def draw(self, context):
            layout = self.layout
            props = context.scene.ue_lightmap_uv_fixer_props

            selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
            selected_collision = [obj for obj in selected_meshes if is_collision_object(obj)]
            selected_visual = [obj for obj in selected_meshes if not is_collision_object(obj)]
            suggested_export_path = build_default_export_path(selected_visual)

            box = layout.box()
            box.label(text="Selection", icon='RESTRICT_SELECT_OFF')
            box.label(text=f"Visual Meshes: {len(selected_visual)}")
            box.label(text=f"Collision Meshes: {len(selected_collision)}")
            box.label(text="Select the visible mesh before running the tool")

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
            if suggested_export_path:
                col.label(text=f"Default file: {suggested_export_path}", icon='FILE')
                col.label(text="Export button opens Blender's native FBX export dialog", icon='INFO')
            else:
                col.label(text="Default file: select a visual SM_* mesh", icon='INFO')

            layout.separator()

            box = layout.box()
            box.label(text="Pipeline", icon='INFO')
            box.label(text="1. Select visual mesh objects")
            box.label(text="2. Tool skips UCX_ during unwrap but finds linked UCX_SM_* collisions")
            box.label(text="3. Apply Scale affects the visual mesh and its linked UCX collision meshes")
            box.label(text="4. Fix Selected Meshes updates the lightmap UV and scale only")
            box.label(text="5. Export FBX Mesh opens Blender's native FBX export dialog with SM_*.fbx filled in")
            box.label(text="6. Preset List preloads the native exporter with the chosen preset values")

            layout.separator()

            col = layout.column(align=True)
            col.scale_y = 1.2
            col.operator("object.fix_ue_lightmap_uvs", text="Fix Selected Meshes", icon='UV_DATA')
            col.operator("object.export_ue_fbx_mesh", text="Export FBX Mesh", icon='EXPORT')


def main():
    args = parse_cli_args()
    if args.headless and not BLENDER_AVAILABLE:
        run_headless_subprocess(args)
        return

    if not BLENDER_AVAILABLE:
        raise RuntimeError("This script must run inside Blender unless --headless is used.")

    if args.headless:
        result = process_headless_file(
            input_fbx=os.path.abspath(args.input_fbx),
            output_fbx=os.path.abspath(args.output_fbx),
            preset_name=resolve_cli_export_preset(args),
            island_margin=args.island_margin,
            merge_by_distance=not args.disable_merge_by_distance,
            merge_distance=args.merge_distance,
            ignore_collision=not args.include_collision,
            apply_scale=not args.disable_apply_scale,
            mark_active=not args.disable_mark_active,
        )
        print(f"Processed {len(result['processed_names'])} mesh object(s): {', '.join(result['processed_names'])}")
        print(f"Exported headless FBX: {result['exported_path']}")
        return

    result = process_selected_meshes(
        island_margin=args.island_margin,
        merge_by_distance=not args.disable_merge_by_distance,
        merge_distance=args.merge_distance,
        ignore_collision=not args.include_collision,
        apply_scale=not args.disable_apply_scale,
        mark_active=not args.disable_mark_active,
    )
    print(f"Processed {len(result['processed_names'])} mesh object(s): {', '.join(result['processed_names'])}")


if BLENDER_AVAILABLE:
    classes = (
        UELightmapUVFixerProperties,
        OBJECT_OT_FixUELightmapUVs,
        OBJECT_OT_ExportUEFBXMesh,
        OBJECT_PT_UELightmapUVFixerPanel,
    )


    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        bpy.types.Scene.ue_lightmap_uv_fixer_props = PointerProperty(type=UELightmapUVFixerProperties)
        initialize_runtime_defaults()


    def initialize_runtime_defaults():
        scene = bpy.context.scene
        if scene is None or not hasattr(scene, 'ue_lightmap_uv_fixer_props'):
            return

        props = scene.ue_lightmap_uv_fixer_props
        if not props.export_preset_choice:
            preset_names = list_fbx_export_presets()
            if DEFAULT_EXPORT_PRESET in preset_names:
                props.export_preset_choice = DEFAULT_EXPORT_PRESET
            else:
                props.export_preset_choice = DEFAULT_EXPORT_PRESET_CHOICE


    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
        del bpy.types.Scene.ue_lightmap_uv_fixer_props


if __name__ == '__main__':
    if '--' in sys.argv or not BLENDER_AVAILABLE:
        main()
    elif BLENDER_AVAILABLE:
        register()