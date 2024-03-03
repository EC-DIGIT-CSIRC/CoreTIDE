import yaml
import os
import git
import pandas as pd
from pathlib import Path
import uuid

CONFIG = yaml.safe_load(open("../../Resources/config.yaml", encoding="utf-8"))
metaschema_folder = Path(CONFIG["paths"]["metaschemas"])
wiki_path = Path(CONFIG["paths"].models_docs_folder)
vocab_path = Path(CONFIG["paths"]["vocabularies"])


vocab_index = {}

ram = yaml.safe_load(
    open("../../Models Library/Response Action Models/RAM0001 - Test.yaml")
)

metaschema = yaml.safe_load(open(metaschema_folder / "RAM Meta Schema.yaml"))


mermaid_template = """
flowchart LR\n\n
    Z([Incident\\n Start]) ==>|Initiates| Preparation
    Preparation --> Identification
    Identification --> Containment
    Containment --> Eradication
    Identification -->|Check\\nand Trace| S[(Potential\\nother Targets)]
    Lessons -->|Define\\nImprovements| Preparation
    Eradication --> Y{Search\\nThreat\\nIndicators} -.->|Threat\\nis still present| Identification
    Y -->|Threat\\nRemoved| Recovery
    Recovery --> W{Control\\nRecovery}
    W -.->|Still not\\nrecovered| Recovery
    W -->|Succesfully\\nrecovered| Lessons
    R[/Detection\\ndetails/] -.->|Supports| Identification
    Z --> R
    Lessons --> MM([Incident\\n Closed])
"""

# Optimization routine to index vocabulary in program memory
print("Indexing vocabularies into optimized dictionary...")
for vocab_file in os.listdir(vocab_path):
    vocab = yaml.safe_load(open(vocab_path / vocab_file))
    vocab_index[vocab["field"]] = vocab["keys"]


def make_vocab_link(field, key):
    link = key
    if field in vocab_index.keys():

        for k in vocab_index[field]:
            if "name" in k.keys():
                check = "name"
            else:
                check = "id"
            if k[check] == key:

                if k.get("name") is None:
                    name = k["id"]

                else:
                    name = k["name"]

                if "link" in k.keys():
                    url = k["link"]
                    link = "[" + name + "]" + "(" + url + ")"
                break
    return link


def make_freeform_table(model_body):

    del model_body["guidelines"]
    del model_body["actions"]

    ram_meta = yaml.safe_load(open(metaschema_folder / "RAM Meta Schema.yaml"))

    model_table = model_body.copy()
    df = pd.DataFrame(columns=["Field", "Data"])

    tag_list = []
    skip_keys = []

    for key in model_body:
        if key not in skip_keys:
            print("This is the key : " + key)
            buffer = {}
            description = []
            # Generates correct names for the fields
            title = model_fields_to_title(key, ram_meta["properties"])
            model_table[title] = model_body[key]
            model_table.pop(key)

            # Converts arrays into strings
            if type(model_body[key]) == list:
                if len(model_body[key]) > 1:
                    # Hyphen for multi items list
                    links = []
                    for k in model_body[key]:
                        links.append(make_vocab_link(key, k))
                    model_table[title] = " - " + "\n - ".join(links)
                # Case for single value items in lists, to avoid hyphen
                else:
                    model_table[title] = "".join(
                        make_vocab_link(key, model_body[key][0])
                    )

                for tag in model_body[key]:
                    tag_list.append(tag)

            else:
                tag_list.append(model_body[key])

            if type(model_body[key]) == str:
                description = get_description_from_vocab(key, model_table[title])

            elif type(model_body[key]) == list:
                for field in model_body[key]:
                    description.append(get_description_from_vocab(key, field))
                description = "\n".join(description)

            buffer["Field"] = "**" + title + "**"
            buffer["Data"] = model_table[title]
            buffer["Description"] = description
            # Append dict to dataframe similar to append, using concat as
            # append() method is now deprecated beyond 1.14
            df = pd.concat([df, pd.DataFrame([buffer])], ignore_index=True)

    print("Dumping table into markdown")
    markdown_table = df.to_markdown(index=False)

    if df.empty:
        markdown_table = ""
    return markdown_table  # , tag_list


