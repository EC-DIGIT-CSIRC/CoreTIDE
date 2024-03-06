import importlib
import sys
import git
from abc import ABC, abstractmethod
from dataclasses import dataclass

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.tide import DataTide
from Engines.modules.logs import log


class DeployEngine(ABC):
    pass


class DeployMDR(DeployEngine):
    @abstractmethod
    def deploy(self, deployment: list[str]):
        """Deploy MDR Objects onto target systems"""


class DeployMetadata(DeployEngine):
    @abstractmethod
    def deploy(self, deployment: list[str], lookup_name: str):
        """Deploy MDR Metadata onto target systems"""


class DeployLookups(DeployEngine):
    @abstractmethod
    def deploy(self, deployment: list[str]):
        """Deploy Lookups onto target systems"""


class DeployEnginesLoader:
    """Return Deployer Classes for all available Deployment Engines"""

    class PluginInterface:
        """Represents a plugin interface. A plugin has a single declare function."""

        @staticmethod
        def declare():
            """Registers the DeployEngine Class"""
            ...

    @staticmethod
    def import_plugin(plugin: str) -> PluginInterface:
        return importlib.import_module(plugin)  # type: ignore

    def _generic_loader(self, identifier: str = ""):
        log("ONGOING", "Initiating deployment plugin routine")
        available_plugins: dict = {}
        CONFIGURATIONS: dict[str, dict] = DataTide.Configurations.Systems.Index
        for system in CONFIGURATIONS:
            plugin_name: str = system + identifier
            try:
                plugin = self.import_plugin(
                    str("Engines.deployment." + plugin_name)
                )
                try:
                    available_plugins[system] = plugin.declare()
                except Exception as e:
                    log(
                        "FATAL",
                        "Was able to import module but couldn't declare the plugin",
                        plugin_name,
                        "The plugin should contain a declare() function returning"
                        "the deploy engine Class",
                    )
                    log("FATAL", repr(e))
                    raise Exception("DEPLOYMENT ENGINE PLUGIN IMPORT ERROR")
                log("SUCCESS", "Found deployment plugin for", plugin_name)
            except:
                log("SKIP", "No deployment plugin found for", plugin_name)

        return available_plugins

    def mdr_deployers(self) -> dict[str, DeployMDR]:
        return self._generic_loader()

    def lookups_deployers(self) -> dict[str, DeployLookups]:
        return self._generic_loader(identifier="_lookups")

    def metadata_deployers(self) -> dict[str, DeployMetadata]:
        return self._generic_loader(identifier="_metadata")


@dataclass
class DeployTide:
    """Unified interface to interact with deployment engines plugins"""

    mdr = DeployEnginesLoader().mdr_deployers()
    lookups = DeployEnginesLoader().lookups_deployers()
    metadata = DeployEnginesLoader().metadata_deployers()
