import sys
import os
import git
import toml
from pathlib import Path

import yaml

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.dont_write_bytecode = True  # Prevents pycache

from Engines.modules.logs import log
from Engines.modules.files import safe_file_name

ROOT = Path(str(git.Repo(".", search_parent_directories=True).working_dir))
CONFIG = toml.load(open(ROOT / "Configurations/global.toml", encoding="utf-8"))
MODEL_TYPES = CONFIG["models"]

MODEL_PATHS = {model: ROOT / CONFIG["paths"]["tide"][model] for model in MODEL_TYPES}


def assign_id(file_path, new_id):

    # Infer basic id from new_id string
    old_id = "".join(filter(str.isalpha, new_id)) + "0000"
    old_id_x = old_id.replace("0000", "XXXX")
    with open(file_path, "r", encoding="utf-8") as file:
        buffer = []
        for line in file:
            line = line.replace(old_id, new_id)
            line = line.replace(old_id_x, new_id)
            buffer.append(line)

    with open(file_path, "w", encoding="utf-8") as file:
        for line in buffer:
            file.write(line)


def run():

    log("TITLE", "File Name and ID Aligner")
    log(
        "INFO",
        "Aligns the file name with the YAML Content and assigns"
        " ID if missing (non-MDR objects only)",
    )

    MODEL_TYPES.remove("mdr")
    for model in MODEL_TYPES:
        highest_id = 0
        files_to_assign = []
        for file in sorted(os.listdir(MODEL_PATHS[model])):
            data = yaml.safe_load(open(MODEL_PATHS[model] / file, encoding="utf-8"))
            model_name = data["name"]
            model_id = data.get("id")

            # Check files that need new ID assigned
            # Supports not having ID, or having ABC0000 , ABCXXXX.
            # ABC0000 is preferred as will pass validation
            if (
                model_id.endswith("0000") or model_id.endswith("XXXX") or not model_id
            ) and model != "mdr":
                log("INFO", "Object Identified to receive new ID", model_name)
                files_to_assign.append(file)

            else:
                # Check files that only need file name realigned
                if model == "mdr":
                    standard_name = f"{safe_file_name(model_name)}.yaml"
                else:
                    id_value = int("".join(filter(str.isdigit, model_id)))
                    if id_value > highest_id:
                        highest_id = id_value

                    standard_name = f"{safe_file_name(model_id)} - {model_name}.yaml"

                if file != standard_name:
                    log("INFO", "Re-aligning file name with model_data", file)
                    # Renaming goes through a temp file to still rename in case-insensitive OSs
                    # when the only difference is capitalization
                    os.rename(
                        MODEL_PATHS[model] / file,
                        MODEL_PATHS[model] / (standard_name + ".tmp"),
                    )
                    os.rename(
                        MODEL_PATHS[model] / (standard_name + ".tmp"),
                        MODEL_PATHS[model] / standard_name,
                    )
                    log("SUCCESS", f"Alligned file name with model data", standard_name)

        # Assigning new ID to files and new name
        if files_to_assign:
            for file in files_to_assign:
                log("INFO", "Re-aligning file name with model_data", file)
                file_name = MODEL_PATHS[model] / file
                data = yaml.safe_load(open(file_name, encoding="utf-8"))
                highest_id += 1
                model_name = data["name"]
                model_id = f"{model.upper()}{str(highest_id).zfill(4)}"
                standard_name = f"{safe_file_name(model_id)} - {model_name}.yaml"
                log("INFO", "Reassigning ID to", model_id)

                assign_id(file_name, model_id)
                os.rename(file_name, MODEL_PATHS[model] / standard_name)
                log(
                    "SUCCESS",
                    "Successfully assigned new id and updated file name",
                    standard_name,
                )

        else:
            log("SKIP", "No files to assign ID or fix file names in model type", model)


if __name__ == "__main__":
    run()
