import os
import git
import shutil
import toml
from pathlib import Path
from ruamel.yaml import YAML

yaml = YAML()
yaml.indent(mapping=2, sequence=4, offset=2)

ROOT = Path(str(git.Repo(".", search_parent_directories=True).working_dir))

CONFIG = toml.load(open(ROOT / "Configurations/global.toml", encoding="utf-8"))
MDR_FOLDER = ROOT / CONFIG["paths"]["tide"]["mdr"]
MDR_LEGACY_FOLDER = ROOT / CONFIG["paths"]["tide"]["mdrv2"]
TEMPLATES_PATH = ROOT / CONFIG["paths"]["core"]["templates"]

MDR_TEMPLATE = yaml.load(open(TEMPLATES_PATH / "MDR TEMPLATE.yaml", encoding="utf-8"))

SUB_TEMPLATES_PATH = (
    ROOT
    / CONFIG["paths"]["core"]["subschemas"]
    / CONFIG["artifacts"]["recomposition"]["systems"]
    / "Templates"
)

SPLUNK_IDENTIFIER = "splunk"
SENTINEL_IDENTIFIER = "sentinel"
CBC_IDENTIFIER = "carbonblackcloud"

SYSTEMS_SCOPE = [SPLUNK_IDENTIFIER, SENTINEL_IDENTIFIER, CBC_IDENTIFIER]

TOKEN_SPACES = [
    "meta",
    "description",
    "response",
    "configurations",
    "throttling",
    "scheduling",
    "notable",
    "query",
    "sentinel",
    "splunk",
    "carbon_black_cloud",
]

TOKEN_COMMENTS = ["contributors", "cron", "watchlist", "tags"]

SPLUNK_COMMENTED_TEMPLATE = """
    #drilldown:
      #name: 
      #search: |
        #Type Here
  
    #security_domain: 
"""

SENTINEL_COMMENTED_TEMPLATE = """
    #alert:
        #title: 
        #description: 
        #custom_details:
        #- key: 
            #value: 
    
    #grouping:
        #event: SingleAlert
        #alert:
        #enabled: true
        #grouping_lookback: 5h
        #matching: 
    
    #entities:
        #- entity: 
        #mappings:
            #- identifier: 
            #column: 
"""


def replace_strings_in_file(file_path, strings, replacement):
    file = open(file_path, "r", encoding="utf-8")
    buffer = []
    for line in file:
        for word in strings:
            if word in line:
                line = line.replace(word, replacement)
        buffer.append(line)
    file.close()
    file = open(file_path, "w", encoding="utf-8")
    for line in buffer:
        file.write(line)
    file.close()
    return True


TEMPLATES_SYSTEMS = dict()

# for s in CONFIG["systems"]:
#    identifier = s["identifier"]
#    if identifier in SYSTEMS_SCOPE:
#        template_path = SUB_TEMPLATES_PATH / (s["name"] + " Template.yaml")
#        TEMPLATES_SYSTEMS[identifier] = yaml.load(open(template_path, encoding='utf-8'))

STATUS_MAPPING = {
    "1-SELECTED": "",
    "2-DESIGN": "DESIGN",
    "3-DEV": "DEVELOPMENT",
    "4-IMPROVING": "IMPROVING",
    "5-STAGING": "STAGING",
    "6-PRODUCTION": "PRODUCTION",
    "7-UNDER REVIEW": "REVIEWING",
    "8-DISABLED": "DISABLED",
    "9-REMOVED": "REMOVED",
}

SEVERITY_MAPPING = {
    1: "Informational",
    2: "Informational",
    3: "Low",
    4: "Low",
    5: "Low",
    6: "Medium",
    7: "Medium",
    8: "High",
    9: "High",
    10: "Critical",
}


def make_comments(file_path: Path, tokens: list) -> bool:

    file = open(file_path, "r", encoding="utf-8").readlines()
    commented = []

    for line in file:
        key = line.split(":")[0].strip()
        if key in tokens:
            commented.append(line.replace(key, ("#" + key)))
        elif "- blank" in line:
            commented.append(line.replace("- blank", "#-"))
        elif "blank" in line:
            commented.append(line.replace("blank", ""))
        else:
            commented.append(line)

    file = open(file_path, "w", encoding="utf-8")
    for s in commented:
        file.write(s)

    return True


