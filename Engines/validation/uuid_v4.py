import pandas as pd
import os
import git
import sys
from uuid import UUID

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logs import log
from Engines.modules.tide import DataTide

MODELS_INDEX = DataTide.Models.Index


def run():

    log("TITLE", "MDR UUIDv4 Validation")
    log("INFO", "Validates UUID against v4 specification using the standard library")

    error_registry = list()
    counter = 0

    for mdr in MODELS_INDEX["mdr"]:
        mdr_data = MODELS_INDEX["mdr"][mdr]

        mdr_uuid = mdr_data["uuid"]
        mdr_name = mdr_data["name"]
        mdr_metadata = mdr_data.get("metadata") or mdr_data["meta"]
        mdr_author = mdr_metadata["author"]

        try:
            UUID(mdr_uuid, version=4)
        except ValueError:
            error_registry.append(
                {"MDR Name": mdr_name, "UUID": mdr_uuid, "Author": mdr_author}
            )

        counter += 1

    if error_registry:
        os.environ["VALIDATION_ERROR_RAISED"] = "True"
        log(
            "WARNING",
            f"⚠️ Successfully validated {counter} MDRs but found",
            f"{len(error_registry)} invalid ones",
        )
        error_table = pd.DataFrame(error_registry).to_markdown(
            index=False, tablefmt="fancy_grid"
        )
        print(error_table)
        log("FAILURE", "Failed UUID validation")

    else:
        log("SUCCESS", "Successfully validated", f"{counter} MDRs")


if __name__ == "__main__":
    run()
