import yaml
import os
import git
import re
from datetime import datetime
import sys
import traceback
from pathlib import Path
from typing import Literal, Tuple


sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.deployment import enabled_systems, modified_mdr_files, Proxy
from Engines.modules.logs import log, Colors, tidemec_intro
from Engines.modules.tide import DataTide, IndexTide
from Engines.mutation.promotion import PromoteMDR


toolchain_start_time = datetime.now()
PRODUCTION_STATUS = DataTide.Configurations.Deployment.status["production"]
SAFE_STATUS = DataTide.Configurations.Deployment.status["safe"]
MDR_METADATA_LOOKUPS_CONFIG = DataTide.Configurations.Deployment.metadata_lookup

os.environ["INDEX_OUTPUT"] = "cache"

SUPPORTED_PLANS = ["STAGING", "PRODUCTION"]
DEPLOYMENT_PLAN = str(os.getenv("DEPLOYMENT_PLAN")) or ""
SYSTEMS_DEPLOYMENT = enabled_systems()

print(tidemec_intro())

torrent = rf"""
{Colors.ORANGE}
 __________  ___  ___  _____  ________  
/_  __/ __ \/ _ \/ _ \/ __/ |/ /_  __/  
 / / / /_/ / , _/ , _/ _//    / / /     
/_/  \____/_/|_/_/|_/___/_/|_/ /_/      
{Colors.BLUE}{Colors.ITALICS}{Colors.BOLD}TIDeMEC MDR Deployment Orchestration
{Colors.STOP}
"""

print(torrent)


def make_deploy_plan(
    plan: Literal["STAGING", "PRODUCTION"]
) -> dict[str, list[str]]:

    log("INFO", "Compiling MDRs to deploy in plan", plan)
    mdr_files = list()
    deploy_mdr = dict()

    if plan == "FULL":
        MDR_PATH = Path(DataTide.Configurations.Global.Paths.Tide.mdr)
        mdr_files = [MDR_PATH / mdr for mdr in os.listdir(MDR_PATH)]
        log(
            "ONGOING",
            "Redeploying complete MDR library",
            f"[{len(mdr_files)} MDR] are in scope",
        )

    else:
        mdr_files = modified_mdr_files(plan)

    for rule in mdr_files:
        data = yaml.safe_load(open(rule, encoding="utf-8"))
        name = data["name"]
        conf_data = data["configurations"]
        mdr_uuid = data["uuid"]

        for system in conf_data:
            platform_status = conf_data[system]["status"]

            if system in SYSTEMS_DEPLOYMENT:
                if plan == "PRODUCTION":
                    if platform_status in PRODUCTION_STATUS:
                        deploy_mdr.setdefault(system, []).append(mdr_uuid)
                        log(
                            "SUCCESS",
                            f"[{system.upper()}][{platform_status}] Identified MDR to deploy in {plan}",
                            name,
                        )
                    else:
                        log(
                            "WARNING",
                            f"[{system.upper()}][{platform_status}] Skipping as cannot be deployed in {plan}",
                            name,
                        )

                elif plan == "STAGING":
                    if (
                        platform_status not in PRODUCTION_STATUS
                        and platform_status not in SAFE_STATUS
                    ):
                        deploy_mdr.setdefault(system, []).append(mdr_uuid)
                        log(
                            "SUCCESS",
                            f"[{system.upper()}][{platform_status}] Identified MDR to deploy in {plan}",
                            name,
                        )
                    else:
                        log(
                            "WARNING",
                            f"[{system.upper()}][{platform_status}] Skipping as cannot be deployed in {plan}",
                            name,
                        )

            else:
                log(
                    "FAILURE",
                    f"[{system.upper()}] is disabled and cannot be deployed to for",
                    name,
                )

    return deploy_mdr


if not DEPLOYMENT_PLAN:
    log(
        "FATAL",
        "No deployment plan, ensure that the CI variable DEPLOYMENT_PLAN is set correctly",
    )
    raise Exception("NO DEPLOYMENT PLAN")

if DEPLOYMENT_PLAN not in SUPPORTED_PLANS:
    log(
        "FATAL",
        "The following deployment plan is not supported",
        DEPLOYMENT_PLAN,
        f"Supported plan : {SUPPORTED_PLANS}",
    )
    raise AttributeError("UNSUPPORTED DEPLOYMENT PLAN")



# Status promotion, happening before the main deployment loop
if DEPLOYMENT_PLAN == "PRODUCTION":
    pre_deployment = modified_mdr_files(DEPLOYMENT_PLAN)
    log("TITLE", "Pre-deployment Routine")
    PromoteMDR().promote(pre_deployment)


# Refetches the deployment plan, so it can read the MDR after modification
# and assess the correct latest status
deployment_list = make_deploy_plan(DEPLOYMENT_PLAN)  # type: ignore

if len(deployment_list) == 0:  # In case of no deployments possible, fail graciously
    log(
        "WARNING",
        "Nothing could deploy, no MDR can be addressed within this deployment context",
    )
    traceback.print_exc()
    sys.exit(19)

# Need reindexation after MDR promotion is complete.
IndexTide.reload()

# Need to import later so DataTide has been correctly
# Refreshed post-promotion, and thus can correctly set
# global modules variables.
from Engines.modules.plugins import DeployTide

if MDR_METADATA_LOOKUPS_CONFIG["enabled"]:
    log("TITLE", "MDR Metadata Deployment")
    log("INFO", "Continuously update a lookup with the MDR Data as they deploy")
    deployment = []
    lookup_name = MDR_METADATA_LOOKUPS_CONFIG["name"]
    enabled_systems = MDR_METADATA_LOOKUPS_CONFIG["systems"]
    for system in deployment_list:
        deployment.extend(deployment_list[system])
    deployment = list(set(deployment))  # Dedup, since MDR can have multiple systems
    for system in enabled_systems:
        if system in DeployTide.metadata:
            log("ONGOING", "Deploying metadata on system", system)
            DeployTide.metadata[system].deploy(
                deployment=deployment, lookup_name=lookup_name
            )
        else:
            log(
                "FATAL",
                f"Cannot find a deployement engine for the target system {system}",
                "Ensure there is an adequate plugin present in the Tide Instance",
            )
            raise (Exception("METADATA DEPLOYMENT ENGINE NOT FOUND"))

for system in deployment_list:
    log("TITLE", "MDR Deployment")
    log(
        "INFO",
        "Deploy MDR onto the system they target, if allowed at the instance level and deployment context",
    )

    if system in DeployTide.mdr:
        log("ONGOING", "Deploying MDR for target system", system)
        DeployTide.mdr[system].deploy(deployment=deployment_list[system])
    else:
        log(
            "FATAL",
            f"Cannot find a deployement engine for the target system {system}",
            "Ensure there is an adequate plugin present in the Tide Instance",
        )
        raise (Exception("DEPLOYMENT ENGINE NOT FOUND"))

print(Colors.GREEN + "Execution Report".center(80, "=") + Colors.STOP)

time_to_execute = datetime.now() - toolchain_start_time
time_to_execute = "%.2f" % time_to_execute.total_seconds()

log("INFO", "Completed deployment toolchain in", f"{time_to_execute} seconds")