import os
import git
import yaml
import json
from pathlib import Path
import sys
import toml
import git
import uuid
from pprint import pprint

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.files import resolve_paths, resolve_configurations
from Engines.modules.logs import log
from Engines.templates.tide_indexes import fetch_tide_index_template

def micro_patching_tide_1(LEGACY_UUID_MAPPING:dict, model:dict, model_type:str)->dict:
    """
    Dynamic Micro-Patching on the fly object in staging with new UUIDs to pass validation.
    Once merged to main they will be migrated definitely.
    TODO - Remove before public release, as only concerns existing repositories
    """
    if os.getenv("CI_COMMIT_REF_NAME") == "main":
        log("SKIP", "Not patching for validation, in main")
        return model
    
    log("ONGOING", f"Evaluating patching validation requirements for {model['name']}")
    if not model.get("metadata", {}).get("uuid"):
        if "uuid" in model:
            model["metadata"]["uuid"] = model["uuid"]
        elif "id" in model:
            old_id = model.pop("id")
            if LEGACY_UUID_MAPPING:
                if old_id in LEGACY_UUID_MAPPING:
                    model["metadata"]["uuid"] = LEGACY_UUID_MAPPING[old_id]["uuid"]
                    log("INFO", f"Adding temporary new UUID to {model['name']}", f"{old_id} => {model['metadata']['uuid']}")

                else:
                    model["metadata"]["uuid"] = str(uuid.uuid4())
                    log("INFO", f"Adding temporary UUID to {model['name']}", f"{old_id} => {model['metadata']['uuid']}")
                    
            else:
                model["metadata"]["uuid"] = str(uuid.uuid4())
                log("INFO", f"Adding temporary UUID to {model['name']}", model["metadata"]["uuid"])

        else:
            model["metadata"]["uuid"] = str(uuid.uuid4())
            log("INFO", f"Adding temporary UUID to {model['name']}", model["metadata"]["uuid"])

    if not model.get("metadata", {}).get("schema"):
        schema_identifier = model_type.lower() + "::2.0"
        model["metadata"]["schema"] = model_type.lower() + "::2.0"
        log("INFO", "Adding schema identifier", f"{model['name']} => {schema_identifier}")

    
    if LEGACY_UUID_MAPPING:
        if old_ids:=model.get("threat", {}).get("actors"):
            updated_ids = []
            for old in old_ids:
                if old in LEGACY_UUID_MAPPING:
                    new_uuid = LEGACY_UUID_MAPPING[old]["uuid"]
                    updated_ids.append(new_uuid)
                    log("INFO",
                        f"Updated old ids in model {model['name']}",
                        f"field: threat.vectors , {old} => {new_uuid}")
                else:
                    updated_ids.append(old)
            model["threat"]["actors"] = updated_ids

        if old_ids:=model.get("detection", {}).get("vectors"):
            updated_ids = []
            for old in old_ids:
                if old in LEGACY_UUID_MAPPING:
                    new_uuid = LEGACY_UUID_MAPPING[old]["uuid"]
                    updated_ids.append(new_uuid)
                    log("INFO",
                        f"Updated old ids in model {model['name']}",
                        f"field: detection.vectors , {old} => {new_uuid}")
                else:
                    updated_ids.append(old)
            model["detection"]["vectors"] = updated_ids

        if old:=model.get("detection_model"):
            if old in LEGACY_UUID_MAPPING:
                new_uuid = LEGACY_UUID_MAPPING[old]["uuid"]
                log("INFO",
                    f"Updated old ids in model {model['name']}",
                    f"field: detection_model , {old} => {new_uuid}")

    return model


