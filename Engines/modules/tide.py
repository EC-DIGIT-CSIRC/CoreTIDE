import os
import git
import sys
from pathlib import Path
import json
from typing import Literal, Dict, Tuple
from enum import Enum, auto
from functools import cache

from dataclasses import dataclass

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.indexing.indexer import indexer
from Engines.modules.logs import log
from Engines.modules.patching import Tide2Patching

ROOT = Path(str(git.Repo(".", search_parent_directories=True).working_dir))

class IndexTide:
    """
    Helper class for callable Index related functions. Designed to power
    `DataTide` initialization routine.
    """
    @staticmethod
    def reload():
        """
        Due to the execution model of DataTide, the dataclass gets initialized 
        immediately with current index, and the class can't be updated dynamically
        with index changes.

        Calling this function hard removes the module from `sys.modules` and reimports
        it in the execution context calling the module. This is intended to be used in 
        Orchestration chains where the index has to be updated at some point between two steps,
        for example as framework elements gets updated, and should be reinjected in a later
        toolchain stage.
        """
        log("WARNING", "DataTide re-indexation")
        log("INFO", "The repository will be reindexed to update DataTide")
        del sys.modules["Engines.modules.tide"]
        from Engines.modules.tide import DataTide

    @cache #Memoization as load() is called multiple times as DataTide initializes
    @staticmethod
    def load() -> Dict[str, dict]:
        """
        Resolves the current index from a local index json or dynamically. 
        
        Once DataTide is initialized, it becomes a static object containing all
        of the Tide Instance data at the time the object is created. To update DataTide,
        call `IndexTide.reload()` to return the latest DataTide object.
        """
        EXPECTED_INDEX_PATH = ROOT / "index.json"
        INDEX_PATH = Path(os.getenv("INDEX_PATH") or EXPECTED_INDEX_PATH)

        print("📂 Index not found in memory, first seeking index file...")
        if os.path.isfile(INDEX_PATH):
            _tide_index = json.load(open(INDEX_PATH))
            _tide_index = IndexTide.reconcile_staging(_tide_index)
            return _tide_index
        else:
            # Generate index in memory
            print("💽 Could not find index file, generating it in memory")
            _tide_index = indexer()
            _tide_index = IndexTide.reconcile_staging(_tide_index)
            if not _tide_index:
                raise Exception("INDEX COULD NOT BE LOADED IN MEMORY")
            return _tide_index

    @staticmethod
    def reconcile_staging(index):
        """
        Helper function of `IndexTide.load()` designed to seek a staging index
        and dynamically reconcile in flight.
        """

        log("INFO", "Entering staging index reconciliation routine")
        EXPECTED_STAGING_INDEX_PATH = ROOT / "staging_index.json"
        STAGING_INDEX_PATH = os.getenv("STAGING_INDEX_PATH") or EXPECTED_STAGING_INDEX_PATH

        if not os.path.exists(STAGING_INDEX_PATH):
            log("SKIP", "No Staging Index to reconcile")
            return index

        RECONCILED_INDEX = index.copy()
        STG_INDEX = json.load(open(Path(STAGING_INDEX_PATH)))
        BANNER_MESSAGE = "⚠️ This documentation reflects the latest staging deployment from this MDR. Production status on mainline is, but staging deployment is currently overriding it"
        added_mdr = list()
        updated_mdr = list()

        patch = Tide2Patching()

        for mdr in STG_INDEX:
            if mdr not in RECONCILED_INDEX["models"]["mdr"]:
                log("INFO", "Patching MDR in staging index", mdr)
                RECONCILED_INDEX["models"]["mdr"][mdr] = patch.tide_1_patch(STG_INDEX[mdr], "mdr")
                added_mdr.append(mdr)
            else:
                main_mdr_metadata = (
                    RECONCILED_INDEX["models"]["mdr"][mdr].get("meta") or RECONCILED_INDEX["models"]["mdr"][mdr]["metadata"]
                )
                main_version = main_mdr_metadata["version"]
                stg_mdr_metadata = (
                    STG_INDEX[mdr].get("meta") or STG_INDEX[mdr]["metadata"]
                )
                stg_version = stg_mdr_metadata["version"]

                mdr_name = (
                    STG_INDEX[mdr].get("name")
                    or STG_INDEX[mdr]["title"].split("$")[0].strip()
                )

                if stg_version > main_version:
                    log("INFO",
                        f"🔄 Replacing MDR {mdr_name} from prod index with"
                        f" staging data, as version is higher (main : v{main_version}"
                        f" staging : v{stg_version})"
                    )

                    updated_mdr = list()

                    log("INFO", "Doing a safety patching to avoid edge cases")
                    RECONCILED_INDEX["models"]["mdr"][mdr] = patch.tide_1_patch(STG_INDEX[mdr], "mdr")
        
        log("SUCCESS", "Finalized Staging Reconciliation Routine")
        log("INFO", "Updated MDRs from Production Index with Staging Data", str(len(updated_mdr)))
        log("INFO", "New MDR added from Staging Data ", str(len(added_mdr)))
        return RECONCILED_INDEX

    @staticmethod
    def compute_chains(tvm_index: dict) -> dict:
        chain = dict()
        for tvm in (n := tvm_index):
            if "chaining" in n[tvm]["threat"]:
                if tvm not in chain:
                    chain[tvm] = dict()
                for link in n[tvm]["threat"]["chaining"]:
                    if link["relation"] not in chain[tvm]:
                        chain[tvm][link["relation"]] = []
                    if link["vector"] not in chain[tvm][link["relation"]]:
                        chain[tvm][link["relation"]].append(link["vector"])

        return chain

    @staticmethod
    def return_paths(tier: Literal["all", "core", "tide"]) -> dict[str, Path]:
        if tier == "all":
            return IndexTide.load()["paths"]
        if tier == "core":
            return IndexTide.load()["paths"]["core"]
        if tier == "tide":
            return IndexTide.load()["paths"]["tide"]

    @staticmethod
    def is_debug()->bool:
        """
        Provides an interface to discover whether the current execution
        context is considered to be in a debugging scenario.
        """
        if (
            os.environ.get("DEBUG") == True
            or os.environ.get("TERM_PROGRAM") == "vscode"
        ):
            return True
        else:
            return False


