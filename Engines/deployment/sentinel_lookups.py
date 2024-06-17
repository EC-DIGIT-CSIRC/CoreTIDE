import os
import git
import pandas as pd
import time
import sys
import uuid
from io import StringIO

start_time = time.time()

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logs import log
from Engines.modules.deployment import fetch_config_envvar, Proxy
from Engines.modules.sentinel import connect_to_sentinel
from Engines.modules.tide import DataTide
from Engines.modules.plugins import DeployLookups

from azure.mgmt.securityinsight import SecurityInsights


class SentinelLookupsDeploy(DeployLookups):
    def __init__(self):
        DEBUG = True

        self.LOOKUPS_METADATA_INDEX = DataTide.Lookups.metadata
        self.LOOKUPS_INDEX = DataTide.Lookups.lookups["sentinel"]

        SENTINEL_CONFIG = DataTide.Configurations.Systems.Sentinel
        SENTINEL_SETUP = fetch_config_envvar(SENTINEL_CONFIG.setup)
        SENTINEL_SECRETS = fetch_config_envvar(SENTINEL_CONFIG.secrets)

        if SENTINEL_SETUP["proxy"]:
            Proxy.set_proxy()
        else:
            Proxy.unset_proxy()

        self.AZURE_CLIENT_ID = SENTINEL_SECRETS["azure_client_id"]
        self.AZURE_CLIENT_SECRET = SENTINEL_SECRETS["azure_client_secret"]
        self.AZURE_SENTINEL_RESOURCE_GROUP = SENTINEL_SETUP["resource_group"]
        self.AZURE_SENTINEL_WORKSPACE_NAME = SENTINEL_SETUP["workspace"]
        self.AZURE_SUBSCRIPTION_ID = SENTINEL_SETUP["azure_subscription_id"]
        self.AZURE_TENANT_ID = SENTINEL_SETUP["azure_tenant_id"]

    def deploy_lookup(
        self, lookup_name: str, lookup_content: pd.DataFrame, client: SecurityInsights
    ):
        lookup_metadata = self.LOOKUPS_METADATA_INDEX.get(lookup_name, {})
        watchlist = client.watchlists.models.Watchlist()

        lookup_search_key = lookup_metadata.get("sentinel", {}).get("search_key")
        lookup_watchlist_alias = lookup_metadata.get("sentinel", {}).get(
            "watchlist_alias"
        )

        lookup_content = lookup_content.fillna("").astype(str)

        watchlist.display_name = lookup_metadata.get("name") or lookup_name
        watchlist.provider = "EC-TIDE"
        watchlist.source = lookup_name + (".csv")
        watchlist.content_type = "text/csv"
        watchlist.description = (
            lookup_metadata.get("description") or "EC-TIDE Managed Lookup"
        )
        watchlist.items_search_key = lookup_search_key or lookup_content.columns[0]

        lookup_content.to_csv("test.csv", index=False)

        # Trigger deletion and recreation if alias or search key change
        existing_watchlist = client.watchlists.list(
            resource_group_name=self.AZURE_SENTINEL_RESOURCE_GROUP,
            workspace_name=self.AZURE_SENTINEL_WORKSPACE_NAME,
        )
        delayed_deletion = False
        for existing in existing_watchlist:
            if existing.source == watchlist.source:

                # If the search key changed, we need to delete synchronousely as it
                # is an unmutable parameter.
                if existing.items_search_key != watchlist.items_search_key:
                    client.watchlists.delete(
                        resource_group_name=self.AZURE_SENTINEL_RESOURCE_GROUP,
                        workspace_name=self.AZURE_SENTINEL_WORKSPACE_NAME,
                        watchlist_alias=str(existing.watchlist_alias),
                    )

                    # Check that the watchlist is removed before moving on, else the creation
                    # will be rejected if the alias stayed the same
                    deleted = False
                    while not deleted:
                        try:
                            client.watchlists.get(
                                resource_group_name=self.AZURE_SENTINEL_RESOURCE_GROUP,
                                workspace_name=self.AZURE_SENTINEL_WORKSPACE_NAME,
                                watchlist_alias=str(existing.watchlist_alias),
                            )
                        except:
                            deleted = True

                # If the alias change, Sentinel will create a new watchlist. By safety,
                # we can delete it async after the new watchlist is created to reduce the
                # time where a watchlist is not available.
                elif existing.watchlist_alias != watchlist.watchlist_alias:
                    delayed_deletion = existing.watchlist_alias

                break

        # Check if watchlist exists, else create
        client.watchlists.create_or_update(
            resource_group_name=self.AZURE_SENTINEL_RESOURCE_GROUP,
            workspace_name=self.AZURE_SENTINEL_WORKSPACE_NAME,
            watchlist_alias=(lookup_watchlist_alias or lookup_name),
            watchlist=watchlist,
        )

        # Getting all current items
        watchlist_items = client.watchlist_items.list(
            resource_group_name=self.AZURE_SENTINEL_RESOURCE_GROUP,
            workspace_name=self.AZURE_SENTINEL_WORKSPACE_NAME,
            watchlist_alias=(lookup_watchlist_alias or lookup_name),
        )

        # Building Indexes
        watchlist_content = []
        watchlist_content_index = {}
        for i in watchlist_items:
            watchlist_content.append(i.items_key_value)
            watchlist_content_index[i.watchlist_item_id] = i.items_key_value

        csv_content = []
        for index, row in lookup_content.iterrows():
            csv_content.append(dict(row))

        # If watchlist item not in lookup, we delete it
        for watch_item_id in watchlist_content_index:
            if watchlist_content_index[watch_item_id] not in csv_content:
                client.watchlist_items.delete(
                    resource_group_name=self.AZURE_SENTINEL_RESOURCE_GROUP,
                    workspace_name=self.AZURE_SENTINEL_WORKSPACE_NAME,
                    watchlist_alias=(lookup_watchlist_alias or lookup_name),
                    watchlist_item_id=watch_item_id,
                )
        # If lookup content not in lookup, we create it
        for lookup_item in csv_content:
            if lookup_item not in watchlist_content:
                item_model = client.watchlists.models.WatchlistItem()
                item_model.items_key_value = lookup_item
                client.watchlist_items.create_or_update(
                    resource_group_name=self.AZURE_SENTINEL_RESOURCE_GROUP,
                    workspace_name=self.AZURE_SENTINEL_WORKSPACE_NAME,
                    watchlist_alias=(lookup_watchlist_alias or lookup_name),
                    watchlist_item_id=str(uuid.uuid4()),
                    watchlist_item=item_model,
                )

        # Async deletion for watchlist alias change
        if delayed_deletion:
            client.watchlists.delete(
                resource_group_name=self.AZURE_SENTINEL_RESOURCE_GROUP,
                workspace_name=self.AZURE_SENTINEL_WORKSPACE_NAME,
                watchlist_alias=delayed_deletion,
            )

        return True

    def deploy(self, deployment: list[str], DEBUG=False):
        log("ONGOING", "Sentinel Watchlist Deployer")
        log(
            "INFO",
            "Performs a progressive and safe update of Watchlists with\
            the newly modified one from CoreTIDE",
        )

        if DEBUG:
            deployment = ["TIDE_LD_999_Debug.csv"]

        client = connect_to_sentinel(
            self.AZURE_CLIENT_ID,
            self.AZURE_CLIENT_SECRET,
            self.AZURE_TENANT_ID,
            self.AZURE_SUBSCRIPTION_ID,
        )

        # Start deployment routine
        for lookup in deployment:
            if lookup.endswith(".csv"):
                lookup.removesuffix(".csv")
            lookup_content = pd.read_csv(StringIO(self.LOOKUPS_INDEX[lookup]))
            lookup_name = "".join(c for c in lookup if (c.isalnum() or c in [" ", "_"]))

            if lookup not in self.LOOKUPS_INDEX:
                log(
                    "FAILURE",
                    f"Skipping {lookup_name} as can not find the lookup name in the current index",
                )
                raise (Exception)

            log("INFO", "Lookup deployment started", lookup_name)
            self.deploy_lookup(lookup_name, lookup_content, client)
            log("SUCCESS", "Lookup deployment successful", lookup_name)


def declare():
    return SentinelLookupsDeploy()
