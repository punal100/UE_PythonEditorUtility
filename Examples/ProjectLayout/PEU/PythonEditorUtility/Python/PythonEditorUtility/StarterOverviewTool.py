import json
import os

import unreal

from .ProjectIntegration import get_integration_root, get_state_dir, get_state_file_path, get_status_file_path, get_scripts_dir, load_script_module


_STATUS_FILE_NAME = "StarterOverviewStatus.txt"
_STATE_FILE_NAME = "StarterOverviewState.json"


def _get_state_file_path():
    return get_state_file_path(_STATE_FILE_NAME)


def _get_status_file_path():
    return get_status_file_path(_STATUS_FILE_NAME)


def _load_backend_module():
    return load_script_module("starter_catalog_backend", "starter_catalog.py")


def _write_payload(payload):
    state = {
        "headline": str(payload.get("headline", "Standalone host ready")),
        "summary_text": str(payload.get("summary_text", "This starter demonstrates project-owned integration content.")),
        "tool_count_text": str(payload.get("tool_count_text", "Starter tools discovered: 0")),
        "contract_text": str(payload.get("contract_text", "Do not modify plugin source. Replace the project-owned UI, controllers, and scripts in your own project.")),
        "detail_text": str(payload.get("detail_text", "")),
        "progress_percent": float(payload.get("progress_percent", 0.0)),
    }

    status_lines = payload.get(
        "status_lines",
        [
            state["headline"],
            state["summary_text"],
            state["tool_count_text"],
            state["contract_text"],
        ],
    )
    status_lines = [str(line) for line in status_lines]

    os.makedirs(get_state_dir(), exist_ok=True)
    with open(_get_state_file_path(), "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)

    with open(_get_status_file_path(), "w", encoding="utf-8") as handle:
        handle.write("\n".join(status_lines))

    for line in status_lines:
        unreal.log(line)


def _collect_payload(json_path):
    return _load_backend_module().collect_overview(
        json_path=str(json_path or ""),
        integration_root=get_integration_root(),
        scripts_dir=get_scripts_dir(),
        state_dir=get_state_dir(),
    )


def bootstrap(json_path):
    _write_payload(_collect_payload(json_path))


def refresh_status():
    _write_payload(_collect_payload(""))


def reset_example():
    payload = _load_backend_module().make_reset_payload(
        integration_root=get_integration_root(),
        scripts_dir=get_scripts_dir(),
        state_dir=get_state_dir(),
    )
    _write_payload(payload)