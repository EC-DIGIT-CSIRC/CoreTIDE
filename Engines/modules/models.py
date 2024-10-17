import os
import sys
from tokenize import String
import git

from dataclasses import dataclass
from typing import Literal, Never, Optional, Sequence, Mapping, Any, Union
from enum import Enum, auto

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logs import log


class DetectionSystems(Enum):
    DEFENDER_FOR_ENDPOINT = auto()
    CARBON_BLACK_CLOUD = auto()
    SPLUNK = auto()
    SENTINEL = auto()

class DeploymentStrategy(Enum):
    STAGING = auto()
    PRODUCTION = auto()
    FULL = auto()
    ALWAYS = auto()
    MANUAL = auto()
    DEBUG = auto()

    @staticmethod
    def load_from_environment():
        """
        Read the DEPLOYMENT_PLAN environment variable and maps it to 
        DeploymentStrategy valid values. In case of an illegal value, 
        or missing environment variable will raise an exception
        """
        SUPPORTED_PLANS = [plan.name for plan in DeploymentStrategy]
        DEPLOYMENT_PLAN = str(os.getenv("DEPLOYMENT_PLAN")) or None
        if not DEPLOYMENT_PLAN:
            log(
                "FATAL",
                "No deployment plan, ensure that the CI variable DEPLOYMENT_PLAN is set correctly",
            )
            raise Exception("NO DEPLOYMENT PLAN")

        try:
            DEPLOYMENT_PLAN = DeploymentStrategy[DEPLOYMENT_PLAN]
        except:

                log(
                    "FATAL",
                    "The following deployment plan is not supported",
                    DEPLOYMENT_PLAN,
                    f"Supported plan : {SUPPORTED_PLANS}",
                )
                raise AttributeError("UNSUPPORTED DEPLOYMENT PLAN")

        return DEPLOYMENT_PLAN


@dataclass
class SystemConfig:

    @dataclass
    class Platform:
        enabled: bool
        identifier: str
        name: str
        subschema: str
        description: str
        tenants: list[str]
        flags: list[str]

    @dataclass
    class Modifiers:
        @dataclass
        class Conditions:
            status: Optional[Sequence[str]] 
            flags: Optional[Sequence[Never] | Sequence[str]]
            tenants: Optional[Sequence[Never] | Sequence[str]] 
            description: str 

        conditions: Conditions
        modifications: dict

    @dataclass 
    class Tenant:
        @dataclass
        class Setup:
            proxy: bool
            ssl: bool

        name: str
        description: str
        deployment: Union[DeploymentStrategy, str]
        setup: Setup

        def __post_init__(self):
            if type(self.deployment) is str:
                self.deployment = DeploymentStrategy[self.deployment]

    platform: Platform
    modifiers: Sequence[Modifiers] | Sequence[Never]
    tenants: Sequence[Tenant]
    defaults: dict[str,str]

@dataclass
class TideConfigs:

    @dataclass
    class Systems:

        @dataclass
        class Sentinel(SystemConfig):
            ...

        @dataclass
        class Splunk(SystemConfig):
            ...

        @dataclass
        class CarbonBlackCloud(SystemConfig):
            ...

        @dataclass
        class DefenderForEndpoint(SystemConfig):
            
            @dataclass
            class Platform(SystemConfig.Platform):
                device_groups: Sequence[str]

            @dataclass
            class Tenant(SystemConfig.Tenant):

                @dataclass
                class Setup(SystemConfig.Tenant.Setup):
                    tenant_id: str
                    client_id: str
                    secret_id: str
                    client_secret: str

                setup:Setup

            platform: Platform
            tenants: Sequence[Tenant]



