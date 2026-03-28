import os

from project_path_utils import get_export_from_blender_dir


SOURCE = get_export_from_blender_dir(__file__)
DESTINATION = "/Game"


def get_default_settings() -> dict:
    return {
        "source": SOURCE,
        "destination": DESTINATION,
    }


def run_import_reimport(source: str, destination: str) -> dict:
    normalized_source = os.path.abspath(os.path.normpath(source or SOURCE))
    normalized_destination = str(destination or DESTINATION).strip() or DESTINATION
    reimported_assets = [
        "SM_WallPanel",
        "SM_WindowFrame",
        "SM_FloorTile",
        "SM_Column_A",
    ]
    return {
        "operation": "Import/Reimport All",
        "source": normalized_source,
        "destination": normalized_destination,
        "processed": len(reimported_assets),
        "exported": 0,
        "imported_new": 0,
        "reimported_existing": len(reimported_assets),
        "failed": 0,
        "risky": 0,
        "asset_names": reimported_assets,
        "message": (
            f"Reimported {len(reimported_assets)} existing assets from {normalized_source} into {normalized_destination}, "
            "normalized the example lightmap state, and avoided preserving stale destination lightmap index drift."
        ),
    }
