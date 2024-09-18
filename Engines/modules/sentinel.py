import sys
import os
from datetime import timedelta
from abc import ABC

import git

from azure.mgmt.securityinsight import SecurityInsights
from azure.identity import ClientSecretCredential

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.tide import DataTide
from Engines.modules.logs import log
from Engines.modules.debug import DebugEnvironment
from Engines.modules.deployment import fetch_config_envvar, Proxy

class SentinelEngineInit(ABC):

    def __init__(self):
        
        self.DEBUG = DebugEnvironment.ENABLED
        self.DEPLOYER_IDENTIFIER = "sentinel"

        SENTINEL_CONFIG = DataTide.Configurations.Systems.Sentinel
        self.DEFAULT_CONFIG = SENTINEL_CONFIG.defaults
        SENTINEL_SETUP = fetch_config_envvar(SENTINEL_CONFIG.setup)
        SENTINEL_SECRETS = fetch_config_envvar(SENTINEL_CONFIG.secrets)

        if SENTINEL_SETUP["proxy"]:
            Proxy.set_proxy()
        else:
            Proxy.unset_proxy()
        
        self.SSL_ENABLED = SENTINEL_SETUP["ssl"]
        self.AZURE_CLIENT_ID = SENTINEL_SECRETS["azure_client_id"]
        self.AZURE_CLIENT_SECRET = SENTINEL_SECRETS["azure_client_secret"]
        self.AZURE_SENTINEL_RESOURCE_GROUP = SENTINEL_SETUP["resource_group"]
        self.AZURE_SENTINEL_WORKSPACE_NAME = SENTINEL_SETUP["workspace_name"]
        self.AZURE_SENTINEL_WORKSPACE_ID = SENTINEL_SETUP["workspace_id"]
        self.AZURE_SUBSCRIPTION_ID = SENTINEL_SETUP["azure_subscription_id"]
        self.AZURE_TENANT_ID = SENTINEL_SETUP["azure_tenant_id"]

        self.SPLUNK_SUBSCHEMA = DataTide.TideSchemas.subschemas["systems"][
            self.DEPLOYER_IDENTIFIER
        ]["properties"]
        self.LOOKUPS_METADATA_INDEX = DataTide.Lookups.metadata
        self.LOOKUPS_INDEX = DataTide.Lookups.lookups[self.DEPLOYER_IDENTIFIER]

        if self.DEBUG:
            self.SSL_ENABLED = DebugEnvironment.SSL_ENABLED

        log("INFO", "SSL has been set to",
        str(self.SSL_ENABLED),
        "This can be adjusted in sentinel.toml with the setup.ssl keyword")



def connect_sentinel(
    client_id: str,
    client_secret: str,
    tenant_id: str,
    subscription_id: str,
    ssl_enabled:bool =True
) -> SecurityInsights:

    credentials = ClientSecretCredential(tenant_id, client_id, client_secret)
    
    # connection_verify kwarg should be carried through to the ConnectionConfiguration
    # class of azure.core and be then passed to the requests package
    client = SecurityInsights(credentials,
                              subscription_id,
                              connection_verify=ssl_enabled)

    return client


def iso_duration_timedelta(duration: str) -> timedelta:
    """
    Converts an simple duration into an ISO 8601 compliant time duration.
    See https://tc39.es/proposal-temporal/docs/duration.html for more information.
    """

    unit = duration[-1]
    count = int(duration[:-1])

    match unit:
        case "m":
            delta = timedelta(minutes=count)
        case "h":
            delta = timedelta(hours=count)
        case "d":
            delta = timedelta(days=count)
        case _:
            raise Exception(
                f"☢️ [FATAL] Duration {duration} is not in supported unit (m, h or d)"
            )

    return delta


def build_query(data: dict) -> str:
    """
    Modifies KQL Query to add customizable capabilities
    """
    # Backwards compatible with 1.0 data model
    uuid = data.get("uuid") or data["metadata"]["uuid"]
    mdr_sentinel = data["configurations"]["sentinel"]
    kql = mdr_sentinel["query"].strip()
    extend_uuid = f"| extend MDR_UUID = '{uuid}' "

    return kql + extend_uuid

def build_description(data: dict) -> str:
    """
    Modifies MDR Description to add customizable capabilities
    """
    # Backwards compatible with 1.0 data model
    uuid = data.get("uuid") or data["metadata"]["uuid"]
    description = data["description"]
    uuid_header = f"uuid::{uuid}::description::"

    return uuid_header + description
