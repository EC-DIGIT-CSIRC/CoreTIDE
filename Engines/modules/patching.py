import os
import git
import json
import sys
import git
import uuid
from pprint import pprint

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.files import resolve_paths
from Engines.modules.logs import log

class Tide2Patching:
    """
    Class encapsulating all relevant behaviours to patch Tide 1 objects into Tide 2
    """
    def __init__(self):
        TIDE_PATHS, CORE_PATHS = resolve_paths(separate=True)
        PATHS = TIDE_PATHS | CORE_PATHS
        TIDE_INDEXES_PATH = PATHS["tide_indexes"]
        try:
            self.LEGACY_UUID_MAPPING = json.load(open(TIDE_INDEXES_PATH / "legacy_uuid_mapping.json"))
            log("SUCCESS", "Found a legacy ID to UUID Mapping")
        except:
            log("SKIP", "Did not find a legacy id to uuid mapping")
            self.LEGACY_UUID_MAPPING = None
            pass

    def tide_1_patch(self, model:dict, model_type:str)->dict:
        """
        Dynamic Micro-Patching on the fly object in staging with new UUIDs to pass validation.
        Once merged to main they will be migrated definitely.
        TODO - Remove before public release, as only concerns existing repositories
        """
        LEGACY_UUID_MAPPING = self.LEGACY_UUID_MAPPING
        
        if os.getenv("CI_COMMIT_REF_NAME") == "main":
            if os.getenv("DEPLOYMENT_PLAN") not in ["PRODUCTION", "STAGING"]:
                if model_type != "mdr": # Allowing this option for Staging MDR documentation patching
                    log("SKIP", "Not patching for validation, in main", model.get("name", ""))
                    return model

        if model.get("metadata", {}).get("schema"):
            log("SKIP",
                f"Schema identifier found : {model['metadata']['schema']}",
                f"Will not patch {model['name']}")
            return model

        log("ONGOING", f"Evaluating patching validation requirements for {model['name']}")

        if not model.get("metadata"):
            log("INFO", "Missing metadata section", "Transferring meta section to metadata")
            model["metadata"] = model.pop("meta")

        if not model.get("metadata", {}).get("schema"):
            schema_identifier = model_type.lower() + "::2.0"
            model["metadata"]["schema"] = model_type.lower() + "::2.0"
            log("INFO", "Adding schema identifier", f"{model['name']} => {schema_identifier}")
        
        if not model.get("metadata", {}).get("uuid"):
            if "uuid" in model:
                model["metadata"]["uuid"] = model.pop("uuid")
                log("INFO", f"Relocating UUID in {model['name']} to new location")
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
                    model["detection_model"] = new_uuid

        return model
