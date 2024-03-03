import os
from pathlib import Path
import sys
import time
import git

start_time = time.time()


sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.framework import get_type, model_value
from Engines.modules.documentation import (
    get_icon,
    backlink_resolver,
    get_vocab_description,
    get_field_title,
)
from Engines.modules.files import safe_file_name
from Engines.templates.mdr import TEMPLATEv2 as TEMPLATE
from Engines.modules.logs import log
from Engines.modules.tide import DataTide

ROOT = Path(str(git.Repo(".", search_parent_directories=True).working_dir))
DOCUMENTATION_CONFIGURATION = DataTide.Configurations.Documentation
DOCUMENTATION_TYPE = DOCUMENTATION_CONFIGURATION.documentation_type
DEFAULT_RESPONDERS = DataTide.Configurations.Deployment.default_responders
SYSTEMS_CONFIG = DataTide.Configurations.Systems.Index
VOCAB_INDEX = DataTide.Vocabularies.Index
MODELS_INDEX = DataTide.Models.Index
MDR_ICON = get_icon("mdr")
GLFM = DataTide.Configurations.Documentation.glfm_doc_target
ICONS = DOCUMENTATION_CONFIGURATION.icons

MDR_WIKI_PATH = (
    ROOT
    / DOCUMENTATION_CONFIGURATION.models_docs_folder
    / DOCUMENTATION_CONFIGURATION.object_names["mdr"]
)


if GLFM:
    MDR_WIKI_PATH = Path(str(MDR_WIKI_PATH).replace(" ", "-"))
    print("🦊 Configured to use Gitlab Flavored Markdown")


def gen_documentation(model_body, metaschema):

    if not GLFM:
        frontmatter_type = DOCUMENTATION_CONFIGURATION.object_names["mdr"]
        frontmatter = f"---\ntype: {frontmatter_type}\n---"
    else:
        frontmatter = ""

    title = ICONS["mdr"] + " " + model_body["title"].split("$")[0]

    references = model_body.get("references") or ""
    if references != "":
        references = "- " + "\n- ".join(references)
    else:
        references = "_No references mentioned_"

    if "tlp" not in model_body["meta"].keys():
        tlp = "No applicable TLP for this object"
        if GLFM:
            tlp = f"[+{tlp}+]"

    else:
        tlp_icon = get_icon("tlp")
        tlp_data = model_body["meta"]["tlp"]
        tlp_rating_icon = get_icon(tlp_data, vocab="tlp")
        tlp_description = get_vocab_description("tlp", tlp_data)
        tlp = f"{tlp_icon} **TLP:{tlp_data.upper()}** {tlp_rating_icon} : {tlp_description}"

    template = TEMPLATE
    status_field = get_field_title("status", metaschema)
    status_value = model_body["status"]
    status = f"**{status_field}** : {get_icon(status_value, vocab='status')} `{status_value}`"
    uuid = f"{get_icon('uuid')} **UUID** : `{model_body['uuid']}`"

    priority = f"{get_icon('priority')}**Priority** : `{model_body['priority']}`"
    parent = model_body.get("tags", {}).get("detection_model")
    description = model_body["rule"]["description"]

    if parent is None:
        detectionmodel = "No CDMs Created Yet"
        if GLFM:
            detectionmodel = f"[-{detectionmodel}-]"

    elif status in ["8-DISABLED", "9-REMOVED"]:
        detectionmodel = backlink_resolver(parent)
    else:
        detectionmodel = backlink_resolver(parent)

    responders_data = (
        model_body.get("response", {}).get("responders") or DEFAULT_RESPONDERS
    )
    if responders_data:
        responders_description = get_vocab_description("responders", responders_data)
        responders = f"**{responders_data}** : {responders_description}"
    else:
        responders = f"**No defined responders**"
    playbook = model_body.get("tags", {}).get("playbook")
    if not playbook:
        playbook = "No playbook was defined for this detection rule"
        if GLFM:
            playbook = f"[-{playbook}-]"

    scheduling_field = get_field_title("scheduling", metaschema)
    scheduling_value = model_body["rule"]["scheduling"]
    scheduling = f"_{scheduling_field}_ : {scheduling_value}"

    falsepositives = model_body["rule"].get("falsepositives") or ""
    if falsepositives != "":
        falsepositives_field = get_field_title("falsepositives", metaschema)
        falsepositives = f"\n### {falsepositives_field} : \n\n>{falsepositives}"

    throttling = model_body["rule"].get("throttling") or ""
    if throttling != "":
        throttling_field = get_field_title("throttling", metaschema)
        throttling = f"_{throttling_field}_ : {throttling}"

    threshold = model_body["rule"].get("threshold") or ""
    if threshold != "":
        threshold_field = get_field_title("threshold", metaschema)
        threshold = f"_{threshold_field}_ : {threshold}"

    timeframe = model_body["rule"].get("timeframe") or ""
    if timeframe != "":
        timeframe_field = get_field_title("timeframe", metaschema)
        timeframe = f"_{timeframe_field}_ : {timeframe}"

    fields = ""
    logsources = ""

    if "logsources" in model_body.keys():
        for system in model_body["logsources"]:
            ls = model_body["logsources"][system]
            if ls != [None]:
                logsourcetitle = metaschema["logsources"]["properties"][system]["title"]
                logsources += f"\n\n _{logsourcetitle} :_ {', '.join(ls)} "

    if "fields" in model_body["rule"].keys():
        for system in model_body["rule"]["fields"]:
            fd = model_body["rule"]["fields"][system]
            if fd != [None]:
                fieldstitle = metaschema["rule"]["properties"]["fields"]["properties"][
                    system
                ]["title"]
                fields += f"\n\n _{fieldstitle} :_ {', '.join(fd)} "

    if logsources != "":
        logsources = f"### {get_icon('logsources')} Log Sources\n\n{logsources}"

    if fields != "":
        fields = f"### {get_icon('fields')} Alert fields\n\n{fields}"

    query_fold = """
<details>
<summary>{}</summary>

```sql
{}
```

</details>
&nbsp; 
        """

    rules = ""

    for system in model_body["rule"]["alert"]:
        systemtitle = get_field_title(
            system, metaschema["rule"]["properties"]["alert"]["properties"]
        )
        rule = model_body["rule"]["alert"][system]
        rules += f"\n### {systemtitle}\n" + query_fold.format(
            "Expand Rule", rule.strip()
        )

    if parent is not None:
        if parent[:3] != "BDR":  # BDR models do not contain att&ck mappings
            parent_techniques = model_value(parent, "att&ck")
            if parent_techniques is not None:
                techniques = [parent_techniques]
            else:
                techniques = list()
                if n := model_value(parent, "vectors"):
                    for v in n:
                        vector_techniques = model_value(v, "att&ck")
                        if vector_techniques:
                            for t in vector_techniques:
                                techniques.append(t)
        else:
            techniques = ""  # Case for BDR

    else:
        techniques = model_body.get("tags", {}).get("att&ck") or ""
        if techniques != "":
            techniques = [techniques]

    meta = list()
    for k in model_body["meta"]:
        if k in ["tlp"]:
            meta.append(k)
        else:
            # Generates correct names for the fields
            meta_title = get_field_title(k, metaschema) or ""
            meta.append(meta_title + " : " + str(model_body["meta"][k]))

    meta = " | ".join(meta)

    output = template.format(**locals())

    return output


