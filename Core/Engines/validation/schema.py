from jsonschema import Draft7Validator
from tabulate import tabulate
import os
import git
import sys


sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Core.Engines.modules.tide import DataTide
from Core.Engines.modules.logging import log

JSONSCHEMAS_INDEX = DataTide.JsonSchemas.Index
MODELS_INDEX = DataTide.Models.Index

def run():

    log("TITLE", "JSON Schema Validation")
    log("INFO", "Validates all TIDeMEC objects against their respective json schemas")

    errorslist = {}
    stats = dict()
    overall = 0

    for schema in JSONSCHEMAS_INDEX:
        count = 0

        if schema in MODELS_INDEX:
            schema_data = JSONSCHEMAS_INDEX[schema]

            for model in MODELS_INDEX[schema]:
                count += 1

                body = MODELS_INDEX[schema][model]
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

                v = Draft7Validator(schema_data)
                errors = list()
                errors = sorted(v.iter_errors(body), key=lambda e: e.path)

                if public_refs:
                    for ref in public_refs:
                        if type(ref) is not int:
                            errors.append(
                                f"Reference '{ref}' in public references should be an integer"
                            )

                if len(errors) != 0:
                    buf = dict()

                    buf["category"] = schema.upper()
                    buf["errors"] = errors

                    errorslist[model] = buf

            stats[schema.upper()] = count
            overall += count

    errortable = [["Object", "Category", "Error"]]

    for i in errorslist:
        for error in errorslist[i]["errors"]:
            if type(error) is not str:
                error = error.message.replace("\n", "")
            errortable.append([i, errorslist[i]["category"], error])

    errortable = tabulate(errortable, headers="firstrow", tablefmt="fancy_grid")
    if len(errorslist) != 0:
        print(
            "⚠️ TIDeMEC objects currently do not match up to the metaschemas. Review the files before running the validation again: \n\n"
            + errortable
        )
        os.environ["VALIDATION_ERROR_RAISED"] = "True"

    else:
        statstable = [["Category", "Count"]]

        for y in stats:
            statstable.append([y, stats[y]])
        statstable = tabulate(statstable, headers="firstrow")

        print(f"✅Successfully verified {overall} tidemec objects : \n\n{statstable}")


if __name__ == "__main__":
    run()
