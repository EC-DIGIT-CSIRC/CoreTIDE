import os
import git
from pathlib import Path
import time
import urllib.parse
import pandas as pd
import sys


sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.framework import get_type
from Engines.modules.documentation import (
    get_icon,
    backlink_resolver,
    name_subschema_doc,
)
from Engines.modules.files import safe_file_name
from Engines.modules.deployment import system_scope
from Engines.modules.tide import DataTide
from Engines.modules.logs import log

METASCHEMAS_INDEX = DataTide.TideSchemas.Index
SUBSCHEMAS_INDEX = DataTide.TideSchemas.subschemas
LOOKUPS_INDEX = DataTide.Lookups.lookups
LOOKUPS_METADATA_INDEX = DataTide.Lookups.metadata
MODELS_INDEX = DataTide.Models.Index
VOCAB_INDEX = DataTide.Vocabularies.Index


start_time = time.time()

DOCUMENTATION_CONFIG = DataTide.Configurations.Documentation
ICONS = DOCUMENTATION_CONFIG.icons
NAV_INDEX_NAMES = DOCUMENTATION_CONFIG.indexes
MODELS_SCOPE = DOCUMENTATION_CONFIG.scope
MODELS_SCOPE.append("mdr")
PATHS_CONFIG = DataTide.Configurations.Global.paths
DOCUMENTATION_TYPE = os.getenv("DOCUMENTATION_TYPE") or "GLFM"
METASCHEMAS = Path(PATHS_CONFIG["metaschemas"])
# Adding those path changes as the sidebar is a layer up from the documentation subfolders, which these
# variables are also used to output the doc to.
WIKI = Path(os.path.basename(Path(PATHS_CONFIG["models_docs_folder"])))
SPECS = Path(os.path.basename(Path(PATHS_CONFIG["schemas_docs_folder"])))
LOOKUP_DOCS_FOLDER = Path(PATHS_CONFIG["lookup_docs"])
GLFM = False  # DataTide.Configurations.Documentation.glfm_doc_target

DOC_TITLES = DOCUMENTATION_CONFIG.titles
VOCABS_DOCS = Path(os.path.basename(Path(PATHS_CONFIG["vocabularies_docs"])))
SKIP_VOCABS = DOCUMENTATION_CONFIG.skip_vocabularies
WIKI_PATH = PATHS_CONFIG["wiki_docs_folder"]
OUT_PATH = WIKI_PATH / "_sidebar.md"

HTML_FOLDABLE = """<details><summary>{cat_icon}{category}</summary>

{content}

</details>
"""

SIDEBAR_TEMPLATE = """{home}

{data_model}

<br /> 

{lookups}

<br /> 

{reports}

<br /> 

{vocabularies}

<br /> 

{models_sidebar}

"""


def sidebar_link(model_id):

    model_type = get_type(model_id)
    """
    try:
        #Testing if model_id is a uuid, which would mean an MDR
        uuid.UUID(str(model_id))
        model_type = "mdr"
    
    except:
        #For all other models
        model_type = model_id[:3].lower()
        if model_type not in MODELS:
            
            title = MODELS_INDEX["mdr"][model_id].get("name") or MODELS_INDEX["mdr"][model_id]["name"]
            print(f"⚠️ Incorrect uuid for {title} - forcing to MDR category ")

            model_type = "mdr" #Case for invalid uuid that will fall in exception
    """
    model = MODELS_INDEX[model_type][model_id]
    icon = ICONS[model_type]

    # Main change from normal backlink - to be considered in future we want to make
    # a common library of functions
    doc_path = str(WIKI) + "/" + DOCUMENTATION_CONFIG.object_names[model_type]

    if model_type == "mdr":
        model_name = model.get("name") or model.get("title").split("$")[0].strip()
        model_name.replace("_", " ")
        # status = model.get("status")
        # backlink_name = "[{}] {}".format(status,model_name)
        backlink_name = model_name
        file_link = f"/{doc_path}/{icon} {model_name}"

    else:
        model_name = model["name"].strip()
        model_name.replace("_", " ")
        backlink_name = "[{}] {}".format(model_id, model_name)
        file_link = f"/{doc_path}/{icon} {backlink_name}"

    if GLFM:
        file_link = file_link.replace(" ", "-").replace("_", "-")
        file_link = urllib.parse.quote(file_link)
    else:
        file_link = "." + file_link.replace(" ", "%20") + ".md"

    backlink = "[{}]({})".format(backlink_name, file_link)

    return backlink


