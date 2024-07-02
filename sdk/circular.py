import importlib.util
import os
import sys


def _import_from_path(module_name: str, file_path: str) -> None:
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is not None:
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        if spec.loader is not None:
            spec.loader.exec_module(module)


def test_circular_imports() -> None:
    # Start from the src directory
    for path, _, files in os.walk("pragma"):
        py_files = [f for f in files if f.endswith(".py")]
        for file_ in py_files:
            file_path = os.path.join(path, file_)
            module_name = os.path.splitext(file_)[0]
            _import_from_path(module_name, file_path)


if __name__ == "__main__":
    test_circular_imports()