def token_space(file_path: Path, tokens: list) -> bool:

    file = open(file_path, "r", encoding="utf-8").readlines()
    spaced = []

    for line in file:
        if line != "\n":
            key = line.split(":")[0].strip()
            if key in tokens:
                spaced.append("\n")

            spaced.append(line)

    file = open(file_path, "w", encoding="utf-8")
    for s in spaced:
        file.write(s)

    return True


def mdr_migrator(mdrv2):

    mdrv3 = dict()
    dynamic_comments = []

    queries = dict()
    throttling_fields = list()

    systems_scope = mdrv2["rule"]["alert"].keys()
    status = STATUS_MAPPING[mdrv2["status"]]

    for sys in systems_scope:
        queries[sys] = mdrv2["rule"]["alert"][sys]

    detection_model = mdrv2.get("tags", {}).get("tidemec")
    playbook = mdrv2.get("tags", {}).get("playbook")
    responders = mdrv2.get("tags", {}).get("alert_handling_team")

    # MDRv2 Alert Parameters
    scheduling = mdrv2["rule"].get("scheduling")
    timeframe = mdrv2["rule"].get("timeframe")
    throttling = mdrv2["rule"].get("throttling")
    threshold = mdrv2["rule"].get("threshold")
    fields = mdrv2["rule"].get("fields", {}).get("splunk")

    if fields:
        for f in fields:
            throttling_fields.append(f.replace("*", ""))

    # Generic Data Mapping
    old_title = mdrv2["title"]
    mdrv3["name"] = old_title.split("$")[0].strip()
    mdrv3["uuid"] = mdrv2["uuid"]
    if mdrv2.get("references"):
        mdrv3["references"] = mdrv2.get("references")
    else:
        mdrv3["references"] = ["blank"]
        dynamic_comments.append("references")
    severity = SEVERITY_MAPPING[mdrv2["priority"]]
    mdrv3["meta"] = mdrv2["meta"]
    if "splunk" in mdrv3["meta"]:
        del mdrv3["meta"]["splunk"]
    # Round version to integer as float was allowed prior
    mdrv3["meta"]["version"] = round(mdrv2.copy()["meta"]["version"])
    mdrv3["description"] = mdrv2["rule"]["description"]

    # TIDeMEC Parent Mapping
    if detection_model:
        mdrv3["detection_model"] = detection_model
    else:
        mdrv3["detection_model"] = "blank"
        dynamic_comments.append("detection_model")

    # New Response Field Mapping
    mdrv3["response"] = {
        "alert_severity": severity,
        "playbook": str(),
        "responders": str(),
    }

    if playbook:
        mdrv3["response"]["playbook"] = playbook
    else:
        mdrv3["response"]["playbook"] = "blank"
        dynamic_comments.append("playbook")

    if responders:
        mdrv3["response"]["responders"] = responders
    else:
        mdrv3["response"]["responders"] = "blank"
        dynamic_comments.append("responders")

    mdrv3["configurations"] = {}

    for sys in SYSTEMS_SCOPE:
        if sys not in systems_scope:
            mdrv3["configurations"][sys] = "blank"
            dynamic_comments.append(sys)

    if "splunk" in systems_scope:
        splunk_config = dict()
        splunk_config["status"] = status
        splunk_config["contributors"] = ["blank"]
        if threshold:
            splunk_config["threshold"] = 0
        else:
            splunk_config["threshold"] = "blank"
            dynamic_comments.append("threshold")

        if throttling:
            splunk_config["throttling"] = {}
            splunk_config["throttling"]["duration"] = throttling
            if throttling_fields != []:
                splunk_config["throttling"]["fields"] = throttling_fields
            else:
                splunk_config["throttling"]["fields"] = ["blank"]
                dynamic_comments.append("fields")
        else:
            dynamic_comments.append("throttling")
            dynamic_comments.append("duration")

        if scheduling == "24h":
            scheduling = "1d"
        if scheduling == "48h":
            scheduling = "2d"
        if scheduling == "72h":
            scheduling = "3d"
        if scheduling == "72h":
            scheduling = "7d"
        if scheduling == "168h":
            scheduling = "7d"
        if scheduling == "336h":
            scheduling = "14d"
        if scheduling == "720h":
            scheduling = "30d"

        splunk_config["scheduling"] = {}
        splunk_config["scheduling"]["cron"] = "blank"
        splunk_config["scheduling"]["frequency"] = scheduling

        if not timeframe:
            timeframe = scheduling

        splunk_config["scheduling"]["lookback"] = timeframe
        splunk_config["notable"] = {
            "event": {"title": "blank", "notable.description": "blank"},
            "insert": "splunk",
        }

        if "$" in old_title:
            splunk_config["notable"]["event"]["title"] = old_title

        else:
            dynamic_comments.append("event")
            dynamic_comments.append("notable")
            dynamic_comments.append("title")

        splunk_config["query"] = queries["splunk"]

        mdrv3["configurations"]["splunk"] = splunk_config

    if "sentinel" in systems_scope:
        sentinel_config = dict()
        sentinel_config["status"] = status
        sentinel_config["contributors"] = ["blank"]
        if threshold:
            sentinel_config["threshold"] = 0
        else:
            sentinel_config["threshold"] = "blank"
            dynamic_comments.append("threshold")

        sentinel_config["scheduling"] = {}
        sentinel_config["scheduling"]["frequency"] = scheduling
        sentinel_config["scheduling"]["lookback"] = timeframe

        sentinel_config["insert"] = "sentinel"

        sentinel_config["query"] = queries["sentinel"]

        mdrv3["configurations"]["sentinel"] = sentinel_config

    if "carbonblackcloud" in systems_scope:
        cbc_config = dict()
        cbc_config["status"] = status
        cbc_config["contributors"] = ["blank"]

        cbc_config["watchlist"] = "blank"
        cbc_config["tags"] = ["blank"]

        cbc_config["query"] = queries["carbonblackcloud"]

        mdrv3["configurations"]["carbon_black_cloud"] = cbc_config

    return mdrv3, dynamic_comments


