from jsonschema import Draft7Validator
from tabulate import tabulate
import git
import yaml
from pathlib import Path
import os
import sys
import pandas as pd
import numpy as np
import re
import toml

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.validation import indicator_validation
from Engines.modules.logging import Colors, log
from Engines.modules.files import absolute_paths

ROOT = Path(str(git.Repo(".", search_parent_directories=True).working_dir))
CONFIG = toml.load(open(ROOT / "Configurations/global.toml", encoding="utf-8"))
PATHS = absolute_paths()

JSONSCHEMAS_PATHS = PATHS["json_schemas"]
LOOKUPS_METADATA_JSONSCHEMA_PATH = (
    Path(JSONSCHEMAS_PATHS) / CONFIG["json_schemas"]["lookup_metadata"]
)
LOOKUPS_PATH = Path(PATHS["lookups"])

LOOKUPS_JSONSCHEMA = yaml.safe_load(
    open(LOOKUPS_METADATA_JSONSCHEMA_PATH, encoding="utf-8")
)
LOOKUPS_CONFIG = toml.load(
    open(ROOT / "Configurations/lookups.toml", encoding="utf-8")
)

METADATA_MANDATORY = LOOKUPS_CONFIG["validation"].get("enforce_metadata")
NAMING_CONVENTION = LOOKUPS_CONFIG["validation"].get("naming_convention")
VALID_BOOL_TRUE = LOOKUPS_CONFIG["validation"].get("true_values") or ["True"]
VALID_BOOL_FALSE = LOOKUPS_CONFIG["validation"].get("false_values") or ["False"]
log("DEBUG", str(VALID_BOOL_FALSE))
log("DEBUG", str(VALID_BOOL_TRUE))
VALID_BOOLEANS = []
VALID_BOOLEANS.extend(VALID_BOOL_TRUE)
VALID_BOOLEANS.extend(VALID_BOOL_FALSE)

TRAILING_SPACE_ALLOWED = True

DEBUG = os.environ.get("DEBUG") or False

csv_errors = list()
naming_convention_errors = list()
mandatory_metadata_errors = list()
missing_csv_columns = dict()
orphan_metadata_errors = list()
metadata_schema_errors = dict()
columns_error = list()
unknown_file_error = list()
sentinel_search_key_errors = list()


