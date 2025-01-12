import pandas as pd
import os
import git
import time
import sys
from pathlib import Path

start_time = time.time()


sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.framework import techniques_resolver, relations_list, get_type
from Engines.modules.documentation import (
    model_value_doc,
    get_icon,
    get_field_title,
    make_json_table,
)
from Engines.modules.logs import log
from Engines.modules.tide import DataTide
from Engines.modules.debug import DebugEnvironment

DOCUMENTATION_TARGET = DataTide.Configurations.Documentation.documentation_target
COVER_PAGES_ENABLED = DataTide.Configurations.Documentation.gitlab.get("model_cover_pages", False)

# For testing purposes, enabling this script to execute
if DebugEnvironment.ENABLED:
    DOCUMENTATION_TARGET = "gitlab"
    COVER_PAGES_ENABLED = True

MODELS_INDEX = DataTide.Models.Index
METASCHEMAS_INDEX = DataTide.TideSchemas.Index
ICONS = DataTide.Configurations.Documentation.icons

PATHS_CONFIG = DataTide.Configurations.Global.Paths.Index

MODELS_DOCS_PATH = DataTide.Configurations.Documentation.models_docs_folder
MODELS_SCOPE = DataTide.Configurations.Documentation.scope
MODELS_NAME = DataTide.Configurations.Documentation.object_names

CHARS_CLIP = 150
NAV_INDEX_FIELDS = {
    "tvm": [
        "uuid",
        "name",
        "criticality",
        "tlp",
        "description",
        "actors",
        "implementations",
        "criticality",
        "targets",
        "platforms",
        "att&ck",
        "cve",
        "impact",
        "leverage",
    ],
    "cdm": [
        "uuid",
        "name",
        "criticality",
        "tlp",
        "att&ck",
        "guidelines",
        "vectors",
        "implementations",
        "criticality",
        "methods",
        "datasources",
        "collection",
        "artifacts",
    ],
    "bdr": [
        "uuid",
        "name",
        "criticality",
        "tlp",
        "description",
        "implementations",
        "criticality",
        "violation",
        "domains",
    ],
    "mdr": [
        "uuid",
        "name",
        "description",
        "statuses",
        "att&ck",
        "detection_model",
        "system"
    ],
}

MODELS = NAV_INDEX_FIELDS.keys()