class DataTide:
    """Unified programmatic interface to access all data in the
    TIDE instance. Calling this class triggers an indexation of the
    entire repository and stores it in memory.

    DataTide execution model as a self-initializing dataclass means
    it will fetch all index data dynamically when the tide module is first
    imported in the execution environment, then freeze this state. To
    refresh DataTide, call `IndexTide.reload()` , a new DataTide object
    will be initialized. 
    """

    # Index = _retrieve_index
    """Return the raw index content"""

    Index = IndexTide.load()
    
    @dataclass(frozen=True)
    class Models:
        """TIDE Lookups Interface.

        Exposes all the configurations of the instance
        """
        Index = dict(IndexTide.load()["models"])
        """Index containing model types"""
        tvm = dict(Index["tvm"])
        """Threat Vector Models Data Index"""
        cdm = dict(Index["cdm"])
        """Cyber Detection Models Data Index"""
        mdr = dict(Index["mdr"])
        """Managed Detection Rules Data Index"""
        bdr = dict(Index["bdr"])
        """Business Detection Rules Data Index"""
        chaining = IndexTide.compute_chains(tvm)
        """Index of all chaining relationships"""
        FlatIndex =  tvm | cdm | mdr | bdr
        """Flat Key Value pair structure of all UUIDs in the index"""

    @dataclass(frozen=True)
    class Vocabularies:
        """TIDE Schema Interface.

        Exposes the vocabularies used across the instance
        """

        Index = dict(IndexTide.load()["vocabs"])

    @dataclass(frozen=True)
    class JsonSchemas:
        """
        Interface to all the JSON Schemas generated from TideS
        """

        Index = dict(IndexTide.load()["json_schemas"])
        tvm = dict(Index.get("tvm", {}))
        """Threat Vector Model JSON Schema"""
        cdm = dict(Index.get("cdm", {}))
        """Cyber Detection Model JSON Schema"""
        mdr = dict(Index.get("mdr", {}))
        """Managed Detection Rule JSON Schema"""
        bdr = dict(Index.get("bdr", {}))
        """Business Detection Request JSON Schema"""

    @dataclass(frozen=True)
    class Templates:
        """
        Interface to all the templates generated from TideSchemas
        """

        Index = dict(IndexTide.load()["templates"])
        tvm = str(Index.get("tvm"))
        """Threat Vector Model Object Template"""
        cdm = str(Index.get("cdm"))
        """Cyber Detection Model Object Template"""
        mdr = str(Index.get("mdr"))
        """Managed Detection Rule Object Template"""
        bdr = str(Index.get("bdr"))
        """Business Detection Request Object Template"""

    @dataclass(frozen=True)
    class TideSchemas:
        """TIDE Schema Interface.

        Exposes the different schemas used across the instance
        """

        Index = dict(IndexTide.load()["metaschemas"])
        subschemas = dict(IndexTide.load()["subschemas"])
        definitions = dict(IndexTide.load()["definitions"])
        templates = dict(IndexTide.load()["templates"])
        tvm = dict(Index["tvm"])
        """Threat Vector Model Tide Schema"""
        cdm = dict(Index["cdm"])
        """Cyber Detection Model Tide Schema"""
        mdr = dict(Index["mdr"])
        """Managed Detection Rule Tide Schema"""
        mdrv2 = dict(Index.get("mdrv2", {}))
        """DEPRECATED - Legacy MDR Version for backward compatibility use cases"""
        bdr = dict(Index["bdr"])
        """Business Detection Request Tide Schema"""

    @dataclass(frozen=True)
    class Lookups:
        """TIDE Lookups Interface.

        Exposes the lookups data within of the instance
        """

        lookups = dict(IndexTide.load()["lookups"]["lookups"])
        metadata = dict(IndexTide.load()["lookups"]["metadata"])

    @dataclass(frozen=True)
    class Configurations:
        Index = dict(IndexTide.load()["configurations"])
        DEBUG = IndexTide.is_debug()
        """Discovers whether the current execution context is considered
        to be a debugging one"""
        
        @dataclass(frozen=True)
        class Global:
            Index = dict(IndexTide.load()["configurations"]["global"])
            models = Index["models"]
            metaschemas = dict(Index["metaschemas"])
            recomposition = dict(Index["recomposition"])
            json_schemas = dict(Index["json_schemas"])
            data_fields = dict(Index["data_fields"])
            templates = dict(Index["templates"])

            @dataclass(frozen=True)
            class Paths:
                Index = IndexTide.return_paths(tier="all")
                _raw = dict(IndexTide.load()["paths"]["raw"])
                """Paths without the proper absolute calculation.
                Only use for specific use cases, for any others prefer
                the other attributes which are precomputed"""

                @dataclass(frozen=True)
                class Core:
                    """Paths to Tide Internals"""

                    Index = IndexTide.return_paths(tier="core")
                    _raw = dict(IndexTide.load()["paths"]["raw"]["core"])
                    """Paths without the proper absolute calculation.
                    Only use for specific use cases, for any others prefer
                    the other attributes which are precomputed"""
                    vocabularies = Index["vocabularies"]
                    configurations = Index["configurations"]
                    metaschemas = Index["configurations"]
                    subschemas = Index["subschemas"]
                    definitions = Index["definitions"]
                    wiki_docs_folder = Index["wiki_docs_folder"]
                    models_docs_folder = Index["models_docs_folder"]
                    schemas_docs_folder = Index["schemas_docs_folder"]
                    vocabularies_docs = Index["vocabularies_docs"]
                    resources = Index["resources"]

                @dataclass(frozen=True)
                class Tide:
                    """Paths to Tide Content, Models, and Artifacts at
                    the top level directory"""

                    Index = IndexTide.return_paths(tier="tide")
                    _raw = dict(IndexTide.load()["paths"]["raw"]["tide"])
                    """Paths without the proper absolute calculation.
                    Only use for specific use cases, for any others prefer
                    the other attributes which are precomputed"""
                    
                    tvm = Index["tvm"]
                    cdm = Index["cdm"]
                    mdr = Index["mdr"]
                    bdr = Index["bdr"]
                    reports = Index["reports"]
                    lookups = Index["lookups"]
                    analytics = Index["analytics"]
                    snippet_file = Index["snippet_file"]
                    json_schemas = Index["json_schemas"]
                    templates = Index["templates"]
                    tide_indexes = Index["tide_indexes"]

        @dataclass(frozen=True)
        class Systems:
            Index = dict(IndexTide.load()["configurations"]["systems"])

            @dataclass(frozen=True)
            class Splunk:
                Index = dict(IndexTide.load()["configurations"]["systems"]["splunk"])
                tide = dict(Index["tide"])
                setup = dict(Index["setup"])
                secrets = dict(Index["secrets"])
                defaults = dict(Index["defaults"])
                lookups = dict(Index.get("lookups", {}))
                modifiers = dict(Index.get("modifiers", {}))

            @dataclass(frozen=True)
            class Sentinel:
                Index = dict(IndexTide.load()["configurations"]["systems"]["sentinel"])
                tide = dict(Index["tide"])
                setup = dict(Index["setup"])
                secrets = dict(Index["secrets"])
                defaults = dict(Index["defaults"])
                lookups = dict(Index["lookups"])

            @dataclass(frozen=True)
            class CarbonBlackCloud:
                Index = dict(
                    IndexTide.load()["configurations"]["systems"]["carbon_black_cloud"]
                )
                tide = dict(Index["tide"])
                setup = dict(Index["setup"])
                secrets = dict(Index["secrets"])
                validation = dict(Index["validation"])

        @dataclass(frozen=True)
        class Documentation:
            """Parameters describing how documentation should be generated."""


            Index = dict(IndexTide.load()["configurations"]["documentation"])
            documentation_target = str(Index.get("documentation_target"))
            scope = list(Index["scope"])
            skip_model_keys = list(Index["skip_model_keys"])
            skip_vocabularies = list(Index["skip_model_keys"])
            gitlab = dict(Index.get("gitlab", {}))
            cve = dict(Index["cve"])
            wiki = dict(Index.get("wiki",{}))
            object_names = dict(Index["object_names"])
            titles = dict(Index["titles"])
            icons = dict(Index["icons"])
            models_docs_folder: Path = Path(
                IndexTide.load()["configurations"]["global"]["paths"]["core"][
                    "models_docs_folder"
                ]
            )
            models_docs_folder = (
                Path(str(models_docs_folder).replace(" ", "-"))
                if documentation_target == "gitlab"
                else models_docs_folder
            )

        @dataclass(frozen=True)
        class Resources:
            """Parameters pointing to External resources used by engines."""

            Index = dict(IndexTide.load()["configurations"]["resources"])
            attack = dict(Index["attack"])
            d3fend = dict(Index["d3fend"])
            engage = dict(Index["engage"])
            nist = dict(Index["nist"])

        @dataclass(frozen=True)
        class Deployment:
            """Generic deployment parameters."""

            Index = dict(IndexTide.load()["configurations"]["deployment"])
            status = dict(Index["status"])
            promotion = dict(Index["promotion"])
            default_responders = str(Index["default_responders"])
            proxy = dict(Index["proxy"])
            metadata_lookup = dict(Index["metadata_lookup"])
            debug = dict(Index["debug"])

        @dataclass(frozen=True)
        class Lookups:
            """Lookups feature management"""

            Index = dict(IndexTide.load()["configurations"]["lookups"])
            validation = dict(Index["validation"])

        """TIDE Configuration Interface.

        Exposes all the configurations of the instance
        """
        Index = dict(IndexTide.load()["configurations"])
        """Contains all configurations"""