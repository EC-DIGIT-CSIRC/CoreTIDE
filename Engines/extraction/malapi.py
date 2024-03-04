import requests
from bs4 import BeautifulSoup
import pandas as pd
import yaml
from pathlib import Path
import os
import git
import sys
from datetime import datetime


sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logs import log
from Engines.modules.tide import DataTide


class IndentFullDumper(yaml.Dumper):

    def increase_indent(self, flow=False, indentless=False):
        return super(IndentFullDumper, self).increase_indent(flow, False)


DEBUG = False

VOCAB_FILE_PATH = Path(
    DataTide.Configurations.Global.Paths.Core.vocabularies / "MalAPI.yaml"
)

API_DETAILS_FIELD_MAPPING = {
    "Function Name": "name",
    "Description": "description",
    "Library": "library",
    "Associated Attacks": "tide.vocab.stages",
    "Documentation": "link",
}

STAGE_ICON_MAPPING = {
    "Enumeration": "📟",
    "Injection": "💉",
    "Evasion": "🏃‍♂️",
    "Spying": "🥸",
    "Internet": "🌐",
    "Anti-Debugging": "🐞",
    "Ransomware": "🔐",
    "Helper": "🤝",
}

MALAPI_URL = "https://malapi.io"

start_time = datetime.now()


def fetch_win_api_details(api):

    log("INFO", "Fetching API Details", api)
    url = MALAPI_URL + "/winapi/" + api
    # Create object page
    try:
        page = requests.get(url)
        soup = BeautifulSoup(page.text, "html.parser")
    except Exception as e:
        log("FAILURE", "Failed to retrieve details for", api)
        raise e

    details = {}
    details_page = soup.find_all("div", {"class": "detail-container"})
    for detail in details_page:
        detail_name = detail.find("div", attrs={"class": "heading"})
        detail_data = detail.find("div", attrs={"class": "content"})

        if detail_name:
            detail_name = detail_name.text.strip()
            detail_name = API_DETAILS_FIELD_MAPPING[detail_name]
            if detail_data:
                detail_data = detail_data.text.strip()
                details[detail_name] = detail_data

    if details.get("library"):
        details["description"] += f"\nLibrary : `{details.pop('library')}`"

    if details.get("stage"):
        stage_data = details.pop("tide.vocab.stages")
        stage_data = stage_data.replace("\n\n", ",")
        stage_data = stage_data.replace("\n", "").replace(" ", "")
        if "," in stage_data:
            stage_data = stage_data.split(",")
        details["stage"] = stage_data

    if not details:
        log("FAILURE", "Error in parsing, no data returned", api)
        raise ValueError("Empty parsed API")

    if DEBUG:
        log("DEBUG", str(details))
    return details


# Extract headers with details
log("ONGOING", "Fetching MalAPI attacks category details")
attacks = list()
page = requests.get(MALAPI_URL)
soup = BeautifulSoup(page.text, "lxml")
table = soup.find("table", id="main-table")
for i in table.find_all("th"):  # type: ignore
    title = i.text.strip()
    description = i.find("img")["title"].strip()
    entry = dict()
    entry["name"] = title
    entry["icon"] = STAGE_ICON_MAPPING[title]
    entry["description"] = description
    attacks.append(entry)
attacks_list = [a["name"] for a in attacks]

log("SUCCESS", "Retrieved all attacks detailed", ", ".join(attacks_list))

rows = list()
api_list = list()

for j in table.find_all("tr")[1:]:  # type: ignore
    row_data = j.find_all("tbody")
    for row in row_data:
        row_values = []
        a_class = row.find_all("a")
        for a in a_class:
            row_values.append(a.text.strip())

        if row_values:
            rows.append(row_values)
            api_list.extend(row_values)

# Generating a dataframe similar to the frontpage of malapi.io
df = pd.DataFrame(data=rows).transpose()
df.columns = list(attacks_list)

# Deduplicate as same api can be in different attacks (equivalent to tactic, stage...)
api_list = list(set(api_list))
malapi_content = list()

log("ONGOING", "Fetching all API Details")
for api in sorted(api_list):
    malapi_content.append(fetch_win_api_details(api))

time_elapsed = datetime.now() - start_time
time_elapsed = "%.2f" % time_elapsed.total_seconds()

log(
    "SUCCESS",
    "Successfully retrieved",
    f"{len(malapi_content)} APIs",
    f"in {time_elapsed} seconds",
)

vocab_content = {
    "name": "Malicious Window API",
    "field": "malapi",
    "description": "MalAPI.io maps Windows APIs to common techniques used by malware.",
    "reference": MALAPI_URL,
    "icon": "🎭",
    "stages": attacks,
    "keys": malapi_content,
}

log("ONGOING", "Writing to file at location", str(VOCAB_FILE_PATH))
with open(VOCAB_FILE_PATH, encoding="utf-8", mode="w+") as vocab:
    yaml.dump(
        vocab_content,
        vocab,
        sort_keys=False,
        allow_unicode=True,
        Dumper=IndentFullDumper,
    )

log("SUCCESS", "Wrote to vocabulary file")
