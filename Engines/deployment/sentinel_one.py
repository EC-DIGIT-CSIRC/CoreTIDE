import git
import sys

from typing import Sequence
from dataclasses import dataclass

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.debug import DebugEnvironment
from Engines.modules.tide import DataTide, DetectionSystems, TideLoader
from Engines.modules.plugins import DeployMDR
from Engines.modules.models import (TideModels,
                                    DeploymentStrategy) 
from Engines.modules.deployment import TideDeployment
from Engines.modules.logs import log
from Engines.modules.models import TideConfigs

from Engines.modules.systems.sentinel_one import SentinelOneService, DetectionRule, SeverityMapping

class SentinelOneDeploy(DeployMDR):

    def deploy_mdr(self, data:TideModels.MDR, service:SentinelOneService, tenant_config:TideConfigs.Systems.SentinelOne.Tenant):
        
        mdr_config = data.configurations.sentinel_one

        if not mdr_config:
            exit()
        
        rule_name = data.name
        rule_description = data.description
        rule_expiration_mode = "Permanent"
        rule_severity = SeverityMapping[data.response.alert_severity].value
        rule_expiration = None
        rule_status = "Disabled" if mdr_config.status == "DISABLED" else "Active"
        treat_as_threat = mdr_config.response.treat_as_threat
        network_quarantine = mdr_config.response.network_quarantine

        if details:=mdr_config.details:
            if details.name:
                rule_name = details.name
            if details.description:
                rule_description = details.description
            if details.expiration:
                rule_expiration_mode = "Temporary"
                rule_expiration = details.expiration

        if single_event_data:=mdr_config.condition.single_event:
            query = single_event_data.query
            rule_data = DetectionRule.Data(name=rule_name,
                                            queryType="Events",
                                            s1ql=query,
                                            severity=rule_severity,
                                            status=rule_status,
                                            expirationMode=rule_expiration_mode,
                                            expiration=rule_expiration,
                                            description=rule_description,
                                            networkQuarantine=network_quarantine,
                                            treatAsThreat=treat_as_threat)
        elif correlation_data:=mdr_config.condition.correlation:
            
            sub_queries = []
                        
            for sub_query in correlation_data.sub_queries:
                sub_queries.append(DetectionRule.Data.CorrelationParams.SubQueries(matchesRequired=sub_query.matches_required,
                                                                                   subQuery=sub_query.query))

            time_window_config = None
            if correlation_data.time_window:
                time_window_config = DetectionRule.Data.CorrelationParams.TimeWindow(windowMinutes = correlation_data.time_window)

            correlation_config = DetectionRule.Data.CorrelationParams(entity=correlation_data.entity,
                                                                      matchInOrder=correlation_data.match_in_order,
                                                                      subQueries=sub_queries, #type: ignore
                                                                      timeWindow=time_window_config)
            
            rule_data = DetectionRule.Data(name=rule_name,
                                            queryType="Events",
                                            correlationParams=correlation_config,
                                            severity=rule_severity,
                                            status=rule_status,
                                            expirationMode=rule_expiration_mode,
                                            expiration=rule_expiration,
                                            description=rule_description,
                                            networkQuarantine=network_quarantine,
                                            treatAsThreat=treat_as_threat)

        else:
            raise Exception

        deployment_filter = DetectionRule.Filter(accountIds=[tenant_config.setup.scope],
                                                 siteIds=[tenant_config.setup.site] if tenant_config.setup.site else None)

        rule = DetectionRule(data=rule_data,
                             filter=deployment_filter)

        
        if mdr_config.rule_id_bundle:
            rule_id = mdr_config.rule_id_bundle.get(tenant_config.name) #type:ignore
            log("INFO",
                f"Retrieved ID for tenant {tenant_config.name} in MDR",
                str(rule_id),
                "Will perform an update")
        else:
            log("INFO",
                f"Could not retrieve ID for tenant {tenant_config.name} in MDR",
                "Will create a new rule, and write back the ID to the file")

            rule_id = None

        
        if mdr_config.status == "REMOVED":
            if not rule_id:
                log("FATAL",
                    "Cannot remove the rule as a rule_id could not be found in the file",
                    "You will need to manually check the target system to remove the rule")
            else:
                log("ONGOING",
                    f"Proceeding with deletion of rule against tenant {tenant_config.name}",
                    str(rule_id))
                
                service.delete_detection_rule(rule_id)
                file_path = DataTide.Configurations.Global.Paths.Tide.mdr / DataTide.Models.files[data.metadata.uuid]
                with open(file_path, "r", encoding="utf-8") as mdr_file:
                    content = mdr_file.readlines()

                updated_content = list()

                #Remove previous rule ID from file
                for line in content:
                    if line.strip() != f"rule_id::{tenant_config.name}: {rule_id}":
                        updated_content.append(line)

                with open(file_path, "w", encoding="utf-8") as mdr_file:
                    log("SUCCESS",
                    f"Removed ID in MDR File for tenant {tenant_config.name}")
                    mdr_file.writelines(updated_content)

        else:
            if rule_id:
                service.create_update_detection_rule(rule, rule_id)
        
            else:
                rule_id = service.create_update_detection_rule(rule)
                file_path = DataTide.Configurations.Global.Paths.Tide.mdr / DataTide.Models.files[data.metadata.uuid]
                with open(file_path, "r", encoding="utf-8") as mdr_file:
                    content = mdr_file.readlines()
                
                updated_content = list()
                for line in content:
                    log("DEBUG", line)
                    if line.strip() == 'sentinel_one:':
                        updated_content.append(line)
                        updated_content.append(f"    rule_id::{tenant_config.name}: {rule_id}\n")
                        log("DEBUG", "Appending line", str(rule_id))
                    else:
                        updated_content.append(line)

                with open(file_path, "w", encoding="utf-8") as mdr_file:
                    log("SUCCESS",
                    f"Updated MDR File with new ID for tenant {tenant_config.name}",
                    str(rule_id))
                    mdr_file.writelines(updated_content)


    def deploy(self, mdr_deployment: Sequence[TideModels.MDR], deployment_plan:DeploymentStrategy):
        mdr_deployment = [DataTide.Models.MDR[uuid] for uuid in mdr_deployment]

        deployment = TideDeployment(deployment=mdr_deployment,
                                    system=DetectionSystems.SENTINEL_ONE,
                                    strategy=deployment_plan)

        for tenant_deployment in deployment.rule_deployment:
            service = SentinelOneService(tenant_deployment.tenant)

            for mdr in tenant_deployment.rules:
                self.deploy_mdr(data=mdr, service=service, tenant_config=tenant_deployment.tenant)

def declare():
    return SentinelOneDeploy()

if __name__ == "__main__" and DebugEnvironment.ENABLED:
    SentinelOneDeploy().deploy(DebugEnvironment.MDR_DEPLOYMENT_TEST_UUIDS, DeploymentStrategy.DEBUG)