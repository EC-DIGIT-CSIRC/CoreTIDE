import sys
import git
import os
import toml
from pathlib import Path
from collections.abc import MutableMapping as Map

def resolve_configurations()->dict[str, dict]:
    def recursive_dict_merge(source_dict, merge_dict):
        """
        Recursive dict merge. Mitigation for dict.update() which will not resolve
        two dictionaries with common nested keys and just overwrite from the top level.
        """
        for key in merge_dict:
            if (
                key in source_dict
                and isinstance(source_dict[key], Map)
                and isinstance(merge_dict[key], Map)
            ):
                recursive_dict_merge(source_dict[key], merge_dict[key])
            else:
                source_dict[key] = merge_dict[key]


    def fetch_configs(configuration_path:Path)->dict[str, dict]:
        
        config_index = dict()
        for entry in os.listdir(configuration_path):
            # If there are loose top level files, indexes them
            if os.path.isfile(configuration_path / entry):
                config_index[entry.removesuffix(".toml")] = toml.load(
                    open(configuration_path / entry, encoding="utf-8")
                )
            # Some configurations, especially for recomposition, are namespaced within folders.
            elif os.path.isdir(configuration_path / entry):
                config_index[entry] = dict()
                for config in os.listdir(configuration_path / entry):
                    configuration = toml.load(
                        open(configuration_path / entry / config, encoding="utf-8")
                    )
                    config = configuration.get("tide", {}).get(
                        "identifier"
                    ) or config.removesuffix(".toml")
                    config_index[entry][config] = configuration
        
        return config_index

    PATHS = resolve_paths()
    core_configs = fetch_configs(PATHS["configurations"])
    unified_configs = core_configs.copy()
    custom_configs = fetch_configs(PATHS["custom_configurations"])
    
    recursive_dict_merge(unified_configs, custom_configs)

    return unified_configs

def resolve_paths() -> dict[str, Path]:
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
