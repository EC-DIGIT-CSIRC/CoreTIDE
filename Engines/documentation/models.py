import os
import git
from pathlib import Path
import sys
import shutil
import time

start_time = time.time()

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))
from Engines.modules.framework import (
    get_type,
    childs,
    parents,
    techniques_resolver,
    get_vocab_entry,
)
from Engines.modules.documentation import (
    get_icon,
    rich_attack_links,
    GitlabMarkdown,
    sanitize_hover,
    FOLD,
)
from Engines.modules.documentation_components import (
    criticality_doc,
    classification_doc,
    metadata_doc,
    reference_doc,
    tlp_doc,
    relations_table,
    cve_doc,
    model_data_table,
)
from Engines.modules.files import safe_file_name
from Engines.modules.graphs import relationships_graph, chaining_graph
from Engines.modules.tide import DataTide
from Engines.modules.logs import log
from Engines.modules.deployment import Proxy
from Engines.templates.models import MODEL_DOC_TEMPLATE

ROOT = Path(str(git.Repo(".", search_parent_directories=True).working_dir))
MODELS_DOCS_PATH = Path(DataTide.Configurations.Global.Paths.Core.models_docs_folder)
MODELS_SCOPE = DataTide.Configurations.Documentation.scope.copy()
GLFM = DataTide.Configurations.Documentation.glfm_doc_target
DOCUMENTATION_TYPE = DataTide.Configurations.Documentation.documentation_type
MODELS_INDEX = DataTide.Models.Index

if DataTide.Configurations.Documentation.cve.get("proxy"):
    Proxy.set_proxy()
else:
    Proxy.unset_proxy()


def documentation(model):

    model_uuid = model.get("metadata", {}).get("uuid")
    model_type = get_type(model_uuid)
    uuid = f"UUID : *{model_uuid}*"

    if DOCUMENTATION_TYPE == "MARKDOWN":
        frontmatter_type = DataTide.Configurations.Documentation.object_names[
            model_type
        ].replace("/", "")
        frontmatter = f"---\ntype: {frontmatter_type}\n---"
    elif DOCUMENTATION_TYPE == "GLFM":
        frontmatter = ""

    model_datafield = DataTide.Configurations.Global.data_fields[model_type]
    title = f"# {get_icon(model_type)} {model['name']}"
    criticality = criticality_doc(model["criticality"])
    metadata = model.get("metadata") or model.get("meta") or {}
    metadata = {k: v for k, v in metadata.items() if k != "tlp"}
    metadata = metadata_doc(metadata, model_type="tvm")

    expand_header = ""
    expand_description = ""
    expand_graphs = ""

    if DOCUMENTATION_TYPE == "GLFM":
        title = ""

    references = model.get("references")
    # To deprecate once everything is migrated to new reference system
    if type(references) is list:
        references = "- " + "\n- ".join(references)
    elif type(references) is dict:
        references = reference_doc(model.get("references"))

    description = model[model_datafield].get("description") or model[
        model_datafield
    ].get("guidelines")
    description = description.replace("\n", "\n> ")

    tlp = tlp_doc((model.get("metadata") or model["meta"])["tlp"])
    classification = (model.get("metadata") or model["meta"]).get(
        "classification"
    ) or ""
    if classification:
        classification = classification_doc(classification)

    techniques = techniques_resolver(model_uuid, recursive=False)
    if techniques:
        techniques = rich_attack_links(techniques)
        techniques = f'{get_icon("att&ck")} **ATT&CK Techniques** {techniques}'

    relation_graph = relationships_graph(model_uuid)
    relation_table = ""
    if childs(model_uuid):
        relation_table = "\n\n **Descendants** \n\n" + relations_table(
            model_uuid, direction="downstream"
        )
    if parents(model_uuid):
        relation_table += "\n\n **Ascendants** \n\n"
        relation_table += relations_table(model_uuid, direction="upstream")

    if not relation_graph and not relation_table:
        relation_graph = "🚫 No related objects indexed."
        if DOCUMENTATION_TYPE == "GLFM":
            GitlabMarkdown.negative_diff(relation_graph)

    if model_type == "tam":
        misp = model[model_datafield].get("misp") or ""
        if misp:
            expand_header += f"\n\n{get_icon('misp')} **MISP Galaxy UUID** : `{misp}`"

        attack_group = model[model_datafield].get("att&ck_groups") or ""
        if attack_group:
            group_data = get_vocab_entry("att&ck_groups", attack_group)
            if type(group_data) is dict:
                group_description = group_data["description"]
                hover_link = f'"{sanitize_hover(group_description)}"'
                expand_header += f"\n\n{get_icon('att&ck_groups')} **MITRE ATT&CK Group** : [ ` {attack_group} - {group_data['name']} `]({group_data['link']} {hover_link})"

        aliases = model[model_datafield].get("aliases") or ""
        if aliases:
            expand_header += (
                f"\n\n{get_icon('aliases')} ` Other aliases : {', '.join(aliases)}`"
            )

    if model_type == "bdr":
        justification = model[model_datafield]["justification"].replace("\n", "\n> ")
        expand_description += f"\n\n## ❓ Justification \n\n > {justification}"

    if model_type == "cdm":
        tuning = model[model_datafield]["tuning"].replace("\n", "\n> ")
        expand_description += f"\n\n## 🔧 Tuning \n\n > {tuning}"

    if model_type == "tvm":

        terrain = model[model_datafield]["terrain"].replace("\n", "\n> ")
        expand_description += f"\n\n## 🖥️ Terrain \n\n > {terrain}"

        cve = model[model_datafield].get("cve")
        if cve:
            cve = cve_doc(cve)
            expand_description += f"\n\n {cve}"

        chain_diagram, chain_table = chaining_graph(model_uuid)
        if chain_diagram and chain_table:
            expand_graphs += "\n\n --- \n\n### ⛓️ Threat Chaining\n\n"
            expand_graphs += chain_diagram + "\n\n"
            expand_graphs += (
                FOLD.format("Expand chaining data", chain_table) + "\n\n --- \n"
            )

    data_table, tags = model_data_table(model[model_datafield], model_uuid)

    if GLFM:
        tags = ""
    else:
        tags = "#" + ", #".join(tags)

    doc = MODEL_DOC_TEMPLATE.format(**locals())

    return doc