def run():

    log("TITLE", "Wiki Sidebar")
    log("INFO", "Generates a sidebar in markdown to make wiki navigation easier")

    # Remove everything in  Doc Folder
    if not os.path.exists(WIKI_PATH):
        log("ONGOING", "Did not find a wiki folder", "creating a new folder")
        os.mkdir(WIKI_PATH)

    # 🪬 TIDeMEC Home
    # > 🏗️ Data Model
    # > 🔎 Lookups
    # > 📒 Vocabularies
    # > 👹 Threat Actors
    # > ☣️ Threat Vectors
    # > 🛡️ Detection Models
    # > 🏛️ Business Requests
    # > 🚨 Detection Rules
    # Not in sidebar but in repo
    # ./Documentation_Scripts/
    # ./uploads
    # .index.json
    # .staging_index.json

    cat_icon = ICONS["home"]
    category = "TIDeMEC Home"

    print(f"{cat_icon} Generating sidebar entry for {category}")
    home = f"[{cat_icon} TIDeMEC Home](./home)"

    # Data Model

    data_model_content = []
    cat_icon = ICONS.get("metaschema")
    category = "Data Model"

    print(f"{cat_icon} Generating sidebar entry for {category}")

    for model in METASCHEMAS_INDEX:
        if model in DOC_TITLES.keys():
            icon = ICONS.get(model) or ICONS.get("metaschemas")
            file_name = str(icon) + " " + DOC_TITLES[model]
            file_path = SPECS / file_name
            if GLFM:
                file_path = "/" + file_path.as_posix().replace(" ", "-")
            else:
                file_path = "./" + file_path.as_posix().replace(" ", "%20") + ".md"

            data_model_content.append(f"[{file_name}]({file_path})")

    # Sub Schema Sidebar
    for recomp in SUBSCHEMAS_INDEX:
        for sub in SUBSCHEMAS_INDEX[recomp]:

            subschema_name = name_subschema_doc(recomp, sub)

            file_path = SPECS / subschema_name
            if GLFM:
                file_path = "/" + file_path.as_posix().replace(" ", "-")
            else:
                file_path = "./" + file_path.as_posix().replace(" ", "%20") + ".md"

            data_model_content.append(f"[{subschema_name}]({file_path})")

    content = "- " + "\n- ".join(data_model_content)

    data_model = HTML_FOLDABLE.format(**locals())

    # Lookups
    SYSTEMS = system_scope()

    lookup_content = str()

    for system in LOOKUPS_INDEX:
        system_content = list()
        if LOOKUPS_INDEX[system]:
            if system in SYSTEMS:
                for lookup in LOOKUPS_INDEX[system]:
                    if lookup in LOOKUPS_METADATA_INDEX:
                        metadata = LOOKUPS_METADATA_INDEX[lookup]
                        file_name = metadata["name"]
                    else:
                        file_name = lookup

                    file_path = (
                        LOOKUP_DOCS_FOLDER
                        / system
                        / (safe_file_name(file_name) + ".md")
                    )
                    if GLFM:
                        file_path = "/" + file_path.as_posix().replace(" ", "-")
                    else:
                        file_path = (
                            "./" + file_path.as_posix().replace(" ", "%20") + ".md"
                        )

                    system_content.append(f"[{lookup}]({file_path})")

                content = {system.capitalize(): system_content}
                lookup_content += pd.DataFrame(content).to_markdown(index=False)

    cat_icon = get_icon("lookups")
    category = "Lookups"
    content = lookup_content

    lookups = HTML_FOLDABLE.format(**locals())

    # Intelligence Reports

    REPORTS = VOCAB_INDEX["reports"]["entries"]
    if REPORTS:
        content = [backlink_resolver(report).replace("../", "./") for report in REPORTS]
        content = "- " + "\n- ".join(content)
    else:
        content = "❌ No Intelligence Reports Uploaded"

    cat_icon = get_icon("reports")
    category = "Intelligence Reports"

    reports = HTML_FOLDABLE.format(**locals())

    # Vocabularies

    cat_icon = ICONS.get("vocab")
    vocab_content = []
    category = "Vocabularies"

    print(f"{cat_icon} Generating sidebar entry for {category}")

    for voc in VOCAB_INDEX:
        if voc not in SKIP_VOCABS:
            icon = get_icon(voc) or ICONS["vocab"]
            file_name = icon + " " + VOCAB_INDEX[voc]["metadata"]["name"]
            file_path = VOCABS_DOCS / file_name
            if GLFM:
                file_path = "/" + file_path.as_posix().replace(" ", "-")
            else:
                file_path = "./" + file_path.as_posix().replace(" ", "%20") + ".md"

            # Take note of the forward slash, else gitlab wiki won't process path correctly
            vocab_content.append(f"[{file_name}]({file_path})")

    content = "- " + "\n- ".join(vocab_content)

    vocabularies = HTML_FOLDABLE.format(**locals())

    models_sidebar = ""

    for model_type in MODELS_SCOPE:
        cat_icon = ICONS[model_type]
        model_content = []
        category = DOCUMENTATION_CONFIG.object_names[model_type]

        print(f"{cat_icon} Generating sidebar entry for {category}")

        for m in sorted(MODELS_INDEX[model_type]):
            file_name = sidebar_link(m)
            model_content.append(file_name)

        if model_type == "mdr":
            model_content.sort()
        content = "- " + "\n- ".join(model_content)
        models_sidebar += HTML_FOLDABLE.format(**locals())
        models_sidebar += "<br /> "

    sidebar = SIDEBAR_TEMPLATE.format(**locals())

    if not os.path.exists(WIKI_PATH):
        print("🗑️ Removing Previous Sidebar File...")
        WIKI_PATH.mkdir(parents=True)

    with open(OUT_PATH, "w+", encoding="utf-8") as sidebar_file:
        sidebar_file.write(sidebar)

    time_to_execute = "%.2f" % (time.time() - start_time)

    print("\n⏱️ Generated navigation sidebar in {} seconds".format(time_to_execute))
    print("✅ Successfully built TIDeMEC Sidebar for Gitlab Wiki")


if __name__ == "__main__":
    run()
