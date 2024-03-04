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
from Engines.templates.wiki_navigation import NAV_INDEX_TEMPLATE
from Engines.modules.logs import log
from Engines.modules.tide import DataTide

GLFM = DataTide.Configurations.Documentation.glfm_doc_target
MODELS_INDEX = DataTide.Models.Index
METASCHEMAS_INDEX = DataTide.TideSchemas.Index
ICONS = DataTide.Configurations.Documentation.icons

DOCUMENTATION_TYPE = "GLFM"
PATHS_CONFIG = DataTide.Configurations.Global.Paths.Index

WIKI_PATH = PATHS_CONFIG["wiki_docs_folder"]
OUT_PATH = Path(WIKI_PATH) / "home.md"

CHARS_CLIP = 150
NAV_INDEX_FIELDS = {
    "tam": [
        "id",
        "name",
        "criticality",
        "tlp",
        "description",
        "implementations",
        "aliases",
        "tier",
        "level",
        "objectives",
        "att&ck",
        "domains",
        "platforms",
    ],
    "tvm": [
        "id",
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
        "id",
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
        "id",
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
        "name",
        "description",
        "statuses",
        "schema version",
        "att&ck",
        "detection_model",
        "system",
        "uuid",
    ],
}

MODELS = NAV_INDEX_FIELDS.keys()


def build_searches(model_type):

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
                version = get_type(entry, get_version=True)

                if value == "schema version":
                    version_display = str()
                    if version == "mdrv2":
                        version_display = "MDRv2"
                    elif version == "mdrv3":
                        version_display = "✨MDRv3✨"
                    row[schema_version] = version_display

                elif value == "statuses":

                    if version == "mdrv3":
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
                    else:
                        row[mdr_statuses] = model_value_doc(entry, "status")

                elif value == "name":
                    if version == "mdrv2":
                        mdr_name = str(model_value_doc(entry, "title"))
                        mdr_name = mdr_name.split("$")[0].strip()
                    else:
                        mdr_name = model_value_doc(entry, "name")
                    row[value] = mdr_name

                # List
                elif value == "att&ck":
                    if version == "mdrv3":
                        model_value = (
                            techniques_resolver(str(model_value_doc(entry, "uuid")))
                            or ""
                        )
                        if model_value:
                            model_value = ", ".join(model_value)
                        row[mdr_attack_technique] = model_value

                # Custom ways of returning data beside field listing
                elif value == "system":
                    if version == "mdrv2":
                        model_value = MODELS_INDEX[model_type][entry]["rule"][
                            "alert"
                        ].keys()
                    else:
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
    if "id" in df.columns:
        df = df.sort_values(by=["id"])

    rename_mapping = {
        c: f"{get_field_title(c, METASCHEMAS_INDEX[model_type]['properties'])}"
        for c in [x for x in df.columns if x not in custom_cols]
    }
    df = df.rename(columns=rename_mapping)

    nav_index = str()
    if DOCUMENTATION_TYPE == "GLFM":
        # Seems to force json tables to fit the screen, and will squeeze down
        # up to the number of characters in the wrap function.
        nav_index = make_json_table(df)

    elif DOCUMENTATION_TYPE == "MARKDOWN":
        nav_index = df.to_markdown()

    return nav_index


def construct_navigation_index(models):

    html_foldable = """
<details><summary><h3>{}</h3></summary>

{}

</details>
"""
    searches = str()
    obj = dict()

    for model_type in models:

        icon = ICONS[model_type]
        model_title = DataTide.Configurations.Documentation.object_names[model_type]

        print(f"{icon} Generating navigation index for {model_title}...")

        count = len(MODELS_INDEX[model_type])

        html_summary = f"{icon} {count} {model_title}"
        html_details = build_searches(model_type)
        foldable = html_foldable.format(html_summary, html_details)
        searches += f"\n\n{foldable}\n\n"

    nav_index = NAV_INDEX_TEMPLATE.format(**locals())

    return nav_index


def run():

    log("TITLE", "Wiki Navigation Index")
    log(
        "INFO",
        "Assembles tables exposing TIDeMEC data to make the dataset easier to navigate",
    )

    if not os.path.exists(WIKI_PATH):
        log("ONGOING", "Create wiki folder")
        WIKI_PATH.mkdir(parents=True)

    nav_index = construct_navigation_index(MODELS)
    with open(OUT_PATH, "w+", encoding="utf-8") as out:
        out.write(nav_index)

    doc_format_log = str()
    if DOCUMENTATION_TYPE == "MARKDOWN":
        doc_format_log = "✒️ standard markdown"
    elif DOCUMENTATION_TYPE == "GLFM":
        doc_format_log = "🦊 Gitlab Flavored Markdown"

    time_to_execute = "%.2f" % (time.time() - start_time)

    print("\n⏱️ Generated navigation index in {} seconds".format(time_to_execute))
    print("✅ Successfully built TIDeMEC documentation in {}".format(doc_format_log))


if __name__ == "__main__":
    run()
