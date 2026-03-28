import os

from project_path_utils import get_export_from_blender_dir, get_export_from_ue_dir


SOURCE_DIR = get_export_from_ue_dir(__file__)
DESTINATION_DIR = get_export_from_blender_dir(__file__)
DEFAULT_BLENDER_ENV_VAR = "BLENDER_EXECUTABLE"


def get_default_settings() -> dict:
    return {
        "source_dir": SOURCE_DIR,
        "destination_dir": DESTINATION_DIR,
        "blender_executable": os.environ.get(DEFAULT_BLENDER_ENV_VAR, ""),
    }


def build_preview(source_dir: str, destination_dir: str, blender_executable: str) -> dict:
    normalized_source = os.path.abspath(os.path.normpath(source_dir or SOURCE_DIR))
    normalized_destination = os.path.abspath(os.path.normpath(destination_dir or DESTINATION_DIR))
    normalized_blender = str(blender_executable or os.environ.get(DEFAULT_BLENDER_ENV_VAR, "")).strip()
    status_lines = [
        "Blender UV Fixer Pipeline",
        f"Source folder: {normalized_source}",
        f"Destination folder: {normalized_destination}",
        f"Blender executable: {normalized_blender or 'Use BLENDER_EXECUTABLE or PATH'}",
        "Run the example pipeline to simulate the headless batch flow used by the live project.",
    ]
    detail_lines = [
        f"Source folder: {normalized_source}",
        f"Destination folder: {normalized_destination}",
        f"Blender executable override: {normalized_blender or 'None'}",
        "This example does not invoke Blender. It demonstrates the same state contract and UI flow as the real project-owned batch tool.",
    ]
    return {
        "progress_text": "Idle",
        "progress_percent": 0.0,
        "status_text": "\n".join(status_lines),
        "detail_text": "\n".join(detail_lines),
    }


def run_pipeline(source_dir: str, destination_dir: str, blender_executable: str) -> dict:
    payload = build_preview(source_dir, destination_dir, blender_executable)
    payload["progress_text"] = "Completed"
    payload["progress_percent"] = 1.0
    payload["status_text"] += "\nCompleted example headless run with 3 sample FBX files."
    payload["detail_text"] += "\n\nSimulated actions:\n- Validate source and destination folders\n- Resolve Blender executable\n- Process 3 sample FBX files\n- Write fixed files to the destination folder"
    return payload
