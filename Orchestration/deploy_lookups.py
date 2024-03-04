import os
import git
import re
from datetime import datetime
import sys
import traceback
from pathlib import Path


sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.deployment import enabled_systems, enabled_lookup_systems, diff_calculation
from Engines.modules.logs import log, Colors, tidemec_intro
from Engines.modules.tide import DataTide
from Engines.modules.plugins import DeployTide

toolchain_start_time = datetime.now()

print(tidemec_intro())

floodcurrent = rf"""
{Colors.ORANGE}
   ______   ____  ____  ___  _______  _____  ___  _____  ________
  / __/ /  / __ \/ __ \/ _ \/ ___/ / / / _ \/ _ \/ __/ |/ /_  __/
 / _// /__/ /_/ / /_/ / // / /__/ /_/ / , _/ , _/ _//    / / /   
/_/ /____/\____/\____/____/\___/\____/_/|_/_/|_/___/_/|_/ /_/    
{Colors.BLUE}{Colors.ITALICS}{Colors.BOLD}TIDeMEC Managed Lookups Deployment Orchestration 
{Colors.STOP}
"""

print(floodcurrent)

DEBUG = os.environ.get("DEBUG")
if DEBUG:
    log(
        "DEBUG",
        "Deployment set to debug",
        "Will only target lookup files starting with DEBUG",
    )

SYSTEMS_DEPLOYMENT = enabled_systems()

LOOKUPS_DEPLOYMENT = [s for s in enabled_lookup_systems() if s in SYSTEMS_DEPLOYMENT]
log("DEBUG", "Current systems enabled : ", ",".join(SYSTEMS_DEPLOYMENT))
log("DEBUG", "Current lookups enabled : ", ",".join(LOOKUPS_DEPLOYMENT))

REPO_DIR = os.getenv("CI_PROJECT_DIR") or "./"
JOB_NAME = os.getenv("CI_JOB_NAME")

# We always assume a production deployment for lookups by default
DEPLOYMENT_PLAN = os.getenv("DEPLOYMENT_PLAN") or "PRODUCTION"


def lookup_deployment_plan(plan: str) -> dict:

    lookup_paths = list()
    deploy_lookups = dict()

    if plan == "FULL":
        LOOKUP_PATH = Path(DataTide.Configurations.Global.Paths.Tide.lookups)
        for system in os.listdir(LOOKUP_PATH):
            for lookup in os.listdir(LOOKUP_PATH / system):
                if lookup.endswith(".csv"):
                    lookup_paths.append(REPO_DIR / LOOKUP_PATH / system / lookup)
        log(
            "ONGOING",
            "Redeploying complete Lookups library",
            f"[{len(lookup_paths)} Lookups] are in preliminary scope",
        )

    else:
        lookups_path_regex = r"^.*/Lookups\/[^\/]+\/[^\/]+\.csv$"
        lookup_paths = [
            lookup
            for lookup in diff_calculation("PRODUCTION")
            if re.match(lookups_path_regex, lookup)
        ]

    for lookup in lookup_paths:
        lookup_file = str(lookup.rsplit("/")[-1]).removesuffix("csv")
        lookup_target_system = str(lookup.rsplit("/")[-2]).lower()

        if (DEBUG and lookup_file.startswith("DEBUG")) or (
            not DEBUG and not lookup_file.startswith("DEBUG")
        ):
            if lookup_target_system in LOOKUPS_DEPLOYMENT:
                deploy_lookups.setdefault(lookup_target_system, [])
                deploy_lookups[lookup_target_system].append(lookup_file)
                log(
                    "SUCCESS",
                    f"[{lookup_target_system.upper()}] Identified lookup for deployment",
                    lookup_file,
                    icon="📄",
                )

            elif lookup_target_system == "Global":
                log(
                    "INFO",
                    "Lookup identified to be global, will be added to"
                    "deployment plan of every enabled system",
                    lookup_file,
                    icon="🌐",
                )
                for system in LOOKUPS_DEPLOYMENT:
                    deploy_lookups.setdefault(system, [])
                    deploy_lookups[system].append(lookup)
                    log(
                        "SUCCESS",
                        f"[{system.upper()}] Identified lookup for deployment",
                        lookup_file,
                        icon="📄",
                    )
            else:
                log(
                    "WARNING",
                    f"[{lookup_target_system.upper()}] detected modifications to the"
                    "lookup but won't deploy as is not in scope",
                    lookup_file,
                    "Enable the target system in config.yaml",
                    "🛑",
                )
        else:
            log(
                "DEBUG",
                "The following lookup modification does not match current DEBUG status",
                lookup_file,
            )

    return deploy_lookups


lookup_deployment = lookup_deployment_plan(DEPLOYMENT_PLAN)
if not lookup_deployment:  # In case of no deployments possible
    try:
        log(
            "FATAL",
            "Nothing could deploy, no MDR can be addressed within this deployment context",
        )
        raise Exception("NO_DEPLOYMENT_FOUND")
    except:
        traceback.print_exc()
        sys.exit(19)


for system in lookup_deployment:
    if system in DeployTide.lookups:
        log("ONGOING", "Deploying MDR for target system", system)
        DeployTide.lookups[system].deploy(deployment=lookup_deployment[system])
    else:
        log(
            "FATAL",
            "Cannot find a deployement engine for the target system",
            "Ensure there is an adequate plugin present in the Tide Instance",
        )
        raise (Exception("LOOKUP DEPLOYMENT ENGINE NOT FOUND"))


print(Colors.GREEN + "Execution Report".center(80, "=") + Colors.STOP)

time_to_execute = datetime.now() - toolchain_start_time
time_to_execute = "%.2f" % time_to_execute.total_seconds()

log("INFO", "Completed deployment toolchain in", f"{time_to_execute} seconds")
