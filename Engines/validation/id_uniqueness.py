import yaml
from pathlib import Path
import os
import git
import toml
import sys

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.documentation import get_icon
from Engines.modules.logs import log
from Engines.modules.files import resolve_paths

ROOT = Path(str(git.Repo(".", search_parent_directories=True).working_dir))

TIDE_CONFIG = toml.load(open(ROOT / "Configurations/global.toml", encoding="utf-8"))
METASCHEMAS = TIDE_CONFIG["metaschemas"]
SKIPS = ["logsources", "ram", "mdrv2", "lookup_metadata"]

PATHS = resolve_paths()

duplicates = list()
registry = dict()


def run():

    log("TITLE", "ID Duplication Checks")
    log("INFO", "Check if ID used in TIDeMEC are uniquely assigned")

    for meta_name in METASCHEMAS:
        if meta_name not in SKIPS:
            log(
                "ONGOING",
                "Now checking for id duplication in",
                f"{get_icon(meta_name)} {meta_name.upper()}...",
            )

            for model in os.listdir(PATHS[meta_name]):
                model_path = Path(PATHS[meta_name]) / model

                model_body = yaml.safe_load(open(model_path, encoding="utf-8"))

                if "uuid" in model_body.keys():
                    id = model_body["uuid"]
                else:
                    id = model_body["id"]

                file_name = model
                name = model_body["name"]

                # We check if there is a precedent for the id, if not we add as a reference
                if id not in registry:
                    registry[id] = {"name": name, "file_name": file_name}
                # If there is a precedent we move to an error list - allows multiple same mistakes
                else:
                    duplicates.append({"id": id, "name": name, "file_name": file_name})

    if duplicates:
        for dup in duplicates:
            original = registry[dup["id"]]
            original_name = original["name"]
            original_file_name = original["file_name"]
            log(
                "FAILURE",
                f"Duplicated ID found with {dup['id']} - {dup['name']} @ [{dup['file_name']}]",
                f"has the same id as {original_name} @ ({original_file_name})",
            )
        log("FATAL", "Cannot have duplicated IDs throughout multiple TIDeMEC objects")
        os.environ["VALIDATION_ERROR_RAISED"] = "True"

    else:
        log("SUCCESS", "No duplicated ID throughout", f"{len(registry)} objects")


if __name__ == "__main__":
    run()
