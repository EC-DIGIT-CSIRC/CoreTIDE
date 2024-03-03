import sys
import git
import toml
from pathlib import Path


def absolute_paths() -> dict[str, Path]:
    ROOT = Path(str(git.Repo(".", search_parent_directories=True).working_dir))
    TIDE_CONFIG = toml.load(
        open(ROOT / "Configurations/global.toml", encoding="utf-8")
    )

    TIDE_PATHS = {
        k: (ROOT.parent / path) for k, path in TIDE_CONFIG["paths"]["tide"].items()
    }
    CORE_PATHS = {k: (ROOT / path) for k, path in TIDE_CONFIG["paths"]["core"].items()}

    return TIDE_PATHS | CORE_PATHS


def safe_file_name(string: str, safe_mode: bool = True) -> str:
    """
    Removes forbidden path character based on automatic OS detection.
    Useful when using human-written names to write a file name without running into
    OS issues.

    safe_mode removes all characters that are problematic across all platforms.
    """

    cleaned_string = str()

    FORBIDDEN_WINDOWS_ASCII = [">", "<", ":", '"', "\\", "/", "|", "?", "*"]
    FORBIDDEN_LINUX_ASCII = ["/"]

    if safe_mode:
        forbidden_characters = FORBIDDEN_WINDOWS_ASCII
        forbidden_characters.extend(FORBIDDEN_LINUX_ASCII)
        for char in string:
            if char not in forbidden_characters:
                cleaned_string += char

    else:
        platform = sys.platform
        if platform.startswith("linux"):
            for char in string:
                if char not in FORBIDDEN_LINUX_ASCII:
                    cleaned_string += char

        elif platform.startswith("win32"):
            for char in string:
                if char not in FORBIDDEN_WINDOWS_ASCII:
                    cleaned_string += char

    return cleaned_string
