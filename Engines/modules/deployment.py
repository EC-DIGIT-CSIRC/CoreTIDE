import sys
import os
import git
import yaml
import re
from typing import MutableMapping, Sequence, overload, Literal
from enum import Enum, auto
from pathlib import Path
from dataclasses import asdict


sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logs import log
from Engines.modules.tide import DataTide, HelperTide
from Engines.modules.debug import DebugEnvironment
from Engines.modules.errors import TideErrors
from Engines.modules.tide import DataTide, DetectionSystems, TideLoader
from Engines.modules.models import (TideConfigs,
                                    TideDefinitionsModels,
                                    TideModels,
                                    SystemConfig,
                                    DeploymentStrategy,
                                    TenantDeployment,
                                    TenantDeploymentModel) 
from Engines.modules.framework import unroll_dot_dict

from git.repo import Repo

import pandas as pd

SYSTEMS_CONFIGS_INDEX = DataTide.Configurations.Systems.Index
PRODUCTION_STATUS = DataTide.Configurations.Deployment.status["production"]
SAFE_STATUS = DataTide.Configurations.Deployment.status["safe"]


def make_deploy_plan(
    plan: DeploymentStrategy,
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
                    if plan is DeploymentStrategy.PRODUCTION:
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

                    elif plan is DeploymentStrategy.STAGING:
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



def modified_mdr_files(plan: DeploymentStrategy)->list[Path]:

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


def diff_calculation(plan: DeploymentStrategy) -> list:
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

    if plan is DeploymentStrategy.PRODUCTION:
        SOURCE = os.getenv("CI_COMMIT_BEFORE_SHA")
    elif plan is DeploymentStrategy.STAGING:
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
        try:
            if SYSTEMS_CONFIGS_INDEX[system]["tide"].get("enabled") is True:
                enabled_systems.append(system)
        except:
            if SYSTEMS_CONFIGS_INDEX[system]["platform"].get("enabled") is True:
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
            PROXY_CONFIG = HelperTide.fetch_config_envvar(PROXY_CONFIG)
            proxy_user = PROXY_CONFIG["proxy_user"]
            proxy_pass = PROXY_CONFIG["proxy_password"]
            proxy_host = PROXY_CONFIG["proxy_host"]
            proxy_port = PROXY_CONFIG["proxy_port"]
            if proxy_host and proxy_port and proxy_user and proxy_pass:
                proxy = (f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}")
                os.environ["HTTP_PROXY"] = proxy
                os.environ["HTTPS_PROXY"] = proxy
                log("SUCCESS", "Proxy environment setup successful")
            else:
                log(
                    "FAILURE",
                    "Could not retrieve all proxy information",
                    "Control that all proxy infos are entered in CI variables",
                    "Expects proxy_user, proxy_password, proxy_host and proxy_port"
                )

    @staticmethod
    def unset_proxy():
        os.environ["HTTP_PROXY"] = ""
        os.environ["HTTPS_PROXY"] = ""
        log("INFO", "Resetting proxy setup")


class ExternalIdHelper:
    """
    Utility class to help processing external rule IDs in MDR Files
    """

    @staticmethod
    def remove_id(rule_id:int, tenant_name:str, mdr_uuid:str):
        """
        Removes an existing external ID. Mostly used in rule deletion workflows
        """
        file_path = DataTide.Configurations.Global.Paths.Tide.mdr / DataTide.Models.files[mdr_uuid]
        with open(file_path, "r", encoding="utf-8") as mdr_file:
            content = mdr_file.readlines()

        updated_content = list()

        #Remove previous rule ID from file
        for line in content:
            if line.strip() != f"rule_id::{tenant_name}: {rule_id}":
                updated_content.append(line)

        with open(file_path, "w", encoding="utf-8") as mdr_file:
            log("SUCCESS",
            f"Removed ID in MDR File for tenant {tenant_name}")
            mdr_file.writelines(updated_content)

    @staticmethod
    def insert_id(rule_id:int, tenant_name:str, mdr_uuid:str, system_name:str):
        """
        Adds a new rule_id::<tenant>::<id> key to store IDs generated by the target system
        """
        file_path = DataTide.Configurations.Global.Paths.Tide.mdr / DataTide.Models.files[mdr_uuid]
        with open(file_path, "r", encoding="utf-8") as mdr_file:
            content = mdr_file.readlines()

        updated_content = list()
        for line in content:
            if line.strip().removesuffix(":").strip() == system_name:
                updated_content.append(line)
                updated_content.append(f"    rule_id::{tenant_name}: {rule_id}\n")
            else:
                updated_content.append(line)

        with open(file_path, "w", encoding="utf-8") as mdr_file:
            mdr_file.writelines(updated_content)
            log("SUCCESS",
            f"Updated MDR File with new ID for tenant {tenant_name}",
            str(rule_id))


class TideDeployment:

    def __init__(self, deployment, system:DetectionSystems, strategy):
        
        match system:
            case DetectionSystems.SPLUNK:
                self.rule_deployment:Sequence[TenantDeployment.Splunk] = self.deployment_resolver(deployment, DetectionSystems.SPLUNK, strategy) #type:ignore
            case DetectionSystems.SENTINEL:
                self.rule_deployment:Sequence[TenantDeployment.Sentinel] = self.deployment_resolver(deployment, DetectionSystems.SENTINEL, strategy) #type:ignore
            case DetectionSystems.CARBON_BLACK_CLOUD:
                self.rule_deployment:Sequence[TenantDeployment.CarbonBlackCloud] = self.deployment_resolver(deployment, DetectionSystems.CARBON_BLACK_CLOUD, strategy) #type:ignore
            case DetectionSystems.DEFENDER_FOR_ENDPOINT:
                self.rule_deployment:Sequence[TenantDeployment.DefenderForEndpoint] = self.deployment_resolver(deployment, DetectionSystems.DEFENDER_FOR_ENDPOINT, strategy) #type:ignore
            case DetectionSystems.SENTINEL_ONE:
                self.rule_deployment:Sequence[TenantDeployment.SentinelOne] = self.deployment_resolver(deployment, DetectionSystems.SENTINEL_ONE, strategy) #type:ignore


    def system_configuration_resolver(self, system:DetectionSystems): #type:ignore
        match system:
            #case DetectionSystems.SPLUNK:
            #    return DataTide.Configurations.Systems.Splunk
            #case DetectionSystems.SENTINEL:
            #    return DataTide.Configurations.Systems.Sentinel
            #case DetectionSystems.CARBON_BLACK_CLOUD:
            #    return DataTide.Configurations.Systems.CarbonBlackCloud
            case DetectionSystems.DEFENDER_FOR_ENDPOINT:
                log("DEBUG", str(DataTide.Configurations.Systems.DefenderForEndpoint.raw))
                log("DEBUG", str(DataTide.Configurations.Systems.DefenderForEndpoint.modifiers))
                return DataTide.Configurations.Systems.DefenderForEndpoint
            case DetectionSystems.SENTINEL_ONE:
                log("DEBUG", str(DataTide.Configurations.Systems.SentinelOne.raw))
                log("DEBUG", str(DataTide.Configurations.Systems.SentinelOne.modifiers))
                return DataTide.Configurations.Systems.SentinelOne

            #case _:
            #    raise NotImplemented
        


    def mdr_configuration_resolver(self, data:TideModels.MDR, system:DetectionSystems)->TideDefinitionsModels.SystemConfigurationModel:

        match system:
            case DetectionSystems.DEFENDER_FOR_ENDPOINT:
                mdr_config = data.configurations.defender_for_endpoint
            case DetectionSystems.SENTINEL_ONE:
                mdr_config = data.configurations.sentinel_one
            case _:
                raise Exception(NotImplemented)

        if not mdr_config:
            raise Exception(NotImplemented)

        return mdr_config    

    def tenants_resolver(self, data:TideModels.MDR, system:DetectionSystems, deployment_strategy:DeploymentStrategy)->Sequence[SystemConfig.Tenant]:
        """
        Returns a list of all the tenants configurations, if they are allowed to be targeted.
        - If ALWAYS, will be targeted on every deployment
        - If MANUAL, can only be targeted if defined in the MDR
        - If STAGING or PRODUCTION, can only be targeted if the current deployment plan alligns with it
        """
        tenants = self.system_configuration_resolver(system).tenants #type: ignore
        mdr_tenants = self.mdr_configuration_resolver(data, system).tenants
        target_tenants = list()

        for tenant in tenants:
            
            
            # If Deployment Plan is ALWAYS, we always target the tenant
            if tenant.deployment is DeploymentStrategy.ALWAYS:
                target_tenants.append(tenant)
                continue
            
            # If MDR defines target tenants, we can skip the tenant if
            # it's not defined in the MDR
            if mdr_tenants:
                if tenant.name in mdr_tenants:
                    log("SKIP",
                        f"Skipping tenant {tenant.name} as is not defined by MDR tenant list",
                        str(mdr_tenants))
                    continue
                else:
                    if tenant.deployment is DeploymentStrategy.MANUAL:
                        target_tenants.append(tenant)
                        log("SUCCESS",
                            f"Adding tenant {tenant.name} to the tenant deployment list")
                    elif tenant.deployment is deployment_strategy:
                        target_tenants.append(tenant)
                        log("SUCCESS",
                            f"Adding tenant {tenant.name} to the tenant deployment list")
                    else:
                        log("SKIP",
                            f"Skipping tenant {tenant.name} as is not compatible with current deployment plan",
                            f"Tenant deployment plan : {tenant.deployment}, current deployment plan : {deployment_strategy.name}")
                                
            else:
                if tenant.deployment is DeploymentStrategy.MANUAL:
                    log("SKIP",
                        f"Skipping tenant {tenant.name} as can only be assigned within the MDR defined tenant",
                        "You can define custom target tenants under the tenants keyword")
                    continue
                
                elif tenant.deployment is deployment_strategy:
                    target_tenants.append(tenant)
                    log("SUCCESS",
                        f"Adding tenant {tenant.name} to the tenant deployment list")
                else:
                    log("SKIP",
                        f"Skipping tenant {tenant.name} as is not compatible with current deployment plan",
                        f"Tenant deployment plan : {tenant.deployment}, current deployment plan : {deployment_strategy.name}")

        return target_tenants


    def _deep_update(self, base_dictionary:MutableMapping, updating_dictionary:MutableMapping)->MutableMapping:
        """
        Performs a deep nested mapping, so can combine dictionaries
        without overriding them
        """
        for key, value in updating_dictionary.items():
            if isinstance(value, MutableMapping):
                base_dictionary[key] = self._deep_update(base_dictionary.get(key, {}), value)
            else:
                base_dictionary[key] = value
        return base_dictionary


    def defaults_resolver(self, data:TideModels.MDR, system:DetectionSystems) -> TideModels.MDR:
        """
        Computes a new MDR Configuration based on defaults, if they are present
        in the System Configuration File, by first adding all default to a base
        configuration, then re-adding the user-defined MDR configuration on top
        """

        
        defaults = self.system_configuration_resolver(system).defaults #type: ignore
        mdr_config = self.mdr_configuration_resolver(data, system)
        new_config = dict()
        
        if not defaults:
            return data
        
        raw_config = asdict(mdr_config)
        
        # We first apply all the default onto a base configuration
        # Then we apply the user defined MDR on top. This ensures that
        # the defaults do not override anything already defined.
        for default in defaults:
            self._deep_update(new_config, {default: defaults[default]})

        self._deep_update(new_config, raw_config)
        
        try:
            return TideLoader.load_mdr(raw_config)
        except:
            log("FATAL",
                "Combining the defaults with the MDR Data has created an incompatible schema. Review your default configuration.",
                str(raw_config))
            raise TideErrors.MDRDefaultsConfigurationDataError

    def modifiers_resolver(self, data:TideModels.MDR, target_tenant:str, system:DetectionSystems) -> TideModels.MDR:
        """
        Dynamically modifies MDR data based on 
        """

        system_configuration = self.system_configuration_resolver(system)
        modifiers = system_configuration.modifiers #type: ignore
        mdr_config = self.mdr_configuration_resolver(data, system)
        system_identifier = system_configuration.platform.identifier #type: ignore
        
        if not mdr_config:
            raise NotImplemented

        raw_data = asdict(data)
        raw_mdr_config = asdict(mdr_config)
        
        log("ONGOING",
            "Checking modifiers for system",
            str(system),
            str(modifiers))
        
        if modifiers:
            log("INFO", "Found modifiers in configuration for system", str(system))
            for mod in modifiers:
                log("ONGOING",
                    f"Evaluating modifier {str(mod.name)} {str(mod.description)}",
                    str(mod.conditions))
                
                match = False
                
                if mod.conditions.status:
                    if mod.conditions.status == mdr_config.status:
                        match = True
                if mod.conditions.tenants:
                    if target_tenant in mod.conditions.tenants:
                        match = True
                    else:
                        match = False
                if mod.conditions.flags and mdr_config.flags:
                    if [tag for tag in mdr_config.flags if tag in mod.conditions.flags]:
                        match = True
                    else:
                        match = False

                if match is True:
                    log("INFO", "Condition Matching", str(mod.name or ""), str(mod.description or ""))
                    flatten_modifications = pd.json_normalize(mod.modifications).to_dict(orient="records")[0] #type: ignore
                    for modification in flatten_modifications:
                        new_value = flatten_modifications[modification]
                        new_value = None if new_value in ["NONE", "NULL"] else new_value                     
                        if new_value:
                            if "::" in new_value:
                                raw_mdr_config_flatten = pd.json_normalize(raw_mdr_config).to_dict(orient="records")[0] #type: ignore
                                operator = new_value.split("::")[0]
                                value = new_value.split("::")[1]
                                log("DEBUG", f"Found mod {modification} with operator {operator} with value {value}")
                                log("DEBUG", str(raw_mdr_config_flatten))
                                if modification in raw_mdr_config_flatten:
                                    log("DEBUG", str(raw_mdr_config_flatten[modification]))
                                    if operator == "prefix":
                                        new_value = value + (raw_mdr_config_flatten[modification] or "")
                                    elif operator == "suffix":
                                        new_value = (raw_mdr_config_flatten[modification] or "") + value
                                    log("DEBUG", "Generated new value", new_value)
                                else:
                                    new_value = value

                        updated_config = unroll_dot_dict({modification:new_value})
                        log("ONGOING", f"Applying modification {modification} -> {str(new_value)}")
                        if updated_config:
                            raw_mdr_config = self._deep_update(raw_mdr_config.copy(), updated_config) #type: ignore

        raw_data["configurations"].update({system_identifier: raw_mdr_config})
        log("INFO", "New recompiled modified deployment", str(raw_data))
        
        return TideLoader.load_mdr(raw_data)

    def deployment_resolver(self, mdr_deployment:Sequence[TideModels.MDR], system:DetectionSystems, deployment_strategy:DeploymentStrategy)->Sequence[TenantDeploymentModel]:

        deployment = list()
        tenants_data = dict()
        tenants_mapping = dict()
        
        for mdr in mdr_deployment:
            mdr = self.defaults_resolver(data=mdr,
                                        system=system)
            if type(mdr) is str:
                mdr = DataTide.Models.MDR[mdr]
            
            tenants = self.tenants_resolver(mdr, system, deployment_strategy)
            
            for tenant in tenants:
                tenants_data[tenant.name] = tenant
                tenants_mapping.setdefault(tenant.name, []).append(self.modifiers_resolver(data=mdr, 
                                                                                           target_tenant=tenant.name,
                                                                                           system=system))

        for tenant in tenants_mapping:
            deployment.append(TenantDeploymentModel(tenant=tenants_data[tenant],
                                                    rules=tenants_mapping[tenant]))

        return deployment
    
