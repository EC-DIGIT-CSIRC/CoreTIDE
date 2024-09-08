import json
from pathlib import Path
import os
import git
import toml
from datetime import datetime
import sys

toolchain_start_time = datetime.now()

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logs import log

ROOT = Path(str(git.Repo(".", search_parent_directories=True).working_dir))
TIDE_CONFIG = toml.load(
    open(ROOT / "Configurations/global.toml", encoding="utf-8")
)

PROJECT_NAME = os.getenv("CI_PROJECT_NAME")
STG_INDEX_PATH = ROOT / TIDE_CONFIG["paths"]["tide"]["staging_index_output"]

MAPPING_PATH = ROOT / TIDE_CONFIG["paths"]["core"]["tide_indexes"]
MAPPING = json.load(open(MAPPING_PATH/"legacy_uuid_mapping.json"))
STAGING_INDEX = json.load(open(STG_INDEX_PATH))

for mdr in STAGING_INDEX:
    if old_id:=mdr.get("detection_model"):
        new_uuid = MAPPING[old_id]["uuid"]
        log("ONGOING", "Updating old ID in Staging index", f"{old_id} => {new_uuid}")
        mdr["detection_model"] = new_uuid
with open(STG_INDEX_PATH, "w+") as out:
    json.dump(STAGING_INDEX, out, default=str)
    log("SUCCESS", "Updated staging index with new uuid")