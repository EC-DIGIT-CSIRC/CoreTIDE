import os
import git
import yaml
import json
from pathlib import Path
import sys
import toml
import git
from pprint import pprint

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.files import resolve_paths, resolve_configurations
from Engines.modules.logs import log

def indexer(write_index=False) -> dict:
    ROOT = Path(str(git.Repo(".", search_parent_directories=True).working_dir))
    TIDE_CONFIG = toml.load(
        open(ROOT / "Configurations/global.toml", encoding="utf-8")
    )
    SKIPS = ["logsources", "ram", "mdrv2", "lookup_metadata"]
    
    PATHS = resolve_paths()
    log("INFO", "Loaded all paths")
    pprint(PATHS)
    VOCAB_PATH = PATHS["vocabularies"]
    METASCHEMA_PATH = PATHS["metaschemas"]
    METASCHEMAS = TIDE_CONFIG["metaschemas"]
    JSONSCHEMAS_PATH = PATHS["json_schemas"]
    JSONSCHEMAS = TIDE_CONFIG["json_schemas"]
    SUBSCHEMAS_PATH = PATHS["subschemas"]
    DEFINITIONS_PATH = PATHS["definitions"]
    RECOMPOSITION = TIDE_CONFIG["recomposition"]
    TEMPLATES_PATH = PATHS["templates"]
    TEMPLATES = TIDE_CONFIG["templates"]
    LOOKUPS_PATH = PATHS["lookups"]

    OUTPUT_PATH = PATHS["index_output"]
    # Controls whether the index should keep in memory or export to a file
    # In-memory is helpful when index is used to accelerate functions, like
    # for example to enrich deployment tags.

    index = dict()
    obj_counter = 0

    print("\n" + "Global Indexer".center(80, "=") + "\n")

    # Vocab Indexer

    print("📒 Indexing Vocabularies...")

    voc_index = dict()

    for voc_file in os.listdir(VOCAB_PATH):
        obj_counter += 1

        voc_body = yaml.safe_load(open(VOCAB_PATH / voc_file, encoding="utf-8"))

        voc_meta = {i: voc_body[i] for i in voc_body if i not in ["field", "keys"]}
        voc_data = dict()
        for k in voc_body["keys"]:
            # If model modifier, we index using the id instead since we want to reference it.
            if voc_meta.get("model"):
                voc_name = k.get("id")
                voc_data[voc_name] = {i: k[i] for i in k if i != "id"}
            else:
                voc_name = k.get("name")
                voc_data[voc_name] = {i: k[i] for i in k if i != "name"}

        voc_entry = dict()
        voc_entry["metadata"] = voc_meta
        voc_entry["entries"] = voc_data

        voc_index[voc_body["field"]] = voc_entry

    index["vocabs"] = voc_index

    # JSON Schemas Indexer
    print("🛠️ Indexing JSON Schemas...")

    json_index = dict()

    for meta_name in JSONSCHEMAS:
        json_schema_path = JSONSCHEMAS_PATH / JSONSCHEMAS[meta_name]
        if os.path.isfile(
            json_schema_path
        ):  # In case we are generating the json for the first time
            json_schema_body = json.load(open(json_schema_path, encoding="utf-8"))
            json_index[meta_name] = json_schema_body
            obj_counter += 1

    index["json_schemas"] = json_index

    # Config Indexer
    # Configurations resolve by merging the default Core configs
    # with custom ones defined in the user space
    config_index = resolve_configurations()

    index["configurations"] = config_index

    # Metaschema Indexer
    print("🛠️ Indexing Metaschemas...")

    meta_index = dict()

    for meta_name in METASCHEMAS:
        obj_counter += 1

        meta_body = yaml.safe_load(
            open(METASCHEMA_PATH / METASCHEMAS[meta_name], encoding="utf-8")
        )
        meta_index[meta_name] = meta_body

    index["metaschemas"] = meta_index

    # Definitions Indexer
    print("🛠️ Indexing Definitions...")

    definition_index = dict()

    for definition in os.listdir(DEFINITIONS_PATH):

        definition_body = yaml.safe_load(
            open(DEFINITIONS_PATH / definition, encoding="utf-8")
        )
        definition_name = definition.split(".")[0]
        definition_index[definition_name] = definition_body

    index["definitions"] = definition_index

    print("📐 Indexing Templates")

    template_index = dict()

    for cat in TEMPLATES:

        template_path = TEMPLATES_PATH / TEMPLATES[cat]

        if os.path.isfile(template_path):
            template = open(template_path, encoding="utf-8").read()
            template_index[cat] = template
            obj_counter += 1

    # Template indexer and Subschema indexer (as dependent on recomposition)
    print("📐 Indexing Recomposition Templates")
    print("🧩 Indexing Subschemas")

    subschemas_index = dict()
    for recomp in RECOMPOSITION:
        template_index[recomp] = {}
        subschemas_index[recomp] = {}
        sub_folder = RECOMPOSITION[recomp]
        subchemas_path = SUBSCHEMAS_PATH / sub_folder
        sub_templates_path = SUBSCHEMAS_PATH / sub_folder / "Templates"

        recomp_data = index["configurations"][recomp]

        for data in recomp_data:
            if recomp_data[data].get("tide", {}).get("enabled"):
                obj_counter += 1
                sub_name = recomp_data[data]["tide"]["name"]
                subschema_name = recomp_data[data]["tide"]["subschema"]

                sub_body = yaml.safe_load(
                    open(subchemas_path / (subschema_name + ".yaml"), encoding="utf-8")
                )
                subschemas_index[recomp][data] = sub_body

                template_body = open(
                    sub_templates_path / (sub_name + " Template.yaml"), encoding="utf-8"
                ).read()
                template_index[recomp][data] = template_body

    index["templates"] = template_index
    index["subschemas"] = subschemas_index

    # Models Indexer

    print("📊 Indexing Models...")

    models_index = dict()

    for meta_name in METASCHEMAS:
        if meta_name not in SKIPS:
            model_cat_index = dict()
            for model in os.listdir(PATHS[meta_name]):
                model_path = Path(PATHS[meta_name]) / model
                if not os.path.isdir(model_path):
                    obj_counter += 1

                    if "[DEBUG]" not in model:
                        model_body = yaml.safe_load(open(model_path, encoding="utf-8"))

                        if "uuid" in model_body.keys():
                            identifier = model_body["uuid"]
                        else:
                            identifier = model_body["id"]

                        model_cat_index[identifier] = model_body
            models_index[meta_name] = model_cat_index

    index["models"] = models_index

    # Lookups indexer

    print("🔎 Indexing Lookups...")

    lookup_index = dict()
    lookup_index["lookups"] = dict()
    lookup_index["metadata"] = dict()

    for system in os.listdir(LOOKUPS_PATH):
        lookup_index["lookups"][system.lower()] = dict()
        for lookup in os.listdir(LOOKUPS_PATH / system):
            if lookup.endswith(".csv"):
                lookup_name = lookup.replace(".csv", "")
                lookup_content = open(
                    LOOKUPS_PATH / system / lookup, mode="r", encoding="utf-8"
                ).read()
                lookup_index["lookups"][system.lower().replace(" ", "_")][
                    lookup_name
                ] = lookup_content
                obj_counter += 1

            elif lookup.endswith(".metadata.yaml"):
                metadata_name = lookup.replace(".metadata.yaml", "")
                metadata_content = yaml.safe_load(
                    open(LOOKUPS_PATH / system / lookup, encoding="utf-8")
                )
                lookup_index["metadata"][metadata_name] = metadata_content
                obj_counter += 1

    index["lookups"] = lookup_index

    # Security Stack Mapping Indexer

    # print("🔒 Indexing Cloud Security Stack Mappings...")
    #
    # CLOUD_MITIGATIONS = Path(CONFIG["paths"]["resources"]) / "security-stack-mappings"
    # CLOUD_PLATFORMS = ["AWS", "Azure" ,"GCP"]
    # CLOUD_MAPPINGS_INDEX = dict()
    #
    # for plat in CLOUD_PLATFORMS:
    #    path = CLOUD_MITIGATIONS / plat
    #    buf = list()
    #    for file in os.listdir(path):
    #        if not os.path.isdir(path / file) is True and file.endswith(".yaml"):
    #            obj_counter += 1
    #
    #            body = yaml.safe_load(open(path / file, encoding='utf-8'))
    #            buf.append(body)
    #    CLOUD_MAPPINGS_INDEX[plat] = buf
    #
    # index["security-stack-mappings"] = CLOUD_MAPPINGS_INDEX
    #
    #
    #
    ##ATT&CK relationship Indexer
    #
    # print("⛓️ Indexing ATT&CK Relationships...")
    #
    # ATTACK_ENT = Path(CONFIG["paths"]["att&ck"]) / CONFIG["resources"]["attack"]["enterprise"]
    # ATTACK_ICS = Path(CONFIG["paths"]["att&ck"]) / CONFIG["resources"]["attack"]["ics"]
    # ATTACK_MOB = Path(CONFIG["paths"]["att&ck"]) / CONFIG["resources"]["attack"]["mobile"]
    #
    # ENTERPRISE = pd.read_excel(open(ATTACK_ENT, 'rb'), sheet_name='relationships')
    # ICS = pd.read_excel(open(ATTACK_ICS, 'rb'), sheet_name='relationships')
    # MOBILE = pd.read_excel(open(ATTACK_MOB, 'rb'), sheet_name='relationships')
    #
    # df = pd.concat([ENTERPRISE, ICS, MOBILE])
    #
    # RELATIONSHIPS = df.to_json(orient="records")
    #
    # index["attack-relationships"] = RELATIONSHIPS
    #
    # obj_counter += len(df)
    #
    ##Atomics Indexer
    #
    # print("⚛️ Indexing Atomic Red Tests...")
    #
    # ATOMICS = Path(CONFIG["paths"]["resources"]) / "atomics"
    # ATOMICS_MAPPINGS_INDEX = dict()
    # KB_TO_ATOMIC = Path("../../../Automation/Resources/atomics/")
    #
    # for folder in os.listdir(ATOMICS):
    #    if os.path.isdir(ATOMICS/folder) and folder != "Indexes":
    #        obj_counter += 1
    #
    #        file_name = folder + ".yaml"
    #        doc_name = folder + ".md"
    #        body = yaml.safe_load(open(ATOMICS/folder/file_name, encoding='utf-8'))
    #        body["doc"] = open(ATOMICS/folder/doc_name, encoding='utf-8').read()
    #        ATOMICS_MAPPINGS_INDEX[folder] = body
    #
    # index["atomics"] = ATOMICS_MAPPINGS_INDEX
    #
    #

    if write_index or os.getenv("WRITE_INDEX"):
        print("📝 Exporting Index file to : {} ...".format(OUTPUT_PATH))
        with open(OUTPUT_PATH, "w+", encoding="utf-8") as index_file:
            json.dump(index, index_file, default=str)

    return index


if __name__ == "__main__":
    # if os.environ.get("GENERATE_INDEX_FILE"):
    #    indexer(write_index=True)
    # else:
    #    indexer()
    indexer(write_index=True)
