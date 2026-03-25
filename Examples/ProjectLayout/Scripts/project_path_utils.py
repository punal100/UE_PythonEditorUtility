import os


_MESH_EXCHANGE_ROOT_PARTS = ("_Assets", "Mesh", "UE_Import_Export")
_EXPORT_FROM_UE_FOLDER = "Export_From_UE"
_EXPORT_FROM_BLENDER_FOLDER = "Export_From_Blender_For_Export_From_UE"


def get_scripts_dir(script_file: str) -> str:
    return os.path.abspath(os.path.dirname(script_file))


def get_project_dir(script_file: str) -> str:
    return os.path.abspath(os.path.join(get_scripts_dir(script_file), os.pardir))


def get_project_name(script_file: str) -> str:
    return os.path.basename(os.path.normpath(get_project_dir(script_file)))


def get_projects_root(script_file: str) -> str:
    return os.path.dirname(get_project_dir(script_file))


def build_mesh_exchange_dir(script_file: str, exchange_folder: str) -> str:
    return os.path.join(
        get_projects_root(script_file),
        *_MESH_EXCHANGE_ROOT_PARTS,
        exchange_folder,
        get_project_name(script_file),
    )


def get_export_from_ue_dir(script_file: str) -> str:
    return build_mesh_exchange_dir(script_file, _EXPORT_FROM_UE_FOLDER)


def get_export_from_blender_dir(script_file: str) -> str:
    return build_mesh_exchange_dir(script_file, _EXPORT_FROM_BLENDER_FOLDER)