import os
import importlib.util
import sys

from pathlib import Path

PACKAGE_PATH = Path(__file__).parent.parent / "pragma_sdk"


def _import_from_path(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)


def check_circular_imports():
    for path, _, files in os.walk(PACKAGE_PATH):
        py_files = [f for f in files if f.endswith(".py")]
        for file_ in py_files:
            file_path = os.path.join(path, file_)
            _import_from_path(file_, file_path)


if __name__ == "__main__":
    check_circular_imports()
    print("✅ No circular imports found!")
