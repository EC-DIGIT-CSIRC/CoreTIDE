import yaml
import os
import git
import sys
from pathlib import Path
import pandas as pd

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))
from Engines.modules.tide import DataTide

RESOURCES = Path(DataTide.Configurations.Global.paths["resources"])

D3FEND_COUNTERMEASURES_PATH = DataTide.Configurations.Resources.d3fend[
    "countermeasures"
]

# Used to create links to the countermeasure page
COUNTERMEASURES_LINK = "https://d3fend.mitre.org/technique/"

VOCABS_PATH = Path(DataTide.Configurations.Global.paths["vocabularies"])
OUT_NAME = "D3FEND Countermeasures.yaml"

D3FEND_COUNTERMEASURES = (
    pd.read_csv(RESOURCES / D3FEND_COUNTERMEASURES_PATH)
    .fillna("")
    .to_dict(orient="records")
)


class IndentFullDumper(yaml.Dumper):

    def increase_indent(self, flow=False, indentless=False):
        return super(IndentFullDumper, self).increase_indent(flow, False)


voc_countermeasures = list()

for c in D3FEND_COUNTERMEASURES:
    entry = {}
    entry["id"] = c["ID"]

    if c["D3FEND Technique"] != "":
        entry["name"] = c["D3FEND Technique"]
    elif c["D3FEND Technique Level 0"] != "":
        entry["name"] = c["D3FEND Technique Level 0"]
    elif c["D3FEND Technique Level 1"] != "":
        entry["name"] = c["D3FEND Technique Level 1"]

    entry["tide.vocab.stages"] = c["D3FEND Tactic"]
    entry["description"] = c.get("Definition")
    entry["link"] = COUNTERMEASURES_LINK + entry["id"]

    if entry["description"] == "":
        entry["description"] = (
            "No description exposed by D3FEND in their .csv currently - visit the link for more description about the countermeasure"
        )

    voc_countermeasures.append(entry)


vocab_file = yaml.safe_load(open(VOCABS_PATH / OUT_NAME, encoding="utf-8"))

with open(VOCABS_PATH / OUT_NAME, "w+", encoding="utf-8") as out:
    vocab_file["keys"].clear()
    vocab_file["keys"] = voc_countermeasures
    yaml.dump(
        vocab_file, out, sort_keys=False, Dumper=IndentFullDumper, allow_unicode=True
    )
