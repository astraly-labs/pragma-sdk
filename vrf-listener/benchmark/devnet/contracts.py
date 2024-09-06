from typing import Optional

from pathlib import Path


def find_repo_root(start_directory: Path) -> Path:
    """Finds the root directory of the repo by walking up the directory tree
    and looking for a known file at the repo root.
    """
    current_directory = start_directory
    while current_directory != current_directory.parent:  # Stop at filesystem root
        if (current_directory / "pyproject.toml").is_file():
            return current_directory
        current_directory = current_directory.parent
    raise ValueError("Repository root not found!")


CURRENT_FILE_DIRECTORY = Path(__file__).parent
REPO_ROOT = find_repo_root(CURRENT_FILE_DIRECTORY).parent
SUBMODULE_DIR = REPO_ROOT / "pragma-oracle"
CONTRACTS_COMPILED_DIR = SUBMODULE_DIR / "target/dev"


def read_contract(file_name: str, *, directory: Optional[Path] = None) -> str:
    """
    Return contents of file_name from directory.
    """
    if directory is None:
        directory = CONTRACTS_COMPILED_DIR

    if not directory.exists():
        raise ValueError(f"Directory {directory} does not exist!")

    return (directory / file_name).read_text("utf-8")
