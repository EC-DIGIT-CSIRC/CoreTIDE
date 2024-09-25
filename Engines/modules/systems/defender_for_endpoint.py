import sys 
import requests 

import git

from dataclasses import dataclass, asdict
from typing import Literal, Never, ClassVar, overload

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logs import log
from Engines.modules.debug import DebugEnvironment
from Engines.modules.tide import DataTide, TenantsDefenderForEndpointConfigModel
from Engines.modules.deployment import Proxy
from Engines.modules.errors import TideErrors

@dataclass
class QueryConditionModel:
    query_text: str

@dataclass
class OrganizationalScopeModel:
    scope_type = Literal["deviceGroup"]
    scope_names = list[str]

@dataclass
class ImpactedAssetsModel:
    odata_type = str
    identifier = Literal["deviceId"]

@dataclass
class AlertTemplateModel:
    title: str
    description: str
    severity: str
    category: str
    mitre_techniques: ClassVar[list[Never] | list[str]] = []
    impacted_assets: ClassVar[list[Never] | list[ImpactedAssetsModel]] = []
    recommended_actions: ClassVar[None | str] = None

@dataclass
class ResponseActionModel:
    odata_type: str
    identifier: str
    isolation_type: ClassVar[str | None] = None
    device_group_names: ClassVar[list[str] | None] = None

@dataclass
class DetectionActionModel:
    alert_template: AlertTemplateModel
    response_actions: list[ResponseActionModel]
    organizational_scope: ClassVar[None | OrganizationalScopeModel] = None

@dataclass
class ScheduleModel:
    period: str

@dataclass
class DetectionRuleModel:
    detector_id: str
    display_name: str
    is_enabled: bool
    created_by = Literal["EC-TIDE Automation"]
    query_condition: QueryConditionModel
    schedule: ScheduleModel
    detection_action: DetectionActionModel


class DefenderForEndpointService:
    
    def __init__(self, tenant_config:TenantsDefenderForEndpointConfigModel) -> None:

        self.DEBUG = DebugEnvironment.ENABLED
        self.DEPLOYER_IDENTIFIER = "defender_for_endpoint"
        self.GRAPH_API_ENDPOINT = "https://graph.microsoft.com/beta/security/rules/detectionRule"
        self.tenant_config = tenant_config
        
        if tenant_config.setup.proxy:
            Proxy.set_proxy()
        else:
            Proxy.unset_proxy()
        
        self.access_token = self._connect_to_tenant(self.tenant_config.setup.client_id,
                                                   self.tenant_config.setup.tenant_id,
                                                   self.tenant_config.setup.client_secret)
        
        self.session = requests.Session()
        self.session.headers.update({"Authorization" : f"Bearer {self.access_token}",
                                                        "Content-Type" : "application/json"})


    def _connect_to_tenant(self, client_id:str, tenant_id:str, client_secret:str):
        
        data = {"client_id":client_id,
                "client_secret":client_secret,
                "grant_type":"client_credentials",
                "scope":"https://graph.microsoft.com/.default"}
        
        response = requests.post(data=data,
                                 url=f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token")
        
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            log("FATAL",
                f"Cannot authenticate against {self.tenant_config.name}",
                "Ensure your tenant configuration is correct")
            raise TideErrors.TenantConnectionError("Cannot authenticate with the tenant configuration")

    def create_detection_rule(self, rule:DetectionRuleModel)->int:
        rule_body = asdict(rule)
        rule_body = self.camelify(rule_body)
        request = self.session.post(url=self.GRAPH_API_ENDPOINT,
                                    json=rule_body)

        if request.status_code == 201:
            return int(request.json()["id"])
        else:
            log("FATAL",
                f"Failed to create detection rule in tenant {self.tenant_config.name}",
                str(rule_body))
            raise TideErrors.DetectionRuleCreationFailed

    def update_detection_rule(self, rule:DetectionRuleModel, rule_id:int):
        rule_body = asdict(rule)
        rule_body = self.camelify(rule_body)
        request = self.session.patch(url=self.GRAPH_API_ENDPOINT + f"/{rule_id}",
                                     json=rule_body)
        if request.status_code != 200:
            log("FATAL",
                f"Failed to create detection rule with id {rule_id} in tenant {self.tenant_config.name}",
                str(rule_body))
            raise TideErrors.DetectionRuleUpdateFailed

    def delete_detection_rule(self, rule_id:int):
        request = self.session.delete(url=self.GRAPH_API_ENDPOINT + f"/{rule_id}")
        if request.status_code != 204:
            log("FATAL",
                f"Failed to create detection rule with id {rule_id} in tenant {self.tenant_config.name}",
                "Double check scope permissions, and whether the ID actually exists")
            raise TideErrors.DetectionRuleDeletionFailed

    @overload
    def camelify(self, input:dict[str,dict])->dict[str,dict]: ...
    @overload
    def camelify(self, input:dict[str,list])->dict[str,list]: ...
    @overload
    def camelify(self, input:dict[str,str])->dict[str,str]: ...
    @overload
    def camelify(self, input:list[dict])->list[dict]: ...
    @overload
    def camelify(self, input:list[str])->list[str]: ...
    def camelify(self, input):
        """
        Turns strings, list, dictionaries, and any combinations of those
        from snake_case to camelCase
        """
        def snake_to_camel(string:str)->str:
            split = string.split("_")
            camel = str()
            for index, word in enumerate(split):
                if index == 0:
                    camel += word
                    continue
                camel += word.capitalize()
            return camel

        if type(input) is str:
            return snake_to_camel(input)

        if type(input) is list:
            camel_list = [self.camelify(x) for x in input] 
            return camel_list

        if type(input) is dict:
            camel_dictionary = {}
            for key, value in input.items():
                if type(value) is dict:
                    camel_dictionary[snake_to_camel(key)] = self.camelify(value)

                elif type(value) is list:
                    newvalues = [self.camelify(x) for x in value]
                    camel_dictionary[snake_to_camel(key)] = newvalues

                else:
                    camel_dictionary[snake_to_camel(key)] = value
        
            return camel_dictionary




for tenant in DataTide.Configurations.Systems.DefenderForEndpoint.tenants:
    DefenderForEndpointService(tenant)