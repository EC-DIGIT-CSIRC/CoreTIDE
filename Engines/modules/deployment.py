import sys
import os
import git
from git.repo import Repo
import re
from typing import Literal
from pathlib import Path

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logs import log
from Engines.modules.tide import DataTide


SYSTEMS_CONFIGS_INDEX = DataTide.Configurations.Systems.Index


def fetch_config_envvar(config_secrets: dict) -> dict:
    # Replace placeholder variables with environment
    for sec in config_secrets.copy():
        if type(config_secrets[sec]) == str:
            if config_secrets[sec][0] == "$":
                if config_secrets[sec].removeprefix("$") in os.environ:
                    env_variable = str(config_secrets.pop(sec)).removeprefix("$")
                    config_secrets[sec] = os.environ.get(env_variable)
                    log("SUCCESS", "Fetched environment secret", env_variable)
                else:
                    log(
                        "FATAL",
                        "Could not find expected environment variable",
                        config_secrets[sec],
                        "Review configuration file and execution environment",
                    )

    return config_secrets


def modified_mdr_files(stage: Literal["STAGING", "PRODUCTION"])->list[Path]:

    MDR_PATH = DataTide.Configurations.Global.Paths.Tide.mdr
    MDR_PATH_RAW = DataTide.Configurations.Global.Paths.Tide._raw["mdr"]
    MDR_PATH_RAW = MDR_PATH_RAW.replace(r"/", r"\/")

    mdr_path_regex = (
        rf"^.*{MDR_PATH_RAW}[^\/]+(\.yaml|\.yml)$"
    )
    mdr_files = [
        mdr for mdr in diff_calculation(stage) if re.match(mdr_path_regex, mdr)
    ]

    mdr_files = [(MDR_PATH / f) for f in mdr_files]
    log("INFO", "Computed modified MDR Files", str(mdr_files))
    return mdr_files


def diff_calculation(stage: Literal["STAGING", "PRODUCTION"]) -> list:
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

    if stage == "PRODUCTION":
        SOURCE = os.getenv("CI_COMMIT_BEFORE_SHA")
    elif stage == "STAGING":
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
        log("ONGOING", "Setting environment proxy according to CI variables")
        PROXY_CONFIG = DataTide.Configurations.Deployment.proxy

        if (
            os.environ.get("DEBUG") == True
            or os.environ.get("TERM_PROGRAM") == "vscode"
        ):
            pass
        else:
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
                os.environ["http_proxy"] = proxy
                os.environ["https_proxy"] = proxy
                log("SUCCESS", "Proxy environment setup successful")
            else:
                log(
                    "FAILURE",
                    "Could not retrieve all proxy information",
                    "Control that all proxy infos are entered in CI variables",
                )

    @staticmethod
    def unset_proxy():
        os.environ["http_proxy"] = ""
        os.environ["https_proxy"] = ""
        log("INFO", "Resetting proxy setup")
