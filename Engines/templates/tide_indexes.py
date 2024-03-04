from typing import Literal

TIDE_INDEX_TAM = {
"description": "Internal Reference to TIDeMEC existing threat actor models",
"icon": "👹",
"name": "Threat Actors",
"field": "actors",
"model": True,
"keys": []
}

TIDE_INDEX_TVM = {
"description": "Internal Reference to TIDeMEC existing threat actor vectors",
"icon": "☣️",
"name": "Threat Vectors",
"field": "vectors",
"model": True,
"keys": []
}

TIDE_INDEX_CDM = {
"description": "Internal Reference to TIDeMEC existing cyber detection models",
"icon": "🛡️",
"name": "Cyber Detection Models",
"field": "detection_model",
"model": True,
"keys": []
}

TIDE_INDEX_REPORT = {
"name": "Intelligence Reports",
"field": "reports",
"description": "Registry of reports uploaded to this TIDeMEC instance",
"icon": "💡",
"model": True,
"keys": []
}

def fetch_tide_index_template(model_type:Literal["tam", "tvm","cdm", "bdr", "report"]):
    match model_type:
        case "tam":
            return  TIDE_INDEX_TAM
        case "tvm":
            return  TIDE_INDEX_TVM
        case "cdm":
            return  TIDE_INDEX_CDM
        case "report":
            return  TIDE_INDEX_REPORT