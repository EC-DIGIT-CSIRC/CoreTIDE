import sys
import os
import git
import yaml
import re
from typing import Any
from enum import Enum, auto
from pathlib import Path
from dataclasses import dataclass

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logs import log
from Engines.modules.tide import DataTide
from Engines.modules.debug import DebugEnvironment

from git.repo import Repo

SYSTEMS_CONFIGS_INDEX = DataTide.Configurations.Systems.Index
PRODUCTION_STATUS = DataTide.Configurations.Deployment.status["production"]
SAFE_STATUS = DataTide.Configurations.Deployment.status["safe"]

@dataclass
class DeploymentPlans(Enum):
    STAGING = auto()
    PRODUCTION = auto()
    FULL = auto()

    @staticmethod
    def load_from_environment():
        """
        Read the DEPLOYMENT_PLAN environment variable and maps it to 
        DeploymentPlans valid values. In case of an illegal value, 
        or missing environment variable will raise an exception
        """
        SUPPORTED_PLANS = [plan.name for plan in DeploymentPlans]
        DEPLOYMENT_PLAN = str(os.getenv("DEPLOYMENT_PLAN")) or None
        if not DEPLOYMENT_PLAN:
            log(
                "FATAL",
                "No deployment plan, ensure that the CI variable DEPLOYMENT_PLAN is set correctly",
            )
            raise Exception("NO DEPLOYMENT PLAN")

        try:
            DEPLOYMENT_PLAN = DeploymentPlans[DEPLOYMENT_PLAN]
        except:

                log(
                    "FATAL",
                    "The following deployment plan is not supported",
                    DEPLOYMENT_PLAN,
                    f"Supported plan : {SUPPORTED_PLANS}",
                )
                raise AttributeError("UNSUPPORTED DEPLOYMENT PLAN")

        return DEPLOYMENT_PLAN

def make_deploy_plan(
    plan: DeploymentPlans,
    wide_scope = False
) -> dict[str, list[str]]:
    """
    Algorithm which assembles the MDR to deploy, organized per system

    plan: Execution environment used to calculate the acceptable statuses
    wide_scope: If set to true, will return all statuses regardless of the plan.
    
    plan is still required if wide_scope is set to True as it configures the calculation
    algorithm behaviour. wide_scope is useful to validate all MDR regardless of statuses if
    using the deploy plan to calculate the MDR that were modified. 
    """
    
    SYSTEMS_DEPLOYMENT = enabled_systems()

    log("INFO", "Compiling MDRs to deploy in plan", plan.name)
    if wide_scope:
        log("WARNING", "Wide Scope has been enabled for the deployment plan calculation",
        "This will assemble the plan with no consideration for statuses. Use with caution.")

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
        mdr_uuid = data.get("uuid") or data["metadata"]["uuid"]

        for system in conf_data:
            platform_status = conf_data[system]["status"]

            if system in SYSTEMS_DEPLOYMENT:
                if wide_scope:
                    deploy_mdr.setdefault(system, []).append(mdr_uuid)
                else:
                    if plan is DeploymentPlans.PRODUCTION:
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

                    elif plan is DeploymentPlans.STAGING:
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

def fetch_config_envvar(config_secrets: dict[str,str]) -> dict[str, Any]:
    # Replace placeholder variables with environment

    #Allows to print all errors at once before raising exception
    missing_envvar_error = False
    for sec in config_secrets.copy():
        if not config_secrets[sec]:
            log("SKIP", "Did not found an entry for", sec,
                "If there are deployment issue, review if it is relevant to configure")
            continue
        if type(config_secrets[sec]) == str:
            if config_secrets[sec].startswith("$"):
                if config_secrets[sec].removeprefix("$") in os.environ:
                    env_variable = str(config_secrets.pop(sec)).removeprefix("$")
                    config_secrets[sec] = os.environ.get(env_variable, "")
                    log("SUCCESS", "Fetched environment secret", env_variable)
                else:
                    if DebugEnvironment.ENABLED:
                        log("SKIP", 
                            "Could not find expected environment variable",
                            config_secrets[sec],
                            "Debug Mode identified, continuing - remember that this may break some deployments")
                    else:
                        log(
                            "FATAL",
                            "Could not find expected environment variable",
                            config_secrets[sec],
                            "Review configuration file and execution environment",
                        )
                        missing_envvar_error = True

    if missing_envvar_error:
        log("FATAL",
            "Some environment variable specified in configuration files were not found",
            "Review the previous errors to find which ones were missing",
            "Check your CI settings to ensure these environment variables are properly injected")
        raise KeyError

    return config_secrets


def modified_mdr_files(plan: DeploymentPlans)->list[Path]:

    MDR_PATH = Path(DataTide.Configurations.Global.Paths.Tide.mdr)
    MDR_PATH_RAW = DataTide.Configurations.Global.Paths.Tide._raw["mdr"]
    MDR_PATH_RAW = MDR_PATH_RAW.replace(r"/", r"\/")

    mdr_path_regex = (
        rf"^.*{MDR_PATH_RAW}[^\/]+(\.yaml|\.yml)$"
    )
    mdr_files = [
        mdr.split("/")[-1] for mdr in diff_calculation(plan) if re.match(mdr_path_regex, mdr)
    ]
    #Extracting only the file name so it can be appended to MDR_PATH
    # which is absolute, and thus more reliable

    mdr_files = [(MDR_PATH / f) for f in mdr_files]
    log("INFO", "Computed modified MDR Files", str(mdr_files))
    return mdr_files


