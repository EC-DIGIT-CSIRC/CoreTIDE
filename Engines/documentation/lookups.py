import pandas as pd
import os
import git
from pathlib import Path
import sys
import shutil
from io import StringIO

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.documentation import make_json_table
from Engines.modules.documentation_components import tlp_doc
from Engines.modules.logs import log
from Engines.modules.files import safe_file_name
from Engines.modules.deployment import system_scope
from Engines.modules.tide import DataTide
from Engines.templates.lookups import LOOKUP_TEMPLATE

LOOKUPS_INDEX = DataTide.Lookups.lookups
LOOKUPS_METADATA_INDEX = DataTide.Lookups.metadata


LOOKUP_DOCS_FOLDER = Path(DataTide.Configurations.Global.paths["lookup_docs"])

SYSTEMS = system_scope()

HTML_FOLDABLE = """
<details><summary>{}</summary>

{}

</details>
"""
MARKDOWN = False
GLFM = True
if MARKDOWN:
    log("INFO", "✒️ Detected Markdown as target documentation")
elif GLFM:
    log(
        "INFO",
        "🦊 Detected Gitlab Flavored Markdown as target documentation",
        "Will generate searchable and sortable JSON Table instead or standard markdown",
    )


def lookup_documentation(lookup, lookup_metadata):
    banner = title = owners = tlp = description = column_description = ""

    df_lookup = pd.read_csv(StringIO(lookup))

    if GLFM:
        lookup_table = make_json_table(df_lookup)
    else:
        lookup_table = df_lookup.to_markdown()

    if not lookup_metadata:
        log("SKIP", "No lookup metadata found, will not document metadata contents")
        banner = "⚠️ Consider adding a lookup metadata file to enrich documentation"
        if GLFM:
            banner = f"[-{banner}-]"
    else:
        title = "# " + lookup_metadata["name"]
        owners = ", ".join(lookup_metadata["owners"])
        owners = f"🐲 **Owners** : {owners}"
        tlp = tlp_doc(lookup_metadata["tlp"])
        description = "> " + lookup_metadata["description"]

        if "columns" in lookup_metadata:
            df_columns = pd.DataFrame(lookup_metadata["columns"])

            column_description = df_columns.fillna("").to_markdown(index=False)
            column_description = HTML_FOLDABLE.format(
                "👉 Show column documentation", column_description
            )

        if GLFM:
            title = ""

    lookup_doc = LOOKUP_TEMPLATE.format(
        title=title,
        owners=owners,
        tlp=tlp,
        description=description,
        lookup_table=lookup_table,
        banner=banner,
        column_description=column_description,
    )

    return lookup_doc


def run():

    log("TITLE", "Lookups Documentation")
    log("INFO", "Create the documentation for lookups")

    # Remove everything in  Doc Folder
    if os.path.exists(LOOKUP_DOCS_FOLDER):
        shutil.rmtree(LOOKUP_DOCS_FOLDER)
    LOOKUP_DOCS_FOLDER.mkdir(parents=True)

    log("INFO", "Systems enabled on this instance", ", ".join(SYSTEMS))
    for system_lookups in LOOKUPS_INDEX:

        if system_lookups in SYSTEMS:
            log("INFO", "Now processing for lookups to document for", system_lookups)
            for lookup in LOOKUPS_INDEX[system_lookups]:
                log("ONGOING", f"Generating lookup documentation for", lookup)
                lookup_file = LOOKUPS_INDEX[system_lookups][lookup]
                lookup_metadata = LOOKUPS_METADATA_INDEX.get(lookup) or None
                doc = lookup_documentation(lookup_file, lookup_metadata)

                if lookup_metadata:
                    output_name = lookup_metadata["name"] + ".md"
                else:
                    output_name = lookup

                output_path = (
                    LOOKUP_DOCS_FOLDER / system_lookups / safe_file_name(output_name)
                )

                if not os.path.exists(LOOKUP_DOCS_FOLDER / system_lookups):
                    os.mkdir(LOOKUP_DOCS_FOLDER / system_lookups)

                if GLFM:
                    output_path = Path(str(output_path).replace(" ", "-"))

                with open(output_path, "w+", encoding="utf-8") as output:
                    output.write(doc)

                log("SUCCESS", "Generated lookup documentation for all lookup files")


if __name__ == "__main__":
    run()