def build_search(model_type):

    index = list()
    index_data = MODELS_INDEX[model_type]
    system_column = "🔧 Detection Systems"
    mdr_statuses = "♻️ Status"
    implementation_column = "🪛 Implementations"
    schema_version = "🏷️ Schema Version"
    mdr_attack_technique = "🗡️ MDR Technique"

    custom_cols = [
        system_column,
        implementation_column,
        schema_version,
        mdr_attack_technique,
        mdr_statuses,
    ]

    for entry in index_data:
        row = dict()
        for value in NAV_INDEX_FIELDS[model_type]:

            if value == "implementations":
                relations = relations_list(entry, mode="count", direction="downstream")
                implementations = []

                if not relations:
                    implementations = ["⛔ None"]

                for k, v in relations.items():
                    title = f"{get_icon(k)} {k.upper()} : {v}"

                    implementations.append(title)

                row[implementation_column] = " // ".join(implementations)

            elif model_type == "cdm" and value == "att&ck":
                techniques = ", ".join(techniques_resolver(entry))
                row[value] = techniques

            elif model_type == "mdr":

                if value == "statuses":

                    # Build a key value dict of systems and their status
                    statuses = dict()
                    configurations = model_value_doc(entry, "configurations") or {}
                    for system in configurations:
                        sys_status = configurations[system]["status"]  # type: ignore
                        statuses[system] = sys_status

                    # Pretty print statuses
                    statuses = ", ".join(
                        [f"{k.capitalize()}:{v}" for k, v in statuses.items()]
                    )
                    row[mdr_statuses] = statuses

                elif value == "name":
                    mdr_name = model_value_doc(entry, "name")
                    row[value] = mdr_name

                # List
                elif value == "att&ck":
                    model_value = (
                        techniques_resolver(str(model_value_doc(entry, "uuid")))
                        or ""
                    )
                    if model_value:
                        model_value = ", ".join(model_value)
                    row[mdr_attack_technique] = model_value

                # Custom ways of returning data beside field listing
                elif value == "system":
                    model_value = MODELS_INDEX[model_type][entry][
                        "configurations"
                    ].keys()

                    model_value = [s.capitalize() for s in model_value]
                    model_value = ", ".join(model_value)
                    row[system_column] = model_value

                else:
                    model_value = model_value_doc(
                        entry, value, with_icon=True, max_chars=CHARS_CLIP
                    )
                    row[value] = model_value

            else:
                model_value = model_value_doc(
                    entry, value, with_icon=True, max_chars=CHARS_CLIP
                )

                if type(model_value) == list:
                    if model_value != [None]:
                        model_value = ", ".join(model_value)

                elif type(model_value) == dict:
                    # Mitigation for a possible edge case where list in a dict
                    # can be empty without invalidating validation.
                    # This approach removes dicts containing empty lists but
                    # keeps other dicts that contain values.
                    model_value_iter = model_value.copy()
                    for v in model_value_iter:
                        if model_value_iter[v] == None or model_value_iter[v] == [None]:
                            model_value.pop(v)
                    if model_value != {}:
                        flat_values = [
                            k.capitalize() + " : " + ", ".join(model_value[k])
                            for k in model_value
                        ]
                        model_value = ", ".join(flat_values)
                    else:
                        model_value = ""

                row[value] = model_value

        index.append(row)

    df = pd.DataFrame(index)

    rename_mapping = {
        c: f"{get_field_title(c, METASCHEMAS_INDEX[model_type]['properties'])}"
        for c in [x for x in df.columns if x not in custom_cols]
    }
    df = df.rename(columns=rename_mapping)

    nav_index = make_json_table(df)

    return nav_index


def construct_navigation_index(model):

    icon = ICONS[model]
    model_title = DataTide.Configurations.Documentation.object_names[model]

    log("ONGOING", "Generating navigation index for", model_title)

    count = len(MODELS_INDEX[model])

    summary = f"{icon} {count} {model_title}"
    details = build_search(model)

    nav_index = summary + "\n\n" + details

    return nav_index


def run():


    log("TITLE", "Wiki Navigation Index")
    log(
        "INFO",
        "Assembles tables exposing CoreTIDE data to make the dataset easier to navigate",
    )

    if DOCUMENTATION_TARGET != "gitlab":
        log("SKIP",
            "This is a Gitlab Wiki only feature",
            f"documentation_target is currently set to : {DOCUMENTATION_TARGET}",
            "If you are running OpenTIDE in Gitlab, we advise to change this configuration \
                to 'gitlab' to enjoy all documentation features")
        return 

    if not COVER_PAGES_ENABLED:
        log("SKIP",
            "Disabled in configuration",
            "Not generating cover pages as set to false or missing key",
            "You can enable this feature by setting gitlab.model_cover_pages to True in documentation.toml")
        return
    
    if not os.path.exists(MODELS_DOCS_PATH):
        log("ONGOING", "Create wiki and documentation folder")
        MODELS_DOCS_PATH.mkdir(parents=True)

    for model in MODELS:
        log("ONGOING", "Generating navigation index for model type", model)
        
        nav_index = construct_navigation_index(model)
        navigation_index_path = MODELS_DOCS_PATH / (MODELS_NAME[model].replace(" ", "-") + ".md")
        print(navigation_index_path)
        with open(navigation_index_path, "w+", encoding="utf-8") as out:
            out.write(nav_index)

        time_to_execute = "%.2f" % (time.time() - start_time)

    print("\n⏱️ Generated navigation index in {} seconds".format(time_to_execute))


if __name__ == "__main__":
    run()