def run():

    log("TITLE", "Models Documentation")
    log(
        "INFO",
        "Generates the documentation for all models, with hyperlinks in a folder structure",
    )

    # Initialize a counter of created documents
    doc_count = 0

    for model_type in MODELS_SCOPE:

        doc_type_path = (
            MODELS_DOCS_PATH
            / DataTide.Configurations.Documentation.object_names[model_type]
        )
        if DOCUMENTATION_TYPE == "GLFM":
            doc_type_path = Path(str(doc_type_path).replace(" ", "-"))

        # Remove everything in the doc folder for the model
        if os.path.exists(doc_type_path):
            shutil.rmtree(doc_type_path)
        log(
            "INFO",
            "📁 Creating documentation folder : {}... ".format(str(doc_type_path)),
        )
        doc_type_path.mkdir(parents=True)

        for model in MODELS_INDEX[model_type]:

            # Make a file name based on  data
            model_data = MODELS_INDEX[model_type][model]
            doc_name = model_data.get("name").replace("_", " ")
            doc_file_name = (
                f"{get_icon(model_type)} {doc_name.strip()}.md"
            )

            doc_file_name = safe_file_name(doc_file_name)
            doc_path = doc_type_path / doc_file_name

            # Replace whitespace in file name as it becomes a path in the Gitlab MODELS_DOCS_PATH
            if DOCUMENTATION_TYPE == "GLFM":
                doc_path = Path(str(doc_path).replace(" ", "-"))

            log("ONGOING", "Generating documentation", doc_file_name)
            document = documentation(model_data)

            with open(doc_path, "w+", encoding="utf-8") as output:
                output.write(document)
                doc_count += 1

    if DOCUMENTATION_TYPE == "MARKDOWN":
        doc_format_log = "✒️ standard markdown"
    elif DOCUMENTATION_TYPE == "GLFM":
        doc_format_log = "🦊 Gitlab Flavored Markdown"
    else:
        doc_format_log = ""

    time_to_execute = "%.2f" % (time.time() - start_time)

    log("INFO", f"Generated {doc_count} documents in {time_to_execute} seconds")
    log("SUCCESS", "Successfully built CoreTIDE documentation in format", doc_format_log)


if __name__ == "__main__":
    run()