def diff_calculation(plan: DeploymentPlans) -> list:
    """
    Calculates the files in scope of deployment based on the execution context.
    
    Limitation: Tied to certain Gitlab CI variables, need more separation
    to work in other environments

    In a Merge Request, the calculation will take in consideration
    the root of the MR and tip of the branch. In a direct commit to main, it will
    instead take the difference between the two last commits.

    stage: used to filter the paths computed

    """
    scope = list()

    REPO_DIR = os.getenv("CI_PROJECT_DIR")
    repo = Repo(REPO_DIR, search_parent_directories=True)

    TARGET = os.getenv("CI_COMMIT_SHA")

    if plan is DeploymentPlans.PRODUCTION:
        SOURCE = os.getenv("CI_COMMIT_BEFORE_SHA")
    elif plan is DeploymentPlans.STAGING:
        SOURCE = os.getenv("CI_MERGE_REQUEST_DIFF_BASE_SHA")
        if os.getenv("CI_MERGE_REQUEST_EVENT_TYPE") == "merged_result":
            log("INFO", "Currently running a diff calculation for merge results")
            for commit in repo.iter_commits():
                if commit.hexsha == os.getenv("CI_COMMIT_BEFORE_SHA"):
                    mr_correct_parent = commit.parents[1]
                    log(
                        "INFO",
                        "Current evaluating commit and found parent",
                        f"{commit.hexsha} | {commit.message}",
                        str(mr_correct_parent),
                    )
                    TARGET = mr_correct_parent
                    break
    else:
        log("FATAL", f"Illegal Deployment Plan {str(plan)} passed to diff_calculation algorithm")
        raise KeyError
    log(
        "INFO",
        "Setting source and target commit for the diff calculation to",
        f"{SOURCE} | {TARGET}",
    )

    source_commit = None
    try:
        source_commit = repo.commit(SOURCE)
    except Exception:
        log(
            "INFO",
            "Could not find source commit in current branch, trying iter_commits method",
        )
        remote_refs = repo.remote().refs

        for refs in remote_refs:
            log("INFO", refs.name)

        for commit in repo.iter_commits("origin/main"):
            log("INFO", "Currently Evaluating", f"{commit.message}")
            if commit.hexsha == SOURCE:
                source_commit = commit
                log(
                    "SUCCESS",
                    "Found source commit",
                    f"{commit.hexsha} | {commit.message}",
                )
                break

    if not source_commit:
        log("FATAL", "No Source Commit could be identified")
        raise Exception("No Source Commit Found")

    target_commit = repo.commit(TARGET)
    diff = source_commit.diff(target_commit)

    log(
        "DEBUG",
        "Preliminary diff calculation completed, returned with",
        ", ".join([f.b_path for f in diff]),
    )

    # Computing diff for added/renamed paths and modified files.
    # Deleted files are explicitely excluded to avoid attempting to deploy
    # something that is not material anymore.
    added_files = [f.b_path for f in diff.iter_change_type("A")]
    renamed_files = [f.b_path for f in diff.iter_change_type("R")]
    modified_files = [f.b_path for f in diff.iter_change_type("M")]

    scope = added_files + renamed_files + modified_files
    scope = list(set(scope)) #De-duplicate - may happen if file modified and renamed, for example
    log("INFO", "Computed diff scope", ", ".join(scope))

    return scope


def enabled_lookup_systems() -> list[str]:
    enabled_lookup_systems = list()
    for system in SYSTEMS_CONFIGS_INDEX:
        if SYSTEMS_CONFIGS_INDEX[system].get("lookups", {}).get("enabled") is True:
            enabled_lookup_systems.append(system)

    return enabled_lookup_systems


def enabled_systems() -> list[str]:
    enabled_systems = list()
    for system in SYSTEMS_CONFIGS_INDEX:
        if SYSTEMS_CONFIGS_INDEX[system]["tide"].get("enabled") is True:
            enabled_systems.append(system)

    return enabled_systems


class Proxy:
    """
    Simple class to encapulate configuring the proxy in
    environment variables
    """

    @staticmethod
    def set_proxy():
        if DebugEnvironment.ENABLED and not DebugEnvironment.PROXY_ENABLED:
            pass
        else:
            log("ONGOING", "Setting environment proxy according to CI variables")
            PROXY_CONFIG = DataTide.Configurations.Deployment.proxy
            PROXY_CONFIG = fetch_config_envvar(PROXY_CONFIG)
            proxy_user = PROXY_CONFIG["proxy_user"]
            proxy_pass = PROXY_CONFIG["proxy_password"]
            proxy_host = PROXY_CONFIG["proxy_host"]
            proxy_port = PROXY_CONFIG["proxy_port"]
            if proxy_host and proxy_port and proxy_user and proxy_pass:
                proxy = (
                    "http://"
                    + proxy_user
                    + ":"
                    + proxy_pass
                    + "@"
                    + proxy_host
                    + ":"
                    + str(proxy_port)
                )
                os.environ["HTTP_PROXY"] = proxy
                os.environ["HTTPS_PROXY"] = proxy
                log("SUCCESS", "Proxy environment setup successful")
            else:
                log(
                    "FAILURE",
                    "Could not retrieve all proxy information",
                    "Control that all proxy infos are entered in CI variables",
                )

    @staticmethod
    def unset_proxy():
        os.environ["HTTP_PROXY"] = ""
        os.environ["HTTPS_PROXY"] = ""
        log("INFO", "Resetting proxy setup")
