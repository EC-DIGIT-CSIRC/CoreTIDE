import os
import git
import sys
from pathlib import Path
import yaml
import toml

### TO REMOVE FROM OPEN SOURCE

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logs import log
from Engines.modules.files import resolve_paths

ROOT = Path(str(git.Repo(".", search_parent_directories=True).working_dir))

PATHS = resolve_paths()
MODELS_SCOPE = ["tam", "tvm", "cdm", "bdr", "mdr"]
MODELS_FOLDER = dict()

for model in MODELS_SCOPE:
    MODELS_FOLDER[model] = PATHS[model]
PRIVATE_DOMAIN = "s.cec.eu.int"
REF_TEMPLATE = """#references:
  #public:
    #1: 
  #internal:
    #a:
  #restricted:
    #A
  #reports:
    #-
"""


class MyDumper(yaml.Dumper):

    def increase_indent(self, flow=False, indentless=False):
        return super(MyDumper, self).increase_indent(flow, False)


def upgrade_refs(old_refs):

    old_refs = old_refs.get("references")
    new = dict()

    if old_refs:
        public_refs = dict()
        internal_refs = dict()

        internal_refs_list = [
            ref.strip()
            for ref in old_refs
            if PRIVATE_DOMAIN in ref or (".pdf" in ref and "https" not in ref)
        ]
        public_refs_list = [
            ref.strip() for ref in old_refs if ref not in internal_refs_list
        ]

        public_counter = 1
        for pub_ref in public_refs_list:
            public_refs[public_counter] = pub_ref
            public_counter += 1

        internal_counter = "a"
        for int_ref in internal_refs_list:
            internal_refs[chr(ord(internal_counter))] = int_ref
            internal_counter = chr(ord(internal_counter) + 1)

        if public_refs:
            new["public"] = public_refs
        else:
            new["com_public"] = {"com_1": "rem"}

        if internal_refs:
            new["internal"] = internal_refs
        else:
            new["com_internal"] = {"com_a": "rem"}

        new["com_restricted"] = {"com_A": "rem"}
        new["com_reports"] = ["list"]

        new = {"references": new}
        new = yaml.dump(new, sort_keys=False)
        new = new.replace("com_", "#")
        new = new.replace("rem", "")
        new = new.replace("- list", "  #-")  # Handle indent here since only case
    else:
        new = REF_TEMPLATE
    return new


def run():

    for model_type in MODELS_SCOPE:
        folder = MODELS_FOLDER[model_type]
        log("INFO", "Now processing all files under model type", model_type)
        for file in sorted(os.listdir(folder)):
            raw_body = open(folder / file, "r", encoding="utf-8").read()
            current_references = yaml.safe_load(raw_body).get("references")
            if current_references and (type(current_references) is not list):
                log("DEBUG", "No need to migrate", file)

            elif "#public:" not in raw_body.split("metadata:")[0]:
                log("ONGOING", "Migrating to new references model", file)
                header = raw_body.split("meta:")[0]
                large_block = "metadata:" + raw_body.split("meta:")[1]

                old_references = ""

                ""
                if "#references" in header:
                    new_references = REF_TEMPLATE
                    header = header.split("#references")[0]
                    large_block = "\n" + large_block
                if "references" in header:
                    old_references = "references:" + header.split("references:")[1]
                    old_references = yaml.safe_load(old_references)

                    new_references = upgrade_refs(old_references)
                    new_references = new_references + "\n"
                    header = header.split("references")[0]
                else:
                    new_references = REF_TEMPLATE

                body = ""
                body = header + new_references + large_block

                output_path = folder / file
                # output_path = Path("./DEBUG") / file
                with open(output_path, "w+", encoding="utf-8") as export:
                    export.write(body)

    log("SUCCESS", "Ensured all files are migrated to the new reference schema")


if __name__ == "__main__":
    run()
