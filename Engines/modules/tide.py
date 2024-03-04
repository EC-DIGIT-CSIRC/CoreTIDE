import os
import git
import sys
from pathlib import Path
import json
from typing import Literal, Dict, Tuple

from dataclasses import dataclass

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.indexing.indexer import indexer
from Engines.modules.logs import log
from Engines.modules.files import resolve_paths

ROOT = Path(str(git.Repo(".", search_parent_directories=True).working_dir))


@dataclass
class IndexTide:
    """
    Common helper class to retrieve the Tide Index
    """

    Index = dict()
    EXPECTED_INDEX_PATH = ROOT / "index.json"
    INDEX_PATH = Path(os.getenv("INDEX_PATH") or EXPECTED_INDEX_PATH)

    def __post_init__(self):
        self.Index = self._cache_index()

    def _cache_index(self, reset=False, reconcile_staging=False) -> Dict[str, dict]:
        """
        To ensure that we are not reindexing the repository on every call
        to the index, `_cache_index()` uses a global variable `TIDE_INDEX`to preserve
        state, as a form or memoization.

        The state of the repo will usually not change across most operations,
        but passing `reset=True` will reindex the repository imperatively.
        """

        if "TIDE_INDEX" in globals().keys():
            if reset:  # Regenerate the index
                NEW_INDEX = indexer()

                if reconcile_staging:
                    log(
                        "INFO",
                        "Initializing reconciliation routine after regenerating the index",
                    )
                    NEW_INDEX = IndexUtils.reconcile_staging(NEW_INDEX)

                globals()["TIDE_INDEX"] = NEW_INDEX

            if reconcile_staging:
                log("INFO", "Initializing reconciliation routine on existing index")
                globals()["TIDEINDEX"] = IndexUtils.reconcile_staging(
                    globals()["TIDE_INDEX"]
                )

            return globals()["TIDE_INDEX"]

        global TIDE_INDEX  # INDEX will be written to the global scope
        print("📂 Index not found in memory, first seeking index file...")
        if os.path.isfile(self.INDEX_PATH):
            TIDE_INDEX = json.load(open(self.INDEX_PATH))
            if reconcile_staging:
                log("INFO", "Initializing reconciliation routine for new index")
                TIDE_INDEX = IndexUtils.reconcile_staging(TIDE_INDEX)
            return TIDE_INDEX
        else:
            # Generate index in memory
            print("💽 Could not find index file, generating it in memory")
            TIDE_INDEX = indexer()
            if reconcile_staging:
                TIDE_INDEX = IndexUtils.reconcile_staging(TIDE_INDEX)
            if not TIDE_INDEX:
                raise Exception("INDEX COULD NOT BE LOADED IN MEMORY")
            return TIDE_INDEX


