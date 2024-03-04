import yaml
import git
import sys
import os
from collections import OrderedDict
from pathlib import Path
from urllib.parse import quote_plus

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logs import log
from Engines.modules.tide import DataTide

VOCABS_FOLDER = Path(DataTide.Configurations.Global.Paths.Core.vocabularies)
ICONS = DataTide.Configurations.Documentation.icons
WIKI_PATH = (
    str(DataTide.Configurations.Documentation.models_docs_folder)
    .replace("../", "")
    .replace(" ", "-")
)
WIKI_MODEL_FOLDER = DataTide.Configurations.Documentation.object_names

if os.getenv("TIDE_WIKI_GENERATION") == "GITLAB_WIKI":
    WIKI_URL = f"{os.getenv('CI_SERVER_URL')}/{os.getenv('CI_PROJECT_PATH')}/_/wikis/"
else:
    WIKI_URL = DataTide.Configurations.Documentation.wiki.get("wiki_link")


class IndentFullDumper(yaml.Dumper):

    def increase_indent(self, flow=False, indentless=False):
        return super(IndentFullDumper, self).increase_indent(flow, False)


def gen_lib_model_keys(model, model_type):
    """
    Takes the path of a model file and generates the corresponding vocabulary
    key

    Parameters
    ----------
    path : path from the file to use for generation

    Returns
    -------
    buffer : returns two keys : id (the unique tidemec ID of the model
            contained in the file), and its name.

    """

    buffer = {}

    iterator = model
    buffer["id"] = iterator["id"]
    name = iterator["name"]
    description = ""

    if "actor" in iterator.keys():
        aliases = iterator["actor"]["aliases"]
        description = iterator["actor"]["description"].replace("\n", " ")
        if aliases:
            buffer["aliases"] = aliases

    if "threat" in iterator.keys():
        description = iterator["threat"]["description"].replace("\n", " ")

    if "detection" in iterator.keys():
        description = iterator["detection"]["guidelines"].replace("\n", " ")

    if "request" in iterator.keys():
        description = iterator["request"]["description"].replace("\n", " ")

    buffer["name"] = name
    buffer["description"] = description
    buffer["criticality"] = iterator["criticality"]

    if "tlp" in (iterator.get("metadata") or iterator.get("meta")):
        buffer["tlp"] = (iterator.get("metadata") or iterator.get("meta"))["tlp"]

    doc_wiki_path = f"{ICONS[model_type]} [{iterator['id']}] {name}"
    doc_wiki_path = doc_wiki_path.replace(" ", "-")
    doc_wiki_path = quote_plus(doc_wiki_path)

    model_wiki_subfolder = WIKI_MODEL_FOLDER[model_type].replace(" ", "-")

    full_link = WIKI_URL + WIKI_PATH + model_wiki_subfolder + doc_wiki_path
    buffer["link"] = full_link

    return buffer


def run():

    log("TITLE", "Generate Vocabularies from Model Data")
    log(
        "INFO",
        "Creates Vocabulary entries for TIDeMEC models, so they can be used within JSON Schema for validation.",
    )

    for model in (n := DataTide.Configurations.Global.models_vocabularies):

        output_file_name = n[model]
        out_file_path = VOCABS_FOLDER / output_file_name
        keys = []

        # Edge case : for actors specifically it is often possible that no
        # attribution is possible, but it needs to be put full verbose rather than
        # making actors an optional field.
        if output_file_name == "Threat Actors.yaml":
            unknown_field = {}
            unknown_field["id"] = "Unknown"
            unknown_field["name"] = "Field to be used when no attribution is possible"
            keys.append(unknown_field)

        # Loops through every file in the current model folder
        for object in (i := DataTide.Models.Index[model]):
            output = gen_lib_model_keys(i[object], model_type=model)
            keys.append(output)

        # Updating the keys to the output file, as designated by the
        # folders_to_lib_file dictionary for the current folder.
        out_file_body = yaml.safe_load(
            open(out_file_path, encoding="utf-8", errors="ignore")
        )

        # bdr can be referenced by MDR alongside CDMs
        if model == "bdr":
            out_file_body["keys"] += keys
        else:
            out_file_body["keys"] = keys

        # Reordering keys as per standard to improve readibility
        out_file_body = OrderedDict(out_file_body)
        key_order = ["name", "field", "model", "keys"]
        for k in key_order:
            out_file_body.move_to_end(k)

        ordered_output = dict(out_file_body)

        log("INFO", "Writing vocabulary entry for model type", model)
        # Writes the file
        with open(out_file_path, "w+", encoding="utf-8") as output:
            yaml.dump(
                ordered_output,
                output,
                sort_keys=False,
                Dumper=IndentFullDumper,
                allow_unicode=True,
            )

    log("SUCCESS", "Finished indexing all models as vocabularies")


if __name__ == "__main__":
    run()