def run():

    log("TITLE", "Legacy MDRv2 Documentation")
    log(
        "INFO",
        "Generates markdown documentation for legacy MDRv2 files. Will be deprecated.",
    )

    if not os.path.exists(MDR_WIKI_PATH):
        print("📁 Creating documentation folder : {}... ".format(str(MDR_WIKI_PATH)))
        os.mkdir(MDR_WIKI_PATH)

    doc_count = 0

    metaschema = DataTide.TideSchemas.mdrv2["properties"]

    for model in MODELS_INDEX["mdr"]:
        model_body = MODELS_INDEX["mdr"][model]

        if get_type(model, get_version=True) == "mdrv2":

            icon = ICONS["mdr"]
            clean_name = model_body["title"].split("$")[0]
            clean_name = clean_name.strip().replace("_", " ")
            out_name = f"{icon} {clean_name}.md"
            out_name = safe_file_name(out_name)
            status = model_body["status"]
            output_path = MDR_WIKI_PATH / out_name

            print(f"{icon} Generating documentation for {clean_name} in {status}...")

            if GLFM:
                output_path = Path(str(output_path).replace(" ", "-"))

            markdown = gen_documentation(model_body, metaschema)
            with open(output_path, "w+", encoding="utf-8") as output:
                output.write(markdown)
                doc_count += 1

        else:
            print(f"🚫 [MDRv3 SKIP] Skipping {model_body.get('name')}")
    doc_format_log = ""
    if GLFM:
        doc_format_log = "🦊 Gitlab Flavored Markdown"
    else:
        doc_format_log = "✒️ standard markdown"

    time_to_execute = "%.2f" % (time.time() - start_time)

    print("\n⏱️ Generated {} documents in {} seconds".format(doc_count, time_to_execute))
    print("✅ Successfully built TIDeMEC documentation in {}".format(doc_format_log))


if __name__ == "__main__":
    run()