class IndexUtils:

    @staticmethod
    def reconcile_staging(index):
        log("INFO", "Entering staging index reconciliation routine")
        EXPECTED_STAGING_INDEX_PATH = ROOT / "stg_index.json"
        STAGING_INDEX_PATH = os.getenv("STG_INDEX_PATH") or EXPECTED_STAGING_INDEX_PATH

        if not os.path.exists(STAGING_INDEX_PATH):
            log("SKIP", "No Staging Index to reconcile")
            return index

        RECONCILED_INDEX = index.copy()
        STG_INDEX = json.load(open(Path(STAGING_INDEX_PATH)))
        MDR_INDEX = RECONCILED_INDEX
        BANNER_MESSAGE = "⚠️ This documentation reflects the latest staging deployment from this MDR. Production status on mainline is, but staging deployment is currently overriding it"

        for mdr in STG_INDEX:
            if mdr not in MDR_INDEX:
                MDR_INDEX[mdr] = STG_INDEX[mdr]

            else:
                main_mdr_metadata = (
                    MDR_INDEX[mdr].get("meta") or MDR_INDEX[mdr]["metadata"]
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
                    print(
                        f"🔄 Replacing MDR {mdr_name} from prod index with"
                        f" staging data, as version is higher (main : v{main_version}"
                        f" staging : v{stg_version})"
                    )

                    MDR_INDEX[mdr] = STG_INDEX[mdr]
                    if MDR_INDEX[mdr].get("meta"):
                        MDR_INDEX[mdr]["metadata"] = MDR_INDEX[mdr].pop(
                            "meta"
                        )  # Renaming meta to metadata in the fly to accomodate renaming
                    global TIDE_MDR_STAGING_BANNER
                    TIDE_MDR_STAGING_BANNER = dict()
                    TIDE_MDR_STAGING_BANNER[mdr] = BANNER_MESSAGE.format(**locals())

        return RECONCILED_INDEX

    @staticmethod
    def compute_doc_target() -> Tuple[Literal["GLFM", "MARKDOWN"], bool, bool]:
        if (glfm := os.environ.get("DOCUMENTATION_TYPE")) == "GLFM":
            documentation_type = glfm
            raw_md_doc_target = False
            glfm_doc_targvet = True
            print("🦊 Configured to use Gitlab Flavored Markdown")

        else:
            documentation_type = "MARKDOWN"
            raw_md_doc_target = True
            glfm_doc_target = False

        return documentation_type, glfm_doc_target, raw_md_doc_target

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
            return IndexTide().Index["paths"]
        if tier == "core":
            return IndexTide().Index["paths"]["core"]
        if tier == "tide":
            return IndexTide().Index["paths"]["tide"]


@dataclass(frozen=True)
class DataTide:
    """Unified programmatic interface to access all data in the
    TIDE instance. Calling this class triggers an indexation of the
    entire repository and stores it in memory.

    If the index is already in memory, will directly access this
    object to maintain high performances.
    """

    # Index = _retrieve_index
    """Return the raw index content"""

    Index = IndexTide().Index

    @dataclass(frozen=True)
    class Models:
        """TIDE Lookups Interface.

        Exposes all the configurations of the instance
        """

        Index = dict(IndexTide().Index["models"])
        """All Models Data Index"""
        tam = dict(Index["tam"])
        """Threat Actor Models Data Index"""
        tvm = dict(Index["tvm"])
        """Threat Vector Models Data Index"""
        cdm = dict(Index["cdm"])
        """Cyber Detection Models Data Index"""
        mdr = dict(Index["mdr"])
        """Managed Detection Rules Data Index"""
        bdr = dict(Index["bdr"])
        """Business Detection Rules Data Index"""
        chaining = IndexUtils.compute_chains(tvm)
        """Index of all chaining relationships"""

    @dataclass(frozen=True)
    class Vocabularies:
        """TIDE Schema Interface.

        Exposes the vocabularies used across the instance
        """

        Index = dict(IndexTide().Index["vocabs"])

    @dataclass(frozen=True)
    class JsonSchemas:
        """
        Interface to all the JSON Schemas generated from TideS
        """

        Index = dict(IndexTide().Index["json_schemas"])
        tam = dict(Index.get("tam", {}))
        """Threat Actor Model JSON Schema"""
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

        Index = dict(IndexTide().Index["templates"])
        tam = str(Index.get("tam"))
        """Threat Actor Model Object Template"""
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

        Index = dict(IndexTide().Index["metaschemas"])
        subschemas = dict(IndexTide().Index["subschemas"])
        definitions = dict(IndexTide().Index["definitions"])
        templates = dict(IndexTide().Index["templates"])
        tam = dict(Index["tam"])
        """Threat Actor Model Tide Schema"""
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

        lookups = dict(IndexTide().Index["lookups"]["lookups"])
        metadata = dict(IndexTide().Index["lookups"]["metadata"])

    @dataclass(frozen=True)
    class Configurations:
        Index = dict(IndexTide().Index["configurations"])

        @dataclass(frozen=True)
        class Global:
            Index = dict(IndexTide().Index["configurations"]["global"])
            models = Index["models"]
            metaschemas = dict(Index["metaschemas"])
            recomposition = dict(Index["recomposition"])
            json_schemas = dict(Index["json_schemas"])
            datafields = dict(Index["datafields"])
            templates = dict(Index["templates"])
            models_vocabularies = dict(Index["models_vocabularies"])

            @dataclass(frozen=True)
            class Paths:
                Index = IndexUtils.return_paths(tier="all")
                _raw = dict(IndexTide().Index["paths"]["raw"])
                """Paths without the proper absolute calculation.
                Only use for specific use cases, for any others prefer
                the other attributes which are precomputed"""

                @dataclass(frozen=True)
                class Core:
                    """Paths to Tide Internals"""

                    Index = IndexUtils.return_paths(tier="core")
                    _raw = dict(IndexTide().Index["paths"]["raw"]["core"])
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
                    lookup_docs = Index["lookup_docs"]
                    schemas_docs_folder = Index["schemas_docs_folder"]
                    vocabularies_docs = Index["vocabularies_docs"]
                    resources = Index["resources"]

                @dataclass(frozen=True)
                class Tide:
                    """Paths to Tide Content, Models, and Artifacts at
                    the top level directory"""

                    Index = IndexUtils.return_paths(tier="tide")
                    _raw = dict(IndexTide().Index["paths"]["raw"]["tide"])
                    """Paths without the proper absolute calculation.
                    Only use for specific use cases, for any others prefer
                    the other attributes which are precomputed"""
                    
                    tam = Index["tam"]
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

        @dataclass(frozen=True)
        class Systems:
            Index = dict(IndexTide().Index["configurations"]["systems"])

            @dataclass(frozen=True)
            class Splunk:
                Index = dict(IndexTide().Index["configurations"]["systems"]["splunk"])
                tide = dict(Index["tide"])
                setup = dict(Index["setup"])
                secrets = dict(Index["secrets"])
                defaults = dict(Index["defaults"])
                lookups = dict(Index["lookups"])

            @dataclass(frozen=True)
            class Sentinel:
                Index = dict(IndexTide().Index["configurations"]["systems"]["sentinel"])
                tide = dict(Index["tide"])
                setup = dict(Index["setup"])
                secrets = dict(Index["secrets"])
                defaults = dict(Index["defaults"])
                lookups = dict(Index["lookups"])

            @dataclass(frozen=True)
            class CarbonBlackCloud:
                Index = dict(
                    IndexTide().Index["configurations"]["systems"]["carbon_black_cloud"]
                )
                tide = dict(Index["tide"])
                setup = dict(Index["setup"])
                secrets = dict(Index["secrets"])

        @dataclass(frozen=True)
        class Documentation:
            """Parameters describing how documentation should be generated."""

            Index = dict(IndexTide().Index["configurations"]["documentation"])
            scope = list(Index["scope"])
            skip_model_keys = list(Index["skip_model_keys"])
            skip_vocabularies = list(Index["skip_model_keys"])
            cve = dict(Index["cve"])
            wiki = dict(Index.get("wiki"))
            object_names = dict(Index["object_names"])
            titles = dict(Index["titles"])
            icons = dict(Index["icons"])
            indexes = dict(Index["indexes"])
            (documentation_type, glfm_doc_target, raw_md_doc_target) = (
                IndexUtils.compute_doc_target()
            )
            models_docs_folder: Path = Path(
                IndexTide().Index["configurations"]["global"]["paths"]["core"][
                    "models_docs_folder"
                ]
            )
            models_docs_folder = (
                Path(str(models_docs_folder).replace(" ", "-"))
                if glfm_doc_target
                else models_docs_folder
            )

        @dataclass(frozen=True)
        class Resources:
            """Parameters pointing to External resources used by engines."""

            Index = dict(IndexTide().Index["configurations"]["resources"])
            attack = dict(Index["attack"])
            d3fend = dict(Index["d3fend"])
            engage = dict(Index["engage"])
            nist = dict(Index["nist"])

        @dataclass(frozen=True)
        class Deployment:
            """Generic deployment parameters."""

            Index = dict(IndexTide().Index["configurations"]["deployment"])
            status = dict(Index["status"])
            promotion = dict(Index["promotion"])
            default_responders = str(Index["default_responders"])
            proxy = dict(Index["proxy"])
            metadata_lookup = dict(Index["metadata_lookup"])

        @dataclass(frozen=True)
        class Lookups:
            """Lookups feature management"""

            Index = dict(IndexTide().Index["configurations"]["lookups"])
            validation = dict(Index["validation"])

        """TIDE Configuration Interface.

        Exposes all the configurations of the instance
        """
        Index = dict(IndexTide().Index["configurations"])
        """Contains all configurations"""
