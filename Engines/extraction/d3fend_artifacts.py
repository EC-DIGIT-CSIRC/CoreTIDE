import yaml
import os
import git
import sys
import json
from pathlib import Path

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))
from Engines.modules.tide import DataTide


RESOURCES = Path(DataTide.Configurations.Global.Paths.Core.resources)

D3FEND_ONTOLOGY_PATH = DataTide.Configurations.Resources.d3fend["ontology"]
D3FEND_COUNTERMEASURES_PATH = DataTide.Configurations.Resources.d3fend[
    "countermeasures"
]
VOCABS_PATH = Path(DataTide.Configurations.Global.Paths.Core.vocabularies)
# Used to create links to the artifact page
DAOLINK = "https://d3fend.mitre.org/dao/artifact/"
# Used by some artifacts "see also" entries
DBPEDIA = "https://dbpedia.org/page/"

OUT_NAME = "D3FEND Digital Artifacts.yaml"

with open(RESOURCES / D3FEND_ONTOLOGY_PATH, encoding="utf8") as file:
    D3FEND_ONTOLOGY = json.load(file)

voc_artifacts = []


class IndentFullDumper(yaml.Dumper):

    def increase_indent(self, flow=False, indentless=False):
        return super(IndentFullDumper, self).increase_indent(flow, False)


for i in D3FEND_ONTOLOGY["@graph"]:
    if "rdfs:subClassOf" in i.keys():
        if "rdfs:comment" in i.keys():
            if not "d3f:attack-id" in i.keys():
                if not "d3f:d3fend-id" in i.keys():
                    entry = {}
                    entry["id"] = i["@id"]
                    entry["name"] = i["rdfs:label"]

                    synonyms = i.get("skos:altLabel") or ""
                    description = i["rdfs:comment"]
                    see_also = i.get("rdfs:seeAlso") or ""
                    see_also_links = []
                    if see_also != "":
                        if type(see_also) is dict:
                            see_also_links = [see_also["@id"]]
                        elif type(see_also) is list:

                            # Oddity, sometimes list of see_also items contains a string,
                            # where it seems to be expected to contain dicts instead
                            see_also_links = [
                                l["@id"] for l in see_also if type(l) is dict
                            ]

                        see_also_final = list()
                        for sa_link in see_also_links:
                            if sa_link[:4] == "dbr:":
                                see_also_final.append(DBPEDIA + sa_link[4:])
                            elif sa_link[:4] == "d3f:":
                                see_also_final.append(DAOLINK + sa_link[4:])
                            else:
                                see_also_final.append(sa_link)

                        see_also_final = ", ".join(see_also_final)
                        see_also = f"\n\nSee also : {see_also_final}"

                    if synonyms != "":
                        if type(synonyms) is list:
                            synonyms = ", ".join(synonyms)

                        synonyms = f"\n\nSynonyms : {synonyms}"

                    final_description = f"{description}{synonyms}{see_also}"

                    entry["description"] = final_description
                    entry["link"] = DAOLINK + entry["id"]
                    voc_artifacts.append(entry)

vocab_file = yaml.safe_load(open(VOCABS_PATH / OUT_NAME, encoding="utf-8"))

with open(VOCABS_PATH / OUT_NAME, "w+", encoding="utf-8") as out:
    vocab_file["keys"].clear()
    vocab_file["keys"] = voc_artifacts
    yaml.dump(
        vocab_file, out, sort_keys=False, Dumper=IndentFullDumper, allow_unicode=True
    )
