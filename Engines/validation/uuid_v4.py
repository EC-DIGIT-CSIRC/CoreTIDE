import pandas as pd
import os
import git
import sys
from uuid import UUID

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logs import log
from Engines.modules.tide import DataTide
from Engines.modules.files import resolve_configurations

MODELS_INDEX = DataTide.Models.Index
CONFIGURATIONS = resolve_configurations()
MODELS_TYPES = CONFIGURATIONS["global"]["models"]


def run():

    log("TITLE", "tide_object UUIDv4 Validation")
    log("INFO", "Validates Object UUIDs against the v4 specification")

    error_registry = list()
    counter = 0

    for tide_model in MODELS_TYPES:
        for tide_object in MODELS_INDEX[tide_model]:
            tide_object_data = MODELS_INDEX[tide_model][tide_object]

            tide_object_uuid = tide_object_data.get("uuid") or tide_object_data["metadata"]["uuid"]
            tide_object_name = tide_object_data["name"]
            tide_object_metadata = tide_object_data.get("metadata") or tide_object_data["meta"]
            tide_object_author = tide_object_metadata["author"]

            try:
                UUID(tide_object_uuid, version=4)
            except ValueError:
                error_registry.append(
                    {"Object Name": tide_object_name, "UUID": tide_object_uuid, "Author": tide_object_author}
                )

            counter += 1

    if error_registry:
        os.environ["VALIDATION_ERROR_RAISED"] = "True"
        log(
            "WARNING",
            f"⚠️ Successfully validated {counter} tide_objects but found",
            f"{len(error_registry)} invalid ones",
        )
        error_table = pd.DataFrame(error_registry).to_markdown(
            index=False, tablefmt="fancy_grid"
        )
        print(error_table)
        log("FAILURE", "Failed UUID validation")

    else:
        log("SUCCESS", "Successfully validated", f"{counter} tide_objects")


if __name__ == "__main__":
    run()
