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

from Engines.modules.systems.defender_for_endpoint import (DetectionRule,
                                                           Severity,
                                                           SeverityMapping,
                                                           DefenderForEndpointService)
    




class DefenderForEndpointDeploy(DeployMDR):
    
    def deploy_mdr(self, data:TideModels.MDR, service:DefenderForEndpointService):

        mdr_config = data.configurations.defender_for_endpoint
        
        if not mdr_config:
            exit()
    
        

        # Handle Response Actions 
        response_actions = []


        if mdr_config.actions:
            @dataclass
            class ResponseAction(DetectionRule.DetectionAction.ResponseAction):...

            if device_actions:=mdr_config.actions.devices:
                if isolation_type:=device_actions.isolate_device:
                    response_actions.append(ResponseAction(odata_type="#microsoft.graph.security.isolateDeviceResponseAction",
                                                            isolationType=isolation_type.lower()))

                if device_actions.collect_investigation_package:
                    response_actions.append(ResponseAction(odata_type="#microsoft.graph.security.collectInvestigationPackageResponseAction"))

                if device_actions.initiate_investigation:
                    response_actions.append(ResponseAction(odata_type="#microsoft.graph.security.initiateInvestigationResponseAction"))

                if device_actions.restrict_app_execution:
                    response_actions.append(ResponseAction(odata_type="#microsoft.graph.security.restrictAppExecutionResponseAction"))

                if device_actions.run_antivirus_scan:
                    response_actions.append(ResponseAction(odata_type="#microsoft.graph.security.runAntivirusScanResponseAction"))

            if file_actions:=mdr_config.actions.files:
                if file_actions.allow_block:
                    scope = []
                    if file_actions.allow_block.groups:
                        if file_actions.allow_block.groups.selection == "Specific":
                            scope = file_actions.allow_block.groups.device_groups

                    if file_actions.allow_block.action == "Allow":
                        response_actions.append(ResponseAction(odata_type="#microsoft.graph.security.allowFileResponseAction",
                                                                            deviceGroupNames=scope))

                    elif file_actions.allow_block.action == "Block":
                        response_actions.append(ResponseAction(odata_type="#microsoft.graph.security.blockFileResponseAction",
                                                                            deviceGroupNames=scope))

                if identifier:=file_actions.quarantine_file:
                    response_actions.append(ResponseAction(odata_type="#microsoft.graph.security.stopAndQuarantineFileResponseAction",
                                                            identifier=identifier))

        # Handle Impacted Assets
        impacted_assets = []
        if mdr_config.impacted_entities:
            
            @dataclass
            class ImpactedAsset(DetectionRule.DetectionAction.AlertTemplate.ImpactedAsset):...

            if identifier:=mdr_config.impacted_entities.device:
                impacted_assets.append(ImpactedAsset(odata_type="#microsoft.graph.security.impactedDeviceAsset",
                                                    identifier=identifier))

            if identifier:=mdr_config.impacted_entities.user:
                impacted_assets.append(ImpactedAsset(odata_type="#microsoft.graph.security.impactedUserAsset",
                                                    identifier=identifier))
            if identifier:=mdr_config.impacted_entities.mailbox:
                impacted_assets.append(ImpactedAsset(odata_type="#microsoft.graph.security.impactedMailboxAsset",
                                                    identifier=identifier))

        # Handle Severity
        if mdr_config.alert.severity:
            severity = SeverityMapping[mdr_config.alert.severity].value
        else:
            severity = data.response.alert_severity
            severity = Severity(severity)

        alert_template = DetectionRule.DetectionAction.AlertTemplate(title = mdr_config.alert.title or data.name,
                                                                    description=data.description,
                                                                    severity=severity, 
                                                                    category=mdr_config.alert.category,
                                                                    mitreTechniques=[],
                                                                    impactedAssets=impacted_assets,
                                                                    recommendedActions=mdr_config.alert.recommendation or None)

        scheduling = mdr_config.scheduling if mdr_config.scheduling != "NRT" else "0"
        rule = DetectionRule(displayName=data.name,
                            isEnabled=True,
                            queryCondition=DetectionRule.QueryCondition(queryText=mdr_config.query),
                            schedule=DetectionRule.Schedule(period=scheduling), # type: ignore
                            detectionAction=DetectionRule.DetectionAction(alertTemplate=alert_template,
                                                                            responseActions=response_actions))
        from dataclasses import asdict
        print(asdict(rule))
        exit()
        service.create_detection_rule(rule)
    
    def deploy(self, mdr_deployment: Sequence[TideModels.MDR], deployment_plan:DeploymentStrategy):
        
        mdr_deployment = [DataTide.Models.MDR[uuid] for uuid in mdr_deployment]

        deployment = TideDeployment(deployment=mdr_deployment,
                                    system=DetectionSystems.DEFENDER_FOR_ENDPOINT,
                                    strategy=deployment_plan)
        
        for tenant_deployment in deployment.rule_deployment:
            service = DefenderForEndpointService(tenant_deployment.tenant)
            tt = {"rr":{"rr":["ee"]}}
            for mdr in tenant_deployment.rules:
                self.deploy_mdr(data=mdr, service=service)

            

def declare():
    return DefenderForEndpointDeploy()

if __name__ == "__main__" and DebugEnvironment.ENABLED:
    DefenderForEndpointDeploy().deploy(DebugEnvironment.MDR_DEPLOYMENT_TEST_UUIDS, DeploymentStrategy.DEBUG)