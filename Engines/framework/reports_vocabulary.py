import yaml
import os
import git
import sys
from pathlib import Path

from pypdf import PdfReader

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logs import log
from Engines.modules.tide import DataTide

VOCABS_PATH = DataTide.Configurations.Global.paths["vocabularies"]
REPORTS_FOLDER = Path(DataTide.Configurations.Global.paths["reports"])
REPORTS_VOCAB = Path(VOCABS_PATH) / "Reports.yaml"

class IndentFullDumper(yaml.Dumper):

    def increase_indent(self, flow=False, indentless=False):
        return super(IndentFullDumper, self).increase_indent(flow, False)


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
    
    report_index = list()
    
    for report in sorted(os.listdir(REPORTS_FOLDER)):
        metadata = report.split(" - ")

        report_id = metadata[0]
        report_tlp = (
            metadata[1]
            .replace("TLP", "")
            .replace("[", "")
            .replace("]", "")
            .replace(" ", "")
            .strip()
            .lower()
        )
        report_name = metadata[2].replace(".pdf", "")
        report_description = pdf_description(REPORTS_FOLDER / report)[:500] + "..."

        report_entry = {
            "id": report_id,
            "name": report_name,
            "file_name": report,
            "description": report_description,
            "tlp": report_tlp,
        }

        report_index.append(report_entry)

    print(report_index)

    content = yaml.safe_load(open(REPORTS_VOCAB, "r", encoding="utf-8"))
    content["keys"] = report_index
    with open(REPORTS_VOCAB, "w+", encoding="utf-8") as export:
        yaml.dump(
            content,
            export,
            sort_keys=False,
            Dumper=IndentFullDumper,
            allow_unicode=True,
        )


if __name__ == "__main__":
    run()
