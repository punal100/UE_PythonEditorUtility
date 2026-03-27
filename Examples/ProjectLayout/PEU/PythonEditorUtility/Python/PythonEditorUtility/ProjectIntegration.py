import importlib.util
import os

import unreal


def get_project_dir() -> str:
    return os.path.abspath(os.path.normpath(unreal.Paths.project_dir()))


def get_default_workspace_root() -> str:
    return get_project_dir()


def get_integration_root() -> str:
    package_root = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.normpath(os.path.join(package_root, os.pardir, os.pardir)))


def get_state_dir() -> str:
    state_dir = os.path.join(get_integration_root(), "State")
    os.makedirs(state_dir, exist_ok=True)
    return state_dir


def get_state_file_path(file_name: str) -> str:
    return os.path.join(get_state_dir(), str(file_name))


def get_status_file_path(file_name: str) -> str:
    return get_state_file_path(file_name)


def get_scripts_dir() -> str:
    return os.path.join(get_project_dir(), "Scripts")


def get_script_path(script_file_name: str) -> str:
    return os.path.join(get_scripts_dir(), str(script_file_name))


def load_script_module(module_name: str, script_file_name: str):
    script_path = get_script_path(script_file_name)
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load script module from {script_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call_script(module_name: str, script_file_name: str, function_name: str, *args, **kwargs):
    module = load_script_module(module_name, script_file_name)
    function = getattr(module, function_name, None)
    if function is None:
        raise RuntimeError(f"{script_file_name} does not define {function_name}()")
    return function(*args, **kwargs)