import pandas as pd
import os
import git
import sys
import yaml
from pathlib import Path

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))
from Core.Engines.modules.tide import DataTide

RESOURCE_PATH = Path(DataTide.Configurations.Global.paths["resources"])
ENGAGE_DATA = DataTide.Configurations.Resources.engage["matrix"]

vocab_folder = Path(DataTide.Configurations.Global.paths["vocabularies"])
out_file = vocab_folder / "MITRE Engage.yaml"


class IndentFullDumper(yaml.Dumper):

    def increase_indent(self, flow=False, indentless=False):
        return super(IndentFullDumper, self).increase_indent(flow, False)


df = pd.read_excel(RESOURCE_PATH / ENGAGE_DATA, sheet_name="Activities")
df = df[["ID", "name", "Approaches", "short description", "long description", "url"]]
df = df.rename(columns={"ID": "id", "Approaches": "stage", "url": "link"})
keys = df.to_dict("records")

for k in keys:
    k["description"] = k["short description"] + "\n\n" + k["long description"]
    k["description"] = (
        "Approaches : " + k["tide.vocab.stages"] + "\n" + k["description"]
    )
    k.pop("short description")
    k.pop("long description")

out_file_body = yaml.safe_load(open(out_file))
out_file_body["keys"] = keys

output = open(out_file, "w")
yaml.dump(out_file_body, output, sort_keys=False, Dumper=IndentFullDumper)
output.close()
