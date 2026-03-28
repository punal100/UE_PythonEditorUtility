import os

from project_path_utils import get_export_from_ue_dir


SOURCE = "/Game"
DESTINATION = get_export_from_ue_dir(__file__)


def get_default_settings() -> dict:
    return {
        "source": SOURCE,
        "destination": DESTINATION,
    }


def run_export(source: str, destination: str) -> dict:
    normalized_source = str(source or SOURCE).strip() or SOURCE
    normalized_destination = os.path.abspath(os.path.normpath(destination or DESTINATION))
    asset_names = [
        "SM_WallPanel",
        "SM_WindowFrame",
        "SM_FloorTile",
        "SM_Column_A",
    ]
    return {
        "operation": "Export All",
        "source": normalized_source,
        "destination": normalized_destination,
        "processed": len(asset_names),
        "exported": len(asset_names),
        "imported_new": 0,
        "reimported_existing": 0,
        "failed": 0,
        "risky": 1,
        "asset_names": asset_names,
        "message": f"Exported {len(asset_names)} sample meshes from {normalized_source} to {normalized_destination}.",
    }
