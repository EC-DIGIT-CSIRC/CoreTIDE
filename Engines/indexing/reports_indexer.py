import json
import os
import git
import sys
from pathlib import Path

from pypdf import PdfReader

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logs import log
from Engines.modules.tide import DataTide

TIDE_INDEXES = DataTide.Configurations.Global.Paths.Tide.tide_indexes
REPORTS_FOLDER = DataTide.Configurations.Global.Paths.Tide.reports
REPORTS_INDEX = TIDE_INDEXES / "reports.json"
DEBUG = DataTide.Configurations.DEBUG
ICONS = DataTide.Configurations.Documentation.icons

def pdf_description(pdf: Path) -> str:

    reader = PdfReader(pdf)
    sample_text = ""
    for page_number in range(len(reader.pages)):
        current_text = reader.pages[page_number].extract_text()
        if len(current_text) > 300:
            sample_text = current_text.replace("\n", "")
            break

    if not sample_text:
        sample_text = "⚠️ Could not generate a description from the pdf content"
    return sample_text


def run():

    log("TITLE", "Generate Vocabularies from Reports")
    log("INFO", "Indexes reports and builds vocabulary of reports")
    
    EXPORT_INDENT = 0
    if DEBUG:
        EXPORT_INDENT = 4
    reports_index = dict()
    field_name = "reports"
    metadata = {
        "field": field_name,
        "icon": ICONS.get(field_name, ""),
        "name": "Intelligence Reports",
        "model": True,
        "description": "Registry of reports uploaded to this CoreTIDE instance"
    }
    entries = {}

    for report in sorted(os.listdir(REPORTS_FOLDER)):
        report_metadata = report.split(" - ")

        report_id = report_metadata[0]
        report_tlp = (
            report_metadata[1]
            .replace("TLP", "")
            .replace("[", "")
            .replace("]", "")
            .replace(" ", "")
            .strip()
            .lower()
        )
        report_name = report_metadata[2].replace(".pdf", "")
        report_description = pdf_description(REPORTS_FOLDER / report)[:500] + "..."

        report_entry = {
            "name": report_name,
            "file_name": report,
            "description": report_description,
            "tlp": report_tlp,
        }

        entries[report_id] = report_entry

    reports_index[field_name] = {}
    reports_index[field_name]["metadata"] = metadata
    reports_index[field_name]["entries"] = entries

    with open(TIDE_INDEXES/(field_name + ".json"), "w+", encoding="utf-8") as export:
        json.dump(reports_index, export, indent=EXPORT_INDENT)

if __name__ == "__main__":
    run()
