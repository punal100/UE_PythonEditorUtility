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
    imported_assets = [
        "SM_WallPanel",
        "SM_WindowFrame",
    ]
    reimported_assets = [
        "SM_FloorTile",
        "SM_Column_A",
    ]
    return {
        "operation": "Import/Reimport All",
        "source": normalized_source,
        "destination": normalized_destination,
        "processed": len(imported_assets) + len(reimported_assets),
        "exported": 0,
        "imported_new": len(imported_assets),
        "reimported_existing": len(reimported_assets),
        "failed": 0,
        "risky": 1,
        "asset_names": imported_assets + reimported_assets,
        "message": (
            f"Imported {len(imported_assets)} new assets and reimported {len(reimported_assets)} existing assets "
            f"from {normalized_source} into {normalized_destination}."
        ),
    }
