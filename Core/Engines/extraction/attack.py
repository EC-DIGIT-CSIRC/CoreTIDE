import pandas as pd
import yaml
import os
import git
import sys
from pathlib import Path

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))
from Core.Engines.modules.tide import DataTide

ATTACK_PATH = Path(DataTide.Configurations.Global.paths["att&ck"])
ATTACK_RESOURCES = DataTide.Configurations.Resources.attack
enterprise = ATTACK_PATH / ATTACK_RESOURCES["enterprise"]
mobile = ATTACK_PATH / ATTACK_RESOURCES["mobile"]
ics = ATTACK_PATH / ATTACK_RESOURCES["ics"]

vocab_folder = Path(DataTide.Configurations.Global.paths["vocabularies"])
techniques_vocab = r"ATT&CK Techniques.yaml"
datasources_vocab = r"ATT&CK Data Sources.yaml"
mitigations_vocab = r"ATT&CK Mitigations.yaml"
groups_vocab = vocab_folder / "ATT&CK Groups.yaml"


class IndentFullDumper(yaml.Dumper):

    def increase_indent(self, flow=False, indentless=False):
        return super(IndentFullDumper, self).increase_indent(flow, False)


def gen_techniques_vocab(attack_table, out_file, prefix=None):

    if prefix is None:
        prefix = ""

    else:
        prefix += " : "

    df = pd.read_excel(attack_table, sheet_name="techniques")
    df = df[["ID", "name", "tactics", "description", "url"]]
    df = df.rename(columns={"ID": "id", "tactics": "stage", "url": "link"})
    keys = df.to_dict("records")

    for p in keys:
        p["name"] = prefix + p["name"]
        p["tide.vocab.stages"] = [
            (
                tac.replace("Ics", "").strip()
                if tac != "Evasion Ics"
                else "Defense Evasion"
            )
            for tac in p["tide.vocab.stages"].split(", ")
        ]

    out_file_body = yaml.safe_load(open(out_file, encoding="utf-8"))
    out_file_body["keys"].extend(keys)

    output = open(out_file, "w", encoding="utf-8")
    yaml.dump(
        out_file_body,
        output,
        sort_keys=False,
        allow_unicode=True,
        Dumper=IndentFullDumper,
    )
    output.close()


def gen_datasources_vocab(attack_table, out_file):
    df = pd.read_excel(attack_table, sheet_name="datasources")
    df = df[["ID", "name", "description", "url"]]
    df = df.rename(columns={"ID": "id", "url": "link"})

    """
    for col in ['id', 'link']:
        df[col] = df[col].ffill()
    """
    keys = df.to_dict("records")

    reference = keys.copy()

    for item in keys:
        if type(item["id"]) != str:
            suffix = item["name"].split(":")[1].lstrip()
            prefix = item["name"].split(":")[0].rstrip()
            print(prefix)
            link = item["link"]
            for internal in reference:
                if internal["name"] == prefix:
                    item["id"] = internal["id"]
                    item["name"] = suffix
                    item["link"] = internal["link"]

    out_file_body = yaml.safe_load(open(out_file, encoding="utf-8"))
    out_file_body["keys"].extend(keys)

    output = open(out_file, "w", encoding="utf-8")
    yaml.dump(
        out_file_body,
        output,
        sort_keys=False,
        allow_unicode=True,
        Dumper=IndentFullDumper,
    )
    output.close()


def gen_mitigations_vocab(attack_table, out_file, prefix=None):

    if prefix is None:
        prefix = ""

    else:
        prefix += " : "

    df = pd.read_excel(attack_table, sheet_name="mitigations")
    df = df[["ID", "name", "description", "url"]]
    df = df.rename(columns={"ID": "id", "url": "link"})
    keys = df.to_dict("records")

    for p in keys:
        p["name"] = prefix + p["name"]

    out_file_body = yaml.safe_load(open(out_file, encoding="utf-8"))
    out_file_body["keys"].extend(keys)

    output = open(out_file, "w", encoding="utf-8")
    yaml.dump(
        out_file_body,
        output,
        sort_keys=False,
        allow_unicode=True,
        Dumper=IndentFullDumper,
    )
    output.close()


def gen_group_vocab(attack_table: pd.DataFrame, prefix=""):

    df = attack_table
    df = df[["ID", "name", "description", "url"]]
    df = df.rename(columns={"ID": "id", "url": "link"})
    groups_data = df.to_dict("records")

    for p in groups_data:
        p["name"] = prefix + p["name"]

    return groups_data


# Generate groups vocab

enterprise_groups = pd.read_excel(enterprise, sheet_name="groups")
data = gen_group_vocab(enterprise_groups)
vocab_data = yaml.safe_load(open(groups_vocab, encoding="utf-8"))
vocab_data["keys"] = data
with open(groups_vocab, "w", encoding="utf-8") as vocab:
    yaml.dump(
        vocab_data, vocab, sort_keys=False, allow_unicode=True, Dumper=IndentFullDumper
    )

# Resets techniques table
out_file_body = yaml.safe_load(open(vocab_folder / techniques_vocab, encoding="utf-8"))
out_file_body["keys"].clear()
output = open(vocab_folder / techniques_vocab, "w", encoding="utf-8")
yaml.dump(
    out_file_body, output, sort_keys=False, allow_unicode=True, Dumper=IndentFullDumper
)
output.close()

# Creates Techniques
gen_techniques_vocab(enterprise, os.path.join(vocab_folder, techniques_vocab))
gen_techniques_vocab(
    mobile, os.path.join(vocab_folder, techniques_vocab), prefix="Mobile"
)
gen_techniques_vocab(
    ics, os.path.join(vocab_folder, techniques_vocab), prefix="Industrial"
)


# Resets datasources
out_file_body = yaml.safe_load(open(vocab_folder / datasources_vocab))
out_file_body["keys"].clear()
output = open(vocab_folder / datasources_vocab, "w", encoding="utf-8")
yaml.dump(
    out_file_body, output, sort_keys=False, allow_unicode=True, Dumper=IndentFullDumper
)
output.close()


# Creates Datasources and Data documentation_components
gen_datasources_vocab(enterprise, os.path.join(vocab_folder, datasources_vocab))


# Resets Mitigations
out_file_body = yaml.safe_load(open(vocab_folder / mitigations_vocab, encoding="utf-8"))
out_file_body["keys"].clear()
output = open(vocab_folder / mitigations_vocab, "w", encoding="utf-8")
yaml.dump(
    out_file_body, output, sort_keys=False, allow_unicode=True, Dumper=IndentFullDumper
)
output.close()


# Create Mitigations vocab
gen_mitigations_vocab(enterprise, os.path.join(vocab_folder, mitigations_vocab))
gen_mitigations_vocab(
    mobile, os.path.join(vocab_folder, mitigations_vocab), prefix="Mobile"
)
gen_mitigations_vocab(
    ics, os.path.join(vocab_folder, mitigations_vocab), prefix="Industrial"
)
gen_mitigations_vocab(
    mobile, os.path.join(vocab_folder, mitigations_vocab), prefix="Mobile"
)
gen_mitigations_vocab(
    ics, os.path.join(vocab_folder, mitigations_vocab), prefix="Industrial"
)