class TideDefinitionsModels:

    @dataclass
    class TideObjectMetadata:
        uuid: str
        schema: str
        version: str | int
        created: str
        modified: str
        tlp: str
        author: str
        contributors: Optional[Sequence[str]] = None

    @dataclass
    class TideObjectReferences:
        public: Optional[Mapping[int, str]] = None
        internal: Optional[Mapping[str, str]] = None
        reports: Optional[Sequence[str]] = None

    @dataclass
    class SystemConfigurationModel:
        schema: str
        status: str
        flags: Optional[list[Never] | list[str]]
        tenants: Optional[list[str]]
        contributors: Optional[list[str]]


class TideModels:

    @dataclass
    class MDR:
    
        @dataclass
        class Response:
            alert_severity: Optional[str] = None 
            playbook: Optional[str] = None
            responders: Optional[str] = None

        @dataclass
        class Configurations:
            
            @dataclass
            class DefenderForEndpoint(TideDefinitionsModels.SystemConfigurationModel):
                @dataclass
                class Alert:
                    category: str
                    title: Optional[str] = None
                    severity: Optional[str] = None
                    recommendation: Optional[str] = None

                @dataclass
                class ImpactedEntities:
                    device: Optional[str] = None
                    mailbox: Optional[str] = None
                    user: Optional[str] = None

                @dataclass
                class GroupScoping:
                    selection: Literal["All", "Specific"]
                    device_groups: Optional[Sequence[str]] = None

                @dataclass
                class ResponseActions:
                    
                    @dataclass
                    class FileActions:
                                    
                        @dataclass
                        class FileAllowBlockAction:
                        
                            @dataclass
                            class GroupScoping:
                                selection: Literal["All", "Specific"]
                                device_groups: Optional[Sequence[str]] = None

                            action: Literal["Allow", "Block"]
                            column: str
                            groups: Optional[GroupScoping] = None
            
                        allow_block: Optional[FileAllowBlockAction] = None
                        quarantine_file: Optional[str] = None

                    @dataclass
                    class DeviceActions:
                        isolate_device: Optional[str] = None
                        collect_investigation_package: bool = False
                        run_antivirus_scan:bool = False
                        initiate_investigation:bool = False
                        restrict_app_execution:bool = False

                    devices: Optional[DeviceActions] = None
                    files: Optional[FileActions] = None

                    
                
                schema: str
                alert: Alert
                query: str
                impacted_entities: ImpactedEntities
                scheduling: Literal["NRT", "1H", "3H", "12H", "24H"]
                actions: Optional[ResponseActions] = None
                scope: Optional[GroupScoping] = None
            
            @dataclass
            class Splunk(TideDefinitionsModels.SystemConfigurationModel):
                ...

            @dataclass
            class Sentinel(TideDefinitionsModels.SystemConfigurationModel):
                ...

            @dataclass
            class CarbonBlackCloud(TideDefinitionsModels.SystemConfigurationModel):
                ...
                        
            defender_for_endpoint: Optional[DefenderForEndpoint] = None
            carbon_black_cloud: Optional[Mapping] = None
            splunk: Optional[Mapping] = None
            sentinel: Optional[Mapping] = None

        name: str
        metadata: TideDefinitionsModels.TideObjectMetadata
        description: str
        response: Response
        configurations: Configurations
        detection_model: Optional[str] = None
        references: Optional[TideDefinitionsModels.TideObjectReferences] = None


@dataclass
class TenantDeploymentModel:
    """
    Base common dataclass used to construct tenant deployment
    per system
    """
    tenant: SystemConfig.Tenant
    rules: Sequence[TideModels.MDR]

class TenantDeployment:

    @dataclass
    class Splunk(TenantDeploymentModel):
        tenant: TideConfigs.Systems.DefenderForEndpoint.Tenant

    @dataclass
    class Sentinel(TenantDeploymentModel):
        tenant: TideConfigs.Systems.DefenderForEndpoint.Tenant

    @dataclass
    class CarbonBlackCloud(TenantDeploymentModel):
        tenant: TideConfigs.Systems.DefenderForEndpoint.Tenant

    @dataclass
    class DefenderForEndpoint(TenantDeploymentModel):
        tenant: TideConfigs.Systems.DefenderForEndpoint.Tenant