def model_value_doc(model_id, key):
    if model_id.startswith("TAM"):
        model_folder = Path(config["paths"]["tam"])

    elif model_id.startswith("TVM"):
        model_folder = Path(config["paths"]["tvm"])

    elif model_id.startswith("CDM"):
        model_folder = Path(config["paths"]["cdm"])

    else:
        return "Unknown"

    for model in os.listdir(model_folder):
        model_content = yaml.safe_load(open(model_folder / model))
        if model_content["id"] == model_id:
            model_body = model_content
            break
    value = get_key_in_model_body(model_body, key)

    return value


def get_key_in_model_body(model_body, key):
    if key in model_body.keys():
        return model_body[key]

    else:
        for model_key in model_body.keys():
            if type(model_body[model_key]) is dict:
                # Trick since recursive function would not return for all
                # occurence, would break on first return. If the return is not
                # None, it means it's the title and thus returns.
                if get_key_in_model_body(model_body[model_key], key) != None:
                    return get_key_in_model_body(model_body[model_key], key)


def get_description_from_vocab(field, key, special=None):
    if special is None:
        special = "description"
    description = ""

    for vocab_key in vocab_index[field]:
        if vocab_key["name"] == key:
            description = vocab_key[special].replace("\n", "")
            break

    return description


def backlink_resolver(model_id):

    if model_id.startswith("TAM"):
        model_folder = Path(config["paths"]["tide"]["tam"])
        doc_path = "../" + config["artifacts"]["docs"]["object_name"]["tam"]

    elif model_id.startswith("TVM"):
        model_folder = Path(config["paths"]["tide"]["tvm"])
        doc_path = "../" + config["artifacts"]["docs"]["object_name"]["tvm"]

    elif model_id.startswith("CDM"):
        model_folder = Path(config["paths"]["cdm"])
        doc_path = "../" + config["artifacts"]["docs"]["object_name"]["cdm"]

    else:
        return "Unknown"

    for model in os.listdir(model_folder):
        model_content = yaml.safe_load(open(model_folder / model))
        if model_content["id"] == model_id:
            model_body = model_content
            model_name = model.replace(".yaml", ".md")
            break

    backlink_name = "[" + model_body["id"] + " : " + model_body["name"] + "]"
    backlink_path = doc_path.replace(" ", "%20") + model_name.replace(" ", "%20")
    backlink_link = "(" + backlink_path + ")"
    backlink = backlink_name + backlink_link
    return backlink


def model_fields_to_title(field, metaschema):
    """
    Retreives the field verbose title from the field key, recursively at any
    depth

    Parameters
    ----------
    field : from which the corresponding title will be retrieved
    metaschema : search space

    Returns
    -------
    title: the title of the field to research.

    """
    print("This is retrieved : " + field)
    if field in metaschema.keys():
        title = metaschema[field]["title"]
        return title

    else:
        for key in metaschema.keys():
            print("This is the iteration : " + key)
            if metaschema[key]["type"] == "object":
                # Trick since recursive function would not return for all
                # occurence, would break on first return. If the return is not
                # None, it means it's the title and thus returns.
                if (
                    model_fields_to_title(field, metaschema[key]["properties"])
                    is not None
                ):
                    return model_fields_to_title(field, metaschema[key]["properties"])


def make_attack_link(technique, fmt="full"):

    for key in vocab_index["att&ck"]:
        if key["id"] == technique:
            if fmt == "full":
                link_name = "[" + key["id"] + " : " + key["name"] + "]"
                link_url = "(" + key["link"] + ")"
                link = link_name + link_url
            elif fmt == "compact":
                link_name = "[" + key["id"] + "]"
                link_url = "(" + key["link"] + ")"
                link = link_name + link_url

            return link


def line_wrapper(string, wrap):
    words = string.split()
    wrap_words = []
    count = 0
    for word in words:
        if count == wrap:
            wrap_words.append("\\n")
            wrap_words.append(word)
            count = 0

        else:
            wrap_words.append(word)
            count += 1

    wrapped = " ".join(wrap_words)

    return wrapped


def make_workflow(ram):

    react_stage = [
        "preparation",
        "identification",
        "containment",
        "eradication",
        "recovery",
        "lessons",
    ]

    subgraph_flow = ""

    for stage in ram["response"]:
        if stage in react_stage:
            subgraph = "\tsubgraph " + stage.capitalize() + "\n\n"
            hashes = []
            flow = ""
            for action in ram["response"][stage]["actions"]:
                action_hash = str(uuid.uuid4())[:8]
                hashes.append(action_hash)
                subgraph += (
                    "\t" + action_hash + "[" + line_wrapper(action, 2) + "]" + "\n"
                )

            if len(hashes) == 1:
                flow = ""

            else:
                for h in hashes:
                    if h == hashes[-1]:
                        flow += h
                    else:
                        flow += h + " --> "

            subgraph += "\n" + "\t" + flow + "\n\tend\n\n"
            subgraph_flow += subgraph

    workflow = "```mermaid\n\n" + mermaid_template + "\n\n" + subgraph_flow + "\n\n```"

    return workflow


def gen_ram_doc(ram, metaschema):

    title = ram["id"] + " : " + ram["name"]

    description = ram["response"]["description"].replace("\n", " ")

    parents = ""
    actions = ""

    meta_fields = {}
    meta = ""
    for key in ram["meta"]:
        # Case for TLP/PAP classic formating
        if key in ["pap", "tlp"]:
            meta += key.upper() + ":" + ram["meta"][key].upper() + " | "

        else:
            # Generates correct names for the fields
            meta_title = model_fields_to_title(key, metaschema["properties"])
            meta_fields[title] = ram["meta"][key]
            value = meta_fields[title]
            meta += meta_title + " : " + str(value) + " | "

    # Markdown syntax and remove trailing " | "
    meta = "`" + meta[:-3] + "`"

    # Fetch references verbose title field
    references_title = model_fields_to_title("references", metaschema["properties"])
    references = ""

    workflow = make_workflow(ram)
    attack = []

    rel_vec = []
    rel_actors = []
    rel_assets = []
    rel_detect = []

    tvm_schema = yaml.safe_load(open(metaschema_folder / "TVM Meta Schema.yaml"))

    tam_schema = yaml.safe_load(open(metaschema_folder / "TAM Meta Schema.yaml"))

    cdm_schema = yaml.safe_load(open(metaschema_folder / "CDM Meta Schema.yaml"))

    vec_fields = ["killchain", "domains", "description"]
    actor_fields = ["tier", "description"]
    detect_fields = ["datasources", "collection", "artifacts"]

    for detection in ram["response"]["detection_model"]:
        vectors = model_value_doc(detection, "vectors")

        detect_dict = {}
        detect_dict["Detection Models"] = backlink_resolver(detection)

        for field in detect_fields:

            detect_field_val = model_value_doc(detection, field)
            if type(detect_field_val) is list:
                detect_field_val = ", ".join(detect_field_val)

            detect_dict[model_fields_to_title(field, cdm_schema["properties"])] = (
                detect_field_val.replace("\n", " ")
            )

        rel_detect.append(detect_dict)

        for vector in vectors:

            vec_actors = model_value_doc(vector, "actors")
            for actor in vec_actors:
                actor_dict = {}
                actor_dict["Known Actors"] = backlink_resolver(actor)

                for field in actor_fields:

                    actor_field_val = model_value_doc(actor, field)
                    if type(actor_field_val) is list:
                        actor_field_val = ", ".join(actor_field_val)

                    actor_dict[
                        model_fields_to_title(field, tam_schema["properties"])
                    ] = actor_field_val.replace("\n", " ")

                rel_actors.append(actor_dict)

            vec_dict = {}

            vec_techniques = model_value_doc(vector, "att&ck")

            vec_assets = model_value_doc(vector, "targets")

            vec_name = backlink_resolver(vector)
            vec_links = []

            if len(vec_techniques) < 20:
                for technique in vec_techniques:
                    vec_links.append(make_attack_link(technique))
            else:
                for technique in vec_techniques:
                    vec_links.append(make_attack_link(technique, fmt="compact"))

            vec_links = ", ".join(vec_links)

            vec_dict["Vectors"] = vec_name
            vec_dict["Potential Techniques"] = vec_links
            vec_dict["Assets at Risk"] = ", ".join(vec_assets)

            for field in vec_fields:

                vec_field_val = model_value_doc(vector, field)
                if type(vec_field_val) is list:
                    vec_field_val = ", ".join(vec_field_val)

                vec_dict[model_fields_to_title(field, tvm_schema["properties"])] = (
                    str(vec_field_val).replace("\n", " ")
                )

            rel_vec.append(vec_dict)

    vec_table = pd.DataFrame(rel_vec).drop_duplicates().to_markdown(index=False)
    actors_table = pd.DataFrame(rel_actors).drop_duplicates().to_markdown(index=False)
    threat_table = vec_table + "\n\n" + actors_table

    detect_table = pd.DataFrame(rel_detect).drop_duplicates().to_markdown(index=False)

    # Assembled markdown string
    for ref in ram["references"]:
        references += "- " + ref + "\n"

    for stage in ram["response"]:
        df = pd.DataFrame(columns=["Action", "Description", "Workflow"])

        if type(ram["response"][stage]) is dict:

            for action in ram["response"][stage]["actions"]:
                buffer = {}
                buffer["Action"] = action
                buffer["Description"] = get_description_from_vocab("actions", action)
                buffer["Workflow"] = get_description_from_vocab(
                    "actions", action, special="workflow"
                )
                df = pd.concat([df, pd.DataFrame([buffer])], ignore_index=True)

            stage_freeform = make_freeform_table(ram["response"][stage].copy())

            stage_title = str(model_fields_to_title(stage, metaschema["properties"]))

            stage_desc = ram["response"][stage]["guidelines"].replace("\n", " ")
            stage_actions = df.to_markdown(index=False)

            stage_full = (
                "### "
                + stage_title
                + "\n\n    "
                + stage_desc
                + "\n\n"
                + stage_freeform
                + "\n\n"
                + stage_actions
                + "\n\n---\n\n"
            )

            actions += stage_full

    foam = "---\ntype: Response Actions\n---"

    tlp = (
        "_**TLP:"
        + ram["meta"]["tlp"].upper()
        + "**_  "
        + get_description_from_vocab("tlp", ram["meta"]["tlp"])
    )

    pap = ram["meta"].get("pap")

    if pap is not None:
        pap = "_**PAP:" + pap.upper() + "**_ " + get_description_from_vocab("pap", pap)
    else:
        pap = ""

    header = (
        "> **Criticality** : "
        + ram["criticality"]
        + "\n"
        + "> \n"
        + "> "
        + tlp
        + "\n"
        + "> \n"
        + "> "
        + pap
        + "\n"
        + "> \n"
    )

    layout = (
        foam
        + "\n\n"
        + "# "
        + title
        + "\n\n"
        + header
        + "\n\n"
        + "    "
        + description
        + "\n\n"
        + "### Parent Detections"
        + "\n\n"
        + detect_table
        + "\n\n"
        + "### Potential Threats"
        + "\n\n"
        + threat_table
        + "\n\n"
        + "## Workflow"
        + "\n\n"
        + workflow
        + "\n\n"
        + "### "
        + references_title
        + "\n\n"
        + references
        + "\n\n"
        + "## Response Actions"
        + "\n\n"
        + actions
        + "\n\n"
        + meta
    )

    return layout


doc_out = "../../Models Library/Response Action Models/DOC.md"

output = gen_ram_doc(ram, metaschema)

with open(doc_out, "w+") as doc:
    doc.write(output)
