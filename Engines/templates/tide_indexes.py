from typing import Literal

TIDE_INDEX_TAM = {
"description": "Internal Reference to TIDeMEC existing threat actor models",
"icon": "👹",
"name": "Threat Actors",
"model": True,
}

TIDE_INDEX_TVM = {
"description": "Internal Reference to TIDeMEC existing threat actor vectors",
"name": "Threat Vectors",
"model": True,
}

TIDE_INDEX_CDM = {
"description": "Internal Reference to TIDeMEC existing cyber detection models",
"name": "Detection Models",
"model": True,
}

TIDE_INDEX_BDR = {
"description": "Internal Reference to TIDeMEC existing Business Detection Requests",
"name": "Business Detection Requests",
"model": True,
}

TIDE_INDEX_MDR = {
"description": "Internal Reference to TIDeMEC existing Managed Detection Rules",
"name": "Detection Rules",
"model": True,
}

TIDE_INDEX_REPORT = {
"name": "Intelligence Reports",
"field": "reports",
"description": "Registry of reports uploaded to this TIDeMEC instance",
"model": True,
}

def fetch_tide_index_template(model_type:Literal["tam", "tvm","cdm", "bdr", "report"]):
    match model_type:
        case "tam":
            return  TIDE_INDEX_TAM
        case "tvm":
            return  TIDE_INDEX_TVM
        case "cdm":
            return  TIDE_INDEX_CDM
        case "bdr":
            return TIDE_INDEX_BDR
        case "mdr":
            return TIDE_INDEX_MDR
        case "report":
            return  TIDE_INDEX_REPORT
        case _:
            return {}
