import sys
import git
from pathlib import Path


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
