import yaml
import os
import git
import re
from datetime import datetime
import sys
import traceback
from pathlib import Path
from typing import Literal


sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.deployment import system_scope, modified_mdr_files, Proxy
from Engines.modules.logging import log, Colors, tidemec_intro
from Engines.modules.tide import DataTide
from Engines.mutation import promotion
from Engines.modules.plugins import DeployTide


toolchain_start_time = datetime.now()
PRODUCTION_STATUS = DataTide.Configurations.Deployment.status["production"]
SAFE_STATUS = DataTide.Configurations.Deployment.status["safe"]
MDR_METADATA_LOOKUPS_CONFIG = DataTide.Configurations.Deployment.metadata_lookup

os.environ["INDEX_OUTPUT"] = "cache"

SUPPORTED_PLANS = ["STAGING", "PRODUCTION"]
DEPLOYMENT_PLAN = str(os.getenv("DEPLOYMENT_PLAN")) or ""
SYSTEMS_DEPLOYMENT = system_scope()

deployment_plan = {"splunk": ["701b9c83-15f9-411d-bf3f-d11597b62f8b"],
                   "sentinel": ["701b9c83-15f9-411d-bf3f-d11597b62f8b"],
                   "carbon_black_cloud": ["701b9c83-15f9-411d-bf3f-d11597b62f8b"]}


print(DeployTide.mdr)

exit()

if MDR_METADATA_LOOKUPS_CONFIG["enabled"]:
    deployment = []
    lookup_name = MDR_METADATA_LOOKUPS_CONFIG["name"]
    enabled_systems = MDR_METADATA_LOOKUPS_CONFIG["systems"]
    for system in deployment_plan:
        deployment.extend(deployment_plan[system])
    deployment = list(set(deployment))  # Dedup, since MDR can have multiple systems
    for system in enabled_systems:
        if system in DeployTide.metadata:
            DeployTide.metadata[system].deploy(
                deployment=deployment, lookup_name=lookup_name
            )
        else:
            log(
                "FATAL",
                f"Cannot find a deployment engine for the target system ",
                "Ensure there is an adequate plugin present in the Tide Instance",
            )
            raise (Exception("DEPLOYMENT ENGINE NOT FOUND"))

for system in deployment_plan:
    if system in DeployTide.mdr:
        log("ONGOING", "Deploying MDR for target system", system)
        DeployTide.mdr[system].deploy(deployment=deployment_plan[system])
    else:
        log(
            "FATAL",
            "Cannot find a deployement engine for the target system",
            "Ensure there is an adequate plugin present in the Tide Instance",
        )
        raise (Exception("DEPLOYMENT ENGINE NOT FOUND"))

print(Colors.GREEN + "Execution Report".center(80, "=") + Colors.STOP)

time_to_execute = datetime.now() - toolchain_start_time
time_to_execute = "%.2f" % time_to_execute.total_seconds()

log("INFO", "Completed deployment toolchain in", f"{time_to_execute} seconds")
