from jsonschema import Draft7Validator
from tabulate import tabulate
import os
import git
import sys
import json


sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.tide import DataTide
from Engines.modules.logs import log

JSONSCHEMAS_INDEX = DataTide.JsonSchemas.Index
MODELS_INDEX = DataTide.Models.Index

try:
    LEGACY_UUID_MAPPING = json.load(open(DataTide.Configurations.Global.Paths.Tide.tide_indexes / "legacy_uuid_mapping.json"))
except:
    log("SKIP", "Did not find a legacy id to uuid mapping")
    LEGACY_UUID_MAPPING = None
    pass

def patch_tide_1_id(model:dict)->dict:
    """
    Patch on the fly object in staging with new UUIDs to pass validation.
    Once merged to main they will be migrated definitely.
    TODO - Remove before public release, as only concerns existing repositories
    """
    if os.getenv("CI_COMMIT_REF_NAME") == "main":
        return model
    if LEGACY_UUID_MAPPING:
        if old_ids:=model.get("threat", {}).get("actors"):
            updated_ids = []
            for old in old_ids:
                if old in LEGACY_UUID_MAPPING:
                    new_uuid = LEGACY_UUID_MAPPING[old]["uuid"]
                    updated_ids.append(new_uuid)
                    log("INFO",
                        f"Updated old ids in model {model['name']}",
                        f"field: threat.vectors , {old} => {new_uuid}")
                else:
                    updated_ids.append(old)
            model["threat"]["actors"] = updated_ids

        if old_ids:=model.get("detection", {}).get("vectors"):
            updated_ids = []
            for old in old_ids:
                if old in LEGACY_UUID_MAPPING:
                    new_uuid = LEGACY_UUID_MAPPING[old]["uuid"]
                    updated_ids.append(new_uuid)
                    log("INFO",
                        f"Updated old ids in model {model['name']}",
                        f"field: detection.vectors , {old} => {new_uuid}")
                else:
                    updated_ids.append(old)
            model["threat"]["actors"] = updated_ids

        if old:=model.get("detection_model"):
            if old in LEGACY_UUID_MAPPING:
                new_uuid = LEGACY_UUID_MAPPING[old]["uuid"]
                log("INFO",
                    f"Updated old ids in model {model['name']}",
                    f"field: detection_model , {old} => {new_uuid}")

    return model

def run():

    log("TITLE", "JSON Schema Validation")
    log("INFO", "Validates all CoreTIDE objects against their respective json schemas")

    errorslist = {}
    stats = dict()
    overall = 0

    for schema in JSONSCHEMAS_INDEX:
        count = 0

        if schema in MODELS_INDEX:
            schema_data = JSONSCHEMAS_INDEX[schema]
            v = Draft7Validator(schema_data)

            for model in MODELS_INDEX[schema]:
                count += 1

                body = MODELS_INDEX[schema][model]
                body = patch_tide_1_id(body)
                metadata = body.get("metadata") or body["meta"]
                metadata["created"] = str(metadata["created"])
                metadata["modified"] = str(metadata["modified"])

                # YAML supports int as keys, JSON doesn't. jsonschema team
                # decided not to support serialization, which creates a lot
                # of difficulties validating public references.
                # Solution is to remove public refs, and validate it separately.
                # Other parts of the reference will work as they don't use ints as key.
                public_refs = None

                if type(body.get("references")) is dict:
                    if body.get("references", {}).get("public"):
                        public_refs = body["references"].pop("public")
                        if body["references"] == {}:
                            del body["references"]

                
                errors = list()
                errors = sorted(v.iter_errors(body), key=lambda e: e.path)

                if public_refs:
                    for ref in public_refs:
                        if type(ref) is not int:
                            errors.append(
                                f"Reference '{ref}' in public references should be an integer"
                            )

                if len(errors) != 0:
                    name = f"{body['name']} ({model})"
                    errorslist[name] = errors

            stats[schema.upper()] = count
            overall += count

    for model_name in errorslist:
        for error in errorslist[model_name]:
            if type(error) is not str:
                error = error.message.replace("\n", "")
                if len(error) > 160:
                    error = error[:160] + f" [...Truncated Error Message]"
            log("FATAL", f"Failed validation in Object - {model_name}", error)

    if len(errorslist) != 0:
        log("FATAL", "Failed Schema Validation",
            "CoreTIDE objects currently do not match up to the metaschemas",
            "Review the files before running the validation again" )
        os.environ["VALIDATION_ERROR_RAISED"] = "True"

    else:
        statstable = [["Category", "Count"]]

        for y in stats:
            statstable.append([y, stats[y]])
        statstable = tabulate(statstable, headers="firstrow")

        log("SUCCESS", f"Successfully verified {overall} coretide objects")
        print(statstable)


if __name__ == "__main__":
    run()