def indexer(write_index=False) -> dict:
    SKIPS = ["logsources", "ram", "mdrv2", "lookup_metadata"]
    RESOLVED_CONFIGURATIONS = resolve_configurations()

    TIDE_CONFIG = RESOLVED_CONFIGURATIONS["global"]

    DATA_FIELD = TIDE_CONFIG["data_fields"]

    RAW_TIDE_PATHS = TIDE_CONFIG["paths"]["tide"]
    RAW_CORE_PATHS = TIDE_CONFIG["paths"]["core"]
    RAW_PATHS = RAW_CORE_PATHS | RAW_TIDE_PATHS

    TIDE_PATHS, CORE_PATHS = resolve_paths(separate=True)
    PATHS = TIDE_PATHS | CORE_PATHS

    log("DEBUG", "Loaded all paths")
    VOCABULARIES_PATH = PATHS["vocabularies"]
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
    TIDE_INDEXES_PATH = PATHS["tide_indexes"]
    OUTPUT_PATH = PATHS["index_output"]


    # TODO Remove for public release
    # Makes backwards compatibility measures for OpenTIDE 1.0 down to index level
    try:
        LEGACY_UUID_MAPPING = json.load(open(TIDE_INDEXES_PATH / "legacy_uuid_mapping.json"))
        log("SUCCESS", "Found a legacy ID to UUID Mapping")
    except:
        log("SKIP", "Did not find a legacy id to uuid mapping")
        LEGACY_UUID_MAPPING = None
        pass
    # Controls whether the index should keep in memory or export to a file
    # In-memory is helpful when index is used to accelerate functions, like
    # for example to enrich deployment tags.

    index = dict()
    obj_counter = 0

    log("TITLE", "Tide Indexer")
    log("INFO", "Seeks all Tide related data and stores it for direct access")
    # Vocab Indexer

    log("INFO", "Resolving and indexing", "paths")
    index["paths"] = dict()
    index["paths"].update(PATHS)
    index["paths"]["tide"] = TIDE_PATHS
    index["paths"]["core"] = CORE_PATHS
    index["paths"]["raw"] = RAW_PATHS
    index["paths"]["raw"]["tide"] = RAW_TIDE_PATHS
    index["paths"]["raw"]["core"] = RAW_CORE_PATHS

    log("INFO", "Resolving and index", "configurations")
    # Config Indexer
    # Configurations resolve by merging the default Core configs
    # with custom ones defined in the user space

    index["configurations"] = RESOLVED_CONFIGURATIONS

    print("📒 Indexing Vocabularies...")

    # Data structures like the vocabularies, but need to be
    # indexed from different locations

    voc_index = dict()
    for voc_file in os.listdir(VOCABULARIES_PATH):
        obj_counter += 1

        voc_body = yaml.safe_load(open(VOCABULARIES_PATH / voc_file, encoding="utf-8"))

        if not voc_body:
            log("WARNING", "Could not find data in vocabulary/index", voc_file)
        else:
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
                if (not os.path.isdir(model_path)) and (str(model_path).endswith(".yaml")):
                    obj_counter += 1

                    if "[DEBUG]" not in model:
                        model_body = yaml.safe_load(open(model_path, encoding="utf-8"))
                        
                        #TODO Backward compatibility measure. To remove.
                        if LEGACY_UUID_MAPPING:
                            model_body = micro_patching_tide_1(LEGACY_UUID_MAPPING, model_body, meta_name)
                        
                        identifier = model_body.get("uuid") or model_body.get("metadata",{}).get("uuid")
                        if not identifier:
                            log("FATAL", "Missing identifier from model in file", model)
                        else:
                            model_cat_index[identifier] = model_body
            models_index[meta_name] = model_cat_index

    index["models"] = models_index

    # Tide Indexes retrieval (injected into )
    log("INFO", "Retrieving all Tide Indexes built on the Tide Instance",
        "Injected onto vocabulary index to be retrieved in generation jobs")
    
    if not os.path.exists(TIDE_INDEXES_PATH/"models.json"):
        log("SKIP", "Not able to find a models.json index in Tide instance",
            "Should be generated in the next Framework generation pipeline run")
    else:
        tide_model_index = json.load(open(TIDE_INDEXES_PATH/"models.json", encoding="utf-8"))

        if tide_model_index:
            if ("cdm" in tide_model_index) and ("bdr" in tide_model_index):
                log("INFO", "Appending BDR to CDM in Model index as options")
                tide_model_index["cdm"]["entries"].update(tide_model_index["bdr"]["entries"])
            index["vocabs"].update(tide_model_index)

    if not os.path.exists(TIDE_INDEXES_PATH/"reports.json"):
        log("SKIP", "Not able to find a reports.json index in Tide instance",
            "Should be generated in the next Framework generation pipeline run")
    else:
        tide_reports_index = json.load(open(TIDE_INDEXES_PATH/"reports.json", encoding="utf-8"))

        if tide_reports_index:
            index["vocabs"].update(tide_reports_index)
    
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
