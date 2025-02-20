import sys
import os
import requests 
import json

import git

from dataclasses import dataclass, asdict
from typing import Literal, Never, ClassVar, Sequence, overload, Any, Optional
from enum import Enum, auto

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logs import log
from Engines.modules.debug import DebugEnvironment
from Engines.modules.tide import DataTide
from Engines.modules.models import TideConfigs
from Engines.modules.deployment import Proxy
from Engines.modules.errors import TideErrors


class Severity(str, Enum):
    low = "Low"
    medium = "Medium"
    high = "High"
    critical = "Critical"
    
class SeverityMapping(Enum):
    Informational = Severity.low
    Low = Severity.low
    Medium = Severity.medium
    High = Severity.high
    Critical = Severity.high 

@dataclass
class DetectionRule:    

    @dataclass
    class Data:
        
        @dataclass
        class CoolOffSettings:
            renotifyMinutes:int
        
        @dataclass
        class CorrelationParams:
            @dataclass
            class SubQueries:
                matchesRequired: int
                subQuery: str

            @dataclass
            class TimeWindow:
                windowMinutes: str

            entity:str #Already validated in JSON Schema
            matchInOrder: bool
            subQueries: SubQueries
            timeWindow: Optional[TimeWindow] = None

        expirationMode:Literal["Permanent", "Temporary"]
        name: str
        description: str
        networkQuarantine: bool
        treatAsThreat: bool
        queryType:Literal["Correlation", "Events"]
        severity:Severity
        status:Literal["Active", "Disabled"]
        queryLand: Literal["1.0", "2.0"] = "2.0"
        s1ql: Optional[str] = None #Only for single event 
        expiration: Optional[str] = None
        coolOffSetting:Optional[CoolOffSettings] = None
        correlationParams:Optional[CorrelationParams] = None
    
    @dataclass
    class Filter:
        accountIds:list[str]
        siteIds:Optional[list[str]] = []
        
    data:Data
    filter: Filter


class SentinelOneService:
    """
    Interface to connect and deploy MDRs to SentinelOne. Initialized on a single
    tenant basis.
    """

    def __init__(self, tenant_config:TideConfigs.Systems.SentinelOne.Tenant) -> None:


        self.DEBUG = DebugEnvironment.ENABLED
        self.DEPLOYER_IDENTIFIER = DataTide.Configurations.Systems.SentinelOne.platform.identifier
        self.tenant_config = tenant_config
        self.CUSTOM_DETECTION_RULES_ENDPOINT = self.tenant_config.setup.url + "/web/api/v2.1/cloud-detection/rules"

        self.CREATE_QUERY_ENDPOINT = self.tenant_config.setup.url + "/web/api/v2.1/dv/init-query"

        self.session = requests.Session()
        self.session.headers.update({"Authorization" : f"ApiToken {self.tenant_config.setup.api_token}"})

        if tenant_config.setup.proxy:
            Proxy.set_proxy()
        else:
            Proxy.unset_proxy()

    def validate_query(self, query:str)->bool:
        ...

    def create_update_detection_rule(self, rule:DetectionRule, rule_id:Optional[int]=None)->int:
        rule_body = json.dumps(asdict(rule))
        
        endpoint = self.CUSTOM_DETECTION_RULES_ENDPOINT
        if rule_id:
            log("ONGOING", "Executing API call to update STAR Custom Rule with id", str(rule_id))
            endpoint += f"/{rule_id}"
            request = self.session.put(url=endpoint,
                                        verify=self.tenant_config.setup.ssl,
                                        json=rule_body)
        else:
            log("ONGOING", "Executing API call to create STAR Custom Rule")
            request = self.session.post(url=endpoint,
                                        verify=self.tenant_config.setup.ssl,
                                        json=rule_body)

        match request.status_code:
            case 201:
                log("SUCCESS", "Created rule in SentinelOne", str(request.json()))
                return int(request.json()["data"]["id"])

            case 400:
                log("FATAL",
                    "Received code [400], Invalid user input received",
                    str(request.json))
                raise TideErrors.DetectionRuleCreationFailed

            case 401:
                log("FATAL",
                    "Received code [401], Unauthorized access",
                    str(request.json),
                    "Check your configuration and API permissions again")
                raise TideErrors.DetectionRuleCreationFailed

            case 404:
                log("FATAL",
                    f"Received code [404], Custom Detection rule not found with id {rule_id}",
                    str(request.json),
                    "Go to SentinelOne Console and check if your rule still exists. If not, remove the rule id entry from the MDR file")
                raise TideErrors.DetectionRuleCreationFailed
        
            case _:
                log("FATAL", f"Unforeseen error with code [{request.status_code}]",
                    str(request.json()))
                raise TideErrors.DetectionRuleCreationFailed


    def disable_detection_rule(self, rule_id:int):
        ...

    def delete_detection_rule(self, rule_id:int):
        ...