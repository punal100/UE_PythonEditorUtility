from .ProjectIntegration import call_script, write_tool_snapshot


_STATE_FILE = "BuildLightingState.json"
_STATUS_FILE = "BuildLightingStatus.txt"


def _save(payload: dict):
    write_tool_snapshot(_STATE_FILE, _STATUS_FILE, payload)


def refresh_status():
    _save(call_script("peu_example_build_lighting_refresh", "build_level_lighting.py", "build_refresh_snapshot"))


def run_precheck():
    _save(call_script("peu_example_build_lighting_precheck", "build_level_lighting.py", "build_precheck_snapshot"))


def build_lighting():
    _save(call_script("peu_example_build_lighting_run", "build_level_lighting.py", "build_run_snapshot"))


def open_options_file():
    _save(call_script("peu_example_build_lighting_options", "build_level_lighting.py", "build_options_snapshot"))


def show_native_lighting_actions():
    _save(call_script("peu_example_build_lighting_native_actions", "build_level_lighting.py", "build_native_actions_snapshot"))
