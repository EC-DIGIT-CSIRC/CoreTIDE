import yaml
from pathlib import Path
import os
import git
import sys
import re

ra_vocab = []
CONFIG = yaml.safe_load(open("../../Resources/config.yaml", encoding="utf-8"))
actions_vocab = "RE&CT Response Actions.yaml"
lib_folder = Path(CONFIG["paths"]["core"]["vocabularies"])
out_file = lib_folder / actions_vocab

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))
from Engines.modules.tide import DataTide

RESOURCES = Path(DataTide.Configurations.Global.paths["resources"])
ATC_REACT = RESOURCES / "atc-react"


class IndentFullDumper(yaml.Dumper):

    def increase_indent(self, flow=False, indentless=False):
        return super(IndentFullDumper, self).increase_indent(flow, False)


def normalize_react_title(
    title,
    fmtrules={
        "abbreviations": [
            "ip",
            "dns",
            "ms",
            "ngfw",
            "ips",
            "url",
            "pe",
            "pdf",
            "elf",
            "dhcp",
            "vpn",
            "smb",
            "ftp",
            "http",
        ],
        "capitalizeWords": ["unix", "windows", "proxy", "firewall", "mach-o"],
    },
):
    """Normalize title if it is a RA/RP title in the following format:
    RP_0003_identification_make_sure_email_is_a_phishing
    """

    react_id_re = re.compile(r"R[AP]_\d{4}_.*$")
    if react_id_re.match(title):
        title = title[8:].split("_", 0)[-1].replace("_", " ").capitalize()
        new_title = ""
        for word in title.split():
            if word.lower() in fmtrules["abbreviations"]:
                new_title += word.upper()
                new_title += " "
                continue
            elif word.lower() in fmtrules["capitalizeWords"]:
                new_title += word.capitalize()
                new_title += " "
                continue
            new_title += word
            new_title += " "
        return new_title.strip()
    return title


for ra in os.listdir(ATC_REACT):
    ra_body = yaml.safe_load(open(ATC_REACT / ra))
    ra_entry = {}
    ra_entry["id"] = ra_body["id"]
    ra_entry["name"] = normalize_react_title(ra_body["title"])
    ra_entry["description"] = ra_body["description"]
    ra_entry["tide.vocab.stages"] = ra_body["tide.vocab.stages"].capitalize()
    ra_entry["workflow"] = ra_body["workflow"]

    if ra_entry["workflow"].startswith("Description of the workflow"):
        ra_entry["workflow"] = "Placeholder"

    if ra_entry["tide.vocab.stages"] == "Lessons_learned":
        ra_entry["tide.vocab.stages"] = "Lessons Learned"

    if ra_entry["id"] != "RA0000":
        ra_vocab.append(ra_entry)


out_file_body = yaml.safe_load(open(out_file))
out_file_body["keys"] = ra_vocab
output = open(out_file, "w")
yaml.dump(out_file_body, output, sort_keys=False, Dumper=IndentFullDumper)
output.close()