def run():

    log("TITLE", "Lookups Content Validation")
    log(
        "INFO",
        "Compares the lookup content against their metadata, and other sanity checks",
    )

    for lookup_folder in sorted(os.listdir(LOOKUPS_PATH)):
        for lookup in sorted(os.listdir(LOOKUPS_PATH / lookup_folder)):
            if (DEBUG and lookup.startswith("DEBUG")) or (
                not DEBUG and not lookup.startswith("DEBUG")
            ):
                if lookup.endswith(".csv"):
                    # CSV Format Check
                    try:
                        pd.read_csv(LOOKUPS_PATH / lookup_folder / lookup)
                    except:
                        csv_errors.append(lookup)

                    if NAMING_CONVENTION:
                        if not re.match(NAMING_CONVENTION, lookup):
                            naming_convention_errors.append(lookup)

                    # Metadata File Check
                    if lookup.replace(".csv", ".metadata.yaml") not in os.listdir(
                        (LOOKUPS_PATH / lookup_folder)
                    ):
                        lookup_metadata = None
                        mandatory_metadata_errors.append(lookup)

                    # Sentinel Search Key Check
                    if lookup_folder == "Sentinel":
                        log("ONGOING", lookup, "Sentinel specific checks...")
                        lookup_metadata_file = lookup.replace(".csv", ".metadata.yaml")
                        try:
                            lookup_metadata = yaml.safe_load(
                                open(
                                    LOOKUPS_PATH / lookup_folder / lookup_metadata_file,
                                    encoding="utf-8",
                                )
                            )

                        except:
                            log(
                                "INFO",
                                lookup,
                                "Could not find an associated lookup metadata file",
                            )
                            lookup_metadata = None

                        csv_content = pd.read_csv(
                            LOOKUPS_PATH / lookup_folder / lookup, dtype=object
                        )
                        csv_content = csv_content.replace(np.nan, None)

                        search_key = None
                        if lookup_metadata:
                            search_key = lookup_metadata.get("sentinel", {}).get(
                                "search_key"
                            )
                            if search_key:
                                log(
                                    "INFO",
                                    lookup,
                                    "Found search key in lookup metadata file",
                                    search_key,
                                )
                                for col in lookup_metadata.get("columns", []):
                                    if (col.get("name") == search_key) and (
                                        col.get("nullable") == True
                                    ):
                                        sentinel_search_key_errors.append(
                                            {
                                                "file": lookup_metadata_file,
                                                "error": f"Configured Search Key : {search_key} contains an entry"
                                                "in the lookup column description where nullable is set to True. "
                                                "This is not possible as all cells of a column defined as search key"
                                                "must contain value.",
                                            }
                                        )

                        if not search_key:
                            search_key = csv_content.columns[0]
                            log(
                                "INFO",
                                lookup,
                                "Search key not defined in a companion metadata file. Setting the search key to be the first column",
                                search_key,
                            )

                        if search_key not in csv_content.columns:
                            sentinel_search_key_errors.append(
                                {
                                    "file": lookup_metadata_file,
                                    "error": f"Configured Search Key : {search_key} does not exist in lookup",
                                }
                            )

                        else:
                            if None in csv_content[search_key].tolist():
                                sentinel_search_key_errors.append(
                                    {
                                        "file": lookup,
                                        "error": f"Configured Search Key : {search_key} Column contains empty values in lookup. "
                                        "All cells of a column defined as a Search Key must contain a value",
                                    }
                                )

                elif lookup.endswith(".metadata.yaml"):
                    expected_lookup_name = lookup.replace(".metadata.yaml", ".csv")

                    # Checking metadata schema
                    v = Draft7Validator(LOOKUPS_JSONSCHEMA)
                    lookup_metadata_content = yaml.safe_load(
                        open(LOOKUPS_PATH / lookup_folder / lookup, encoding="utf-8")
                    )
                    errors = sorted(
                        v.iter_errors(lookup_metadata_content), key=lambda e: e.path
                    )
                    if errors:
                        log("FATAL", "Errors found in lookup metadata for", lookup)
                        metadata_schema_errors[lookup] = {"errors": errors}

                    # Checking for metadata file that don't correspond with a lookup file
                    if expected_lookup_name not in [
                        l for l in os.listdir(LOOKUPS_PATH / lookup_folder)
                    ]:
                        orphan_metadata_errors.append(lookup)

                    # Checks that require a corresponding lookup file
                    else:
                        # Checks that also require a valid metadata file
                        if not errors:
                            log(
                                "DEBUG",
                                "No errors found in lookup metadata file for",
                                lookup,
                            )
                            # We convert columns to dtype=object as it prevents a bunch of datatype conversion
                            # which hurt when we try to validate a mixed-datatype column
                            csv_content = pd.read_csv(
                                LOOKUPS_PATH / lookup_folder / expected_lookup_name,
                                dtype=object,
                            )
                            csv_content = csv_content.replace(np.nan, None)

                            # Checking that columns described in metadata exist in csv
                            metadata_columns = [
                                col["name"]
                                for col in lookup_metadata_content["columns"]
                            ]
                            csv_columns = csv_content.columns.to_list()

                            # Check for columns in metadata not existing in lookup
                            for col in metadata_columns:
                                if col not in csv_columns:
                                    missing_csv_columns.setdefault(lookup, list())
                                    missing_csv_columns[lookup].append(col)

                            # Checking column types
                            for col_validation in lookup_metadata_content["columns"]:
                                column_name = col_validation["name"]
                                column_type = col_validation["type"]
                                nullable = col_validation["nullable"]
                                if nullable:
                                    log(
                                        "INFO",
                                        "Column detected as nullable, empty values are allowed",
                                        column_name,
                                    )
                                log("DEBUG", "Now processing", column_name)

                                if column_name not in csv_content.columns:
                                    log(
                                        "FATAL",
                                        f"The column {column_name} defined in the metadata file is not present in the csv columns",
                                        str(csv_content.columns),
                                    )
                                else:
                                    values = csv_content[column_name].tolist()
                                    for index, value in enumerate(values):
                                        error_template = {
                                            "lookup": f"{lookup_folder}/{expected_lookup_name}",
                                            "column": column_name,
                                            "row": f"Row {index+1}",
                                            "type": column_type,
                                            "value": value,
                                        }
                                        # Setting check for nullable to be explicitely False and not None
                                        if not nullable and value is None:
                                            error = {"error": "🫧  Null Value"}
                                            value = f"Check row "
                                            error.update(error_template)
                                            columns_error.append(error)

                                        elif value:

                                            if TRAILING_SPACE_ALLOWED:
                                                if type(value) is str:
                                                    value = value.strip()

                                            match column_type:
                                                case "any":
                                                    pass
                                                # Since int and float can be casted to string, first checking.
                                                case "string":
                                                    try:
                                                        int(value)
                                                        error = {
                                                            "error": "🔢 Expected string, got integer"
                                                        }
                                                        error.update(error_template)
                                                        columns_error.append(error)
                                                    except:
                                                        try:
                                                            float(value)
                                                            error = {
                                                                "error": "🛟 Expected string, got float"
                                                            }
                                                            error.update(error_template)
                                                            columns_error.append(error)
                                                        except:
                                                            try:
                                                                str(value)
                                                            except:
                                                                error = {
                                                                    "error": "💥 Expected string, could not identify type"
                                                                }
                                                                error.update(
                                                                    error_template
                                                                )
                                                                columns_error.append(
                                                                    error
                                                                )

                                                case "integer":
                                                    try:
                                                        int(value)
                                                    except:
                                                        error = {
                                                            "error": "🔢 Expected integer"
                                                        }
                                                        error.update(error_template)
                                                        columns_error.append(error)

                                                case "float":
                                                    try:
                                                        int(value)
                                                    except:
                                                        error = {
                                                            "error": "🛟 Expected float"
                                                        }
                                                        error.update(error_template)
                                                        columns_error.append(error)

                                                case "boolean":
                                                    log(
                                                        "DEBUG",
                                                        value,
                                                        str(VALID_BOOLEANS),
                                                    )
                                                    if value not in VALID_BOOLEANS:
                                                        error = {
                                                            "error": "[✅|❌] Unnaccepted boolean expression"
                                                        }
                                                        error.update(error_template)
                                                        columns_error.append(error)

                                                case "list":
                                                    valid_values = col_validation[
                                                        "list.values"
                                                    ]
                                                    if value not in valid_values:
                                                        error = {
                                                            "error": f"📃 Value not in expected list {', '.join(valid_values)}"
                                                        }
                                                        error.update(error_template)
                                                        columns_error.append(error)

                                                case "regex":

                                                    expression = col_validation[
                                                        "regex.expression"
                                                    ]
                                                    try:
                                                        re.compile(expression)
                                                    except:
                                                        log(
                                                            "FATAL",
                                                            f"Regular expression invalid",
                                                            expression,
                                                            "Ensure that the expression is valid before updating the metadata file",
                                                        )
                                                        VALIDATION_ERROR_RAISED = True
                                                    else:
                                                        if not re.match(
                                                            expression, value
                                                        ):
                                                            error = {
                                                                "error": "🔎 Unmatched expression"
                                                            }
                                                            error.update(error_template)
                                                            columns_error.append(error)

                                                case other:
                                                    TYPE_ICONS = {
                                                        "email": "📧",
                                                        "url": "🔗",
                                                        "domain": "🌐",
                                                        "ip": "🌐",
                                                        "uuid": "🆔",
                                                        "hash": "#️⃣",
                                                    }
                                                    col_icon = TYPE_ICONS.get(
                                                        column_type.split("::")[0]
                                                    )
                                                    if not indicator_validation(
                                                        column_type,
                                                        value,
                                                        verbose=False,
                                                    ):
                                                        error = {
                                                            "error": f"{col_icon} Incorrect type check"
                                                        }
                                                        error.update(error_template)
                                                        columns_error.append(error)

                else:
                    if not lookup.endswith(".gitkeep"):
                        unknown_file_error.append(lookup)

    VALIDATION_ERROR_RAISED = False

    if csv_errors:
        for error in csv_errors:
            log("WARNING", "This csv file is broken or corrupted", highlight=error)
            VALIDATION_ERROR_RAISED = True
    else:
        log("SUCCESS", "All lookups are valid CSV Files")

    if mandatory_metadata_errors:
        errors_list = ", ".join(mandatory_metadata_errors)
        if METADATA_MANDATORY:
            log(
                "FATAL",
                "This TIDeMEC instance is configured to enforce metadata files for every lookup.",
                errors_list,
                "Create a metadata file for the following lookup(s)",
            )
            VALIDATION_ERROR_RAISED = True
        else:
            log(
                "WARNING",
                "Couldn't find a metadata file(s) for the following lookups.",
                errors_list,
                "Consider creation to enrich validation and documentation",
            )

    else:
        log("SUCCESS", "All lookups file are accompanied with metadata files")

    if naming_convention_errors:
        VALIDATION_ERROR_RAISED = True
        for error in naming_convention_errors:
            log(
                "FATAL",
                "Lookup name is not matching convention set on this TIDeMEC instance",
                error,
                f"Ensure name matches pattern : {NAMING_CONVENTION}",
            )

    if orphan_metadata_errors:
        errors_list = ", ".join(orphan_metadata_errors)
        log(
            "FATAL",
            "The following metadata file do not match a lookup file name.",
            errors_list,
            "Ensure it alligns with the lookup file name.",
        )
        VALIDATION_ERROR_RAISED = True
    else:
        log("SUCCESS", "All metadata file are assigned to an existing lookup")

    if metadata_schema_errors:
        error_table = [["Metadata File", "Error"]]

        for i in metadata_schema_errors:
            for e in metadata_schema_errors[i]["errors"]:
                error_table.append(
                    [
                        f"{Colors.PURPLE}{Colors.BOLD}{i}{Colors.STOP}",
                        e.message.replace("\n", ""),
                    ]
                )

        log(
            "FATAL",
            "The following lookup metadata files do not match the expected schema.",
            highlight="Double check in VSCode that local validation passes",
        )
        error_table = tabulate(error_table, headers="firstrow", tablefmt="fancy_grid")
        print(error_table)
        VALIDATION_ERROR_RAISED = True

    else:
        log("SUCCESS", "All metadata file are valid against the lookup metadata schema")

    if columns_error:
        log(
            "FATAL",
            "The following errors were catch in lookup files",
            "This report was built based on the column type described in their respective metadata file",
        )
        error_table = pd.DataFrame(columns_error).to_markdown(
            tablefmt="fancy_grid", index=False
        )
        print(error_table)
        VALIDATION_ERROR_RAISED = True

    else:
        log("SUCCESS", "All lookups value match their column type")

    if sentinel_search_key_errors:
        log(
            "FATAL",
            "Found errors related to Sentinel Search Key configuration",
            advice="Review the errors and perform corrective actions",
        )
        for report in sentinel_search_key_errors:
            log("FAILURE", report["file"], report["error"])
            VALIDATION_ERROR_RAISED = True
    else:
        log("SUCCESS", "Found no Sentinel Search Key related errors")

    if unknown_file_error:
        for file in unknown_file_error:
            log(
                "WARNING",
                "This file does not appear to be a lookup or lookup metadata file ",
                file,
                "By safety, validation will fail. Ensure it ends with .csv for lookup file,"
                "or .metadata.yaml for lookup metadata files.",
            )
        VALIDATION_ERROR_RAISED = True
    else:
        log("SUCCESS", "All files correctly ends with .csv or .metadata.yaml")

    if missing_csv_columns:
        for lookup in missing_csv_columns:
            log(
                "WARNING",
                "The following lookup metadata file contains columns which don't exist on the target lookup",
                f"{lookup} | {', '.join(missing_csv_columns[lookup])}",
            )
    else:
        log(
            "SUCCESS",
            "All metadata file contain columns aligned with their respective csv",
        )

    if VALIDATION_ERROR_RAISED:
        log(
            "FATAL",
            "Found several errors",
            advice="Review the error logs above to identify the issue",
        )
        raise Exception("Validation Failed")
    else:
        log("SUCCESS", "All validation passed !")


if __name__ == "__main__":
    run()