### Older MR will still merge into the older path, so we should transfer the file to the
### new one before running the migration


if os.path.isdir(MDR_LEGACY_FOLDER):
    for file in os.listdir(MDR_LEGACY_FOLDER):
        if not os.path.isdir(MDR_LEGACY_FOLDER / file):
            if not file.endswith("TEMPLATE.yaml"):
                migrated_file_path = MDR_FOLDER / file
                file_path = MDR_LEGACY_FOLDER / file
                body = yaml.load(open(file_path, encoding="utf-8"))

                print(f"Currently migrating {file}...")

                if "configurations" not in body.keys():
                    mdr, dynamic_comments = mdr_migrator(body)

                    with open(migrated_file_path, "w+", encoding="utf-8") as output:
                        yaml.dump(mdr, output)

                    replace_strings_in_file(
                        migrated_file_path, ["notable.description:"], "#description:"
                    )
                    replace_strings_in_file(
                        migrated_file_path, ["query: |-"], "query: |"
                    )
                    replace_strings_in_file(
                        migrated_file_path, ["description: |-"], "description: |"
                    )
                    replace_strings_in_file(
                        migrated_file_path,
                        ["insert: splunk"],
                        SPLUNK_COMMENTED_TEMPLATE,
                    )
                    replace_strings_in_file(
                        migrated_file_path,
                        ["insert: sentinel"],
                        SENTINEL_COMMENTED_TEMPLATE,
                    )
                    replace_strings_in_file(migrated_file_path, ["#logsources:"], "")

                    token_space(migrated_file_path, TOKEN_SPACES)
                    make_comments(migrated_file_path, TOKEN_COMMENTS)
                    make_comments(migrated_file_path, dynamic_comments)

    # Once all file have been migrated, remove folder to avoid confusion
    shutil.rmtree(MDR_LEGACY_FOLDER)
