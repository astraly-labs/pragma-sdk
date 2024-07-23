from pydantic import FilePath, ValidationError


def is_file(maybe_path: str) -> bool:
    """
    Returns true if the string passed as argument is a valid file path.
    """
    try:
        FilePath(maybe_path)
        return True
    except ValidationError:
        return False
