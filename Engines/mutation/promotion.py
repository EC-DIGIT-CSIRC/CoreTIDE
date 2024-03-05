import yaml
import os
import git
import sys
import toml
import ast

from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Engines.modules.logs import log
from Engines.modules.files import resolve_configurations, resolve_paths

ROOT = Path(str(git.Repo(".", search_parent_directories=True).working_dir))

CONFIGURATIONS = resolve_configurations()
PATHS = resolve_paths()

DEPLOYMENT_CONFIG = CONFIGURATIONS["deployment"]
PRODUCTION_STATUSES = DEPLOYMENT_CONFIG["status"]["production"]
PROMOTION_ENABLED = DEPLOYMENT_CONFIG["promotion"].get("enabled")
PROMOTION_TARGET = DEPLOYMENT_CONFIG["promotion"].get("promotion_target")
STATUS_VOCAB = yaml.safe_load(
    open(PATHS["vocabularies"] / "MDR Status.yaml", encoding="utf-8")
)
VALID_STATUSES = [k["id"] for k in STATUS_VOCAB["keys"]]

class PromoteMDR:
    """
    If enabled by config, dynamically re-assigns non-production statuses
    towards new targets
    """
    def edit_mdr_statuses(self, mdr_path:Path, status_to_promote:list):

        # We modify the file as text instead of loading and dumping the yaml
        # as formatting or comments are not always preserved, for small
        # modifications such as this one it's preferable to do in this way.

        with open(mdr_path, "r", encoding="utf-8") as file:
            buffer = []
            crossed = False
            for line in file:

                # Ensure that only data after crossing the configurations point is modified
                # in rare cases where the description contains some mentions of the status,
                # and may introduce confusion if mistakenly modified.
                if "configurations" in line:
                    crossed = True

                if crossed:
                    for word in status_to_promote:
                        if word in line:
                            line = line.replace(word, PROMOTION_TARGET)
                buffer.append(line)

        with open(mdr_path, "w", encoding="utf-8") as file:
            for line in buffer:
                file.write(line)

        log("SUCCESS", f"Successfully promoted MDR to {PROMOTION_TARGET}")


    def promote(self, deployment:list[Path]):
        log("TITLE", "MDR Status Promotion")
        log("INFO", "Promotes the status of modified MDR files according to configuration")

        if PROMOTION_ENABLED:

            if PROMOTION_TARGET not in VALID_STATUSES:
                log(
                    "FAILURE",
                    "The target status defined in the config is not a valid status",
                    PROMOTION_TARGET,
                    f"Valid statuses are in the MDR Status vocabulary file : {', '.join(VALID_STATUSES)}",
                )
                exit()

            if DEBUG:
                MDR_FOLDER = ROOT / PATHS["mdr"]
                deployment = [MDR_FOLDER / mdr for mdr in sorted(os.listdir(MDR_FOLDER))]

            else:
                # Fetch MDR in the deployment diff calculation
                  # Returns string expression into list object
                if not deployment:
                    log(
                        "SKIP",
                        "Found nothing to deploy in PRE_DEPLOYMENT environment variable",
                    )
                    return

            for mdr in deployment:
                system_promotion = {}
                data = yaml.safe_load(open(mdr, encoding="utf-8"))
                mdr_name = data["name"]

                for system in (conf := data["configurations"]):
                    system_status = conf[system]["status"]

                    if system_status not in PRODUCTION_STATUSES:
                        system_promotion[system] = system_status

                if not system_promotion:
                    log("SKIP", "Nothing to promote, MDR already in Production status", mdr_name)
                else:
                    log(
                        "INFO",
                        "Detected statuses needing promotion for the following MDR",
                        mdr_name,
                    )
                    log(
                        "ONGOING",
                        "Promoting the following systems statuses",
                        ", ".join(
                            f"{key} : {value}" for key, value in system_promotion.items()
                        ),
                    )
                    statuses_to_replace = [system_promotion[s] for s in system_promotion]
                    self.edit_mdr_statuses(mdr, statuses_to_replace)

        else:
            log(
                "SKIP",
                "MDR Promotion disabled in config",
                advice="You can enable MDR Promotion under config>deployment>status>promotion",
            )

