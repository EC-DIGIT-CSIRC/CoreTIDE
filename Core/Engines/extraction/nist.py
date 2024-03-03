import pandas as pd
import yaml
import os
import git
import sys
from pathlib import Path
import unicodedata

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))
from Core.Engines.modules.tide import DataTide

RESOURCES = Path(DataTide.Configurations.Global.paths["resources"])
NIST_DATA = DataTide.Configurations.Resources.nist["data"]
VOCABS_PATH = Path(DataTide.Configurations.Global.paths["vocabularies"])

nist_vocab = r"NIST Cybersecurity Framework.yaml"


class IndentFullDumper(yaml.Dumper):

    def increase_indent(self, flow=False, indentless=False):
        return super(IndentFullDumper, self).increase_indent(flow, False)


df = pd.read_excel(RESOURCES / NIST_DATA)
df = df.drop_duplicates(subset=["Subcategory"])
df = df.fillna(method="ffill")
keys = df.to_dict("records")

out = []
for k in keys:
    buf = {}
    buf["id"] = str(k["Subcategory"]).split(":")[0].rstrip()
    buf["name"] = str(k["Subcategory"]).split(":")[1].lstrip()
    buf["description"] = "Category : " + k["Category"].replace("’", "'")
    buf["stage"] = k["Function"].capitalize().split(" (")[0]
    out.append(buf)


out_file_body = yaml.safe_load(open(VOCABS_PATH / nist_vocab, encoding="utf-8"))
out_file_body["keys"] = out

output = open(VOCABS_PATH / nist_vocab, "w", encoding="utf-8")
yaml.dump(out_file_body, output, sort_keys=False, Dumper=IndentFullDumper)
output.close()
