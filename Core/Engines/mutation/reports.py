import os
import git
from pathlib import Path
import toml
import sys

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Core.Engines.modules.logging import log


ROOT = Path(str(git.Repo(".", search_parent_directories=True).working_dir))

CONFIG = toml.load(open(ROOT / "Core/Configurations/global.toml", encoding="utf-8"))
REPORTS_FOLDER = ROOT / CONFIG["paths"]["tide"]["reports"]

DEFAULT_TLP_LEVEL = "[TLP AMBER+STRICT]"

REPORT_STD = "RPT"


def run():

    log("TITLE", "Reports ID & TLP Assigner")
    log("INFO", "Assigns an ID and a default TLP if not done manually")

    id_head = 0
    index_registry = list()

    for report_file in sorted(os.listdir(REPORTS_FOLDER)):

        if report_file.endswith("pdf"):
            parsed_file_name = report_file.split("-")
            new_name = parsed_file_name[-1]

            if not parsed_file_name[0].startswith("RPT"):
                index_registry.append(report_file)

            else:
                latest_id = int(parsed_file_name[0].split(REPORT_STD)[1])
                if latest_id > id_head:
                    id_head = latest_id

    if index_registry:
        log("INFO", f"Identified {len(index_registry)} report files to rename")
        for report_to_rename in index_registry:
            log("ONGOING", "Now processing report :", report_to_rename)

            id_head += 1
            new_name = report_to_rename

            if "TLP" not in report_to_rename.split("-")[0]:
                log(
                    "INFO",
                    f"No TLP level assigned in file name, assigning standard TLP level :",
                    DEFAULT_TLP_LEVEL,
                    "Consider adding your own TLP level in the file name. Do no forget to keep the dashes '-' to allow the file to be properly parsed",
                )
                new_name = f"{DEFAULT_TLP_LEVEL} - {report_to_rename}"

            assigned_id = f"{REPORT_STD}{str(id_head).zfill(4)}"
            new_name = f"{assigned_id} - {new_name}"
            log("ONGOING", f"Renaming report file {report_to_rename} to :", new_name)
            os.rename(REPORTS_FOLDER / report_to_rename, REPORTS_FOLDER / new_name)
            log("SUCCESS", "Successfully renamed file")
        log("SUCCESS", "Renamed all identified")

    else:
        log("SKIP", "No new reports identified")


if __name__ == "__main__":
    run()
