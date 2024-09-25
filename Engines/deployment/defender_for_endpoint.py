import git
import sys

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.framework import techniques_resolver
from Engines.modules.logs import log
from Engines.modules.debug import DebugEnvironment
from Engines.modules.tide import DataTide
from Engines.modules.plugins import DeployMDR
from Engines.modules.systems.defender_for_endpoint import (DetectionRuleModel,
                                                           AlertTemplateModel,
                                                           DetectionActionModel,
                                                           ImpactedAssetsModel,
                                                           OrganizationalScopeModel,
                                                           QueryConditionModel,
                                                           ResponseActionModel,
                                                           ScheduleModel,
                                                           DefenderForEndpointService)

class DefenderForEndpointDeploy(DeployMDR):
    
    def deploy_mdr(self, data:dict, service:DefenderForEndpointService):
        ...
    
    
    def deploy(self, deployment: list[str]):
        ...
    
def declare():
    return DefenderForEndpointDeploy()

if __name__ == "__main__" and DebugEnvironment.ENABLED:
    DefenderForEndpointDeploy().deploy(DebugEnvironment.MDR_DEPLOYMENT_TEST_UUIDS)