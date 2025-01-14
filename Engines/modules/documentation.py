import pandas as pd
import git
import sys
import json
from typing import Literal

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.framework import (
    get_type,
    model_value,
    get_value_metaschema,
    get_vocab_entry,
)
from Engines.modules.logs import log
from Engines.modules.tide import DataTide

VOCAB_INDEX = DataTide.Vocabularies.Index
DOCUMENTATION_TYPE = DataTide.Configurations.Documentation.documentation_type
ICONS = DataTide.Configurations.Documentation.icons
DOCUMENTATION_CONFIG = DataTide.Configurations.Documentation
CONFIG_INDEX = DataTide.Configurations.Index
DEFINITIONS_INDEX = DataTide.TideSchemas.definitions
MODELS_INDEX = DataTide.Models.Index

FOLD = """
<details>
<summary>{}</summary>

{}

</details>
&nbsp; 
"""


class GitlabMarkdown:

    @staticmethod
    def negative_diff(string: str) -> str:
        return f"[- {string} -]"

    @staticmethod
    def positive_diff(string: str) -> str:
        return f"[+ {string} +]"


def sanitize_hover(hover: str) -> str:
    """
    Removes forbidden characters from infobubbles/popovers on
    markdown formatted links
    """
    hover = hover.replace("\n", " ")
    hover = hover.replace("'", "")
    hover = hover.replace('"', "")
    hover = hover.replace("]", "")
    hover = hover.replace("[", "")
    hover = hover.replace("(", "")
    hover = hover.replace(")", "")
    hover = hover.replace("|", "")
    return hover


def object_name(key):
    """
    Return a pretty print name for the TIDe object.
    """
    if key == "Unknown":
        return ""
    id = key if get_type(key) != "mdr" else ""
    name = model_value(key, "name")
    name = f"  {get_icon(get_type(key)) or ''} {id} {name}"
    return name or key


def make_json_table(dataframe: pd.DataFrame) -> str:
    """
    Converts a dataframe into a searchable and sortable json table,
    rendered in Gitlab.
    """

    # Optimization for json tables:
    # Columns are repeated in every row of the table,
    # to avoid unnecessary characters, an alias is provided
    # under the fields key with label.
    # All rows then use a single character instead of the full
    # column name

    # Create optimized mapping
    df = dataframe
    data = df.to_json(orient="records")
    columns = list(df.columns)

    char = "a"
    optimized_cols = {}
    for c in columns:
        optimized_cols[c] = char
        char = chr(ord(char) + 1)

    # Create field section
    sortable_columns = [
        {"key": optimized_cols[key], "label": key, "sortable": "true"}
        for key in columns
    ]

    # Rename rows with the optimised layout
    items = json.loads(data)
    optimized_items = []
    for i in items:
        buffer = {}
        for old_name in i:
            new_name = optimized_cols[old_name]
            buffer[new_name] = i[old_name]
        optimized_items.append(buffer)

    # Make data structure
    json_data = {
        "fields": sortable_columns,
        "items": optimized_items,
        "filter": "true",
    }

    # Dumps as an escaped string
    json_data = json.dumps(json_data)

    # Markdown block for rendering
    json_table = f"""
```json:table
{json_data}
```
    """

    return json_table


def get_icon(
    value, vocab=None, parent_icon=True, metaschema=None, legacy=False
) -> str:  # type:ignore

    if metaschema:
        meta_icon = get_value_metaschema(value, metaschema, "icon")
        if meta_icon:
            return str(meta_icon)
        else:
            return ""

    elif value in ICONS:
        return str(ICONS[value])

    elif value in VOCAB_INDEX.keys():
        return VOCAB_INDEX[value].get("metadata", {}).get("icon") or ""

    elif vocab and vocab in VOCAB_INDEX.keys():
        vocab_data = VOCAB_INDEX[vocab]["entries"]
        entry = vocab_data.get(value) or {}

        if "icon" in entry.keys():
            return entry["icon"]
        elif parent_icon is True:
            return VOCAB_INDEX[vocab]["metadata"].get("icon") or ""

        elif legacy:
            for v in vocab_data:
                if vocab_data[v].get("legacy") == value:
                    return vocab_data[v].get("icon") or ""
        else:
            return ""
    else:
        return ""


# def copy_atomics():
#    path = WIKI / "atomics"
#    os.mkdir(path)
#    for t in ATOMICS_INDEX:
#        body = ATOMICS_INDEX[t]["doc"]
#        atomic_technique = ATOMICS_INDEX[t]["attack_technique"]
#        atomic_name = ATOMICS_INDEX[t]["display_name"].replace("/", " ").replace(":","")
#        atomic_out = f"{atomic_technique} {atomic_name}.md"
#
#        if DOCUMENTATION_TYPE == "GLFM":
#            atomic_out = f"{get_icon('atomics')} {atomic_out}".replace(" ", "-")
#            body = body.split("\n",1)[1]
#
#        with open(path/atomic_out, "w+", encoding='utf-8') as out:
#            out.write(body)


# def make_attack_recommendations(mapping, techniques):
#
#    if mapping == "detection":
#        mapped = RELATIONSHIPS[RELATIONSHIPS["mapping type"] == "detects"]
#        mapped = mapped[mapped["source type"] == "datacomponent"]
#        relevant = mapped[mapped["target ID"].isin(techniques)]
#
#    if mapping == "mitigation":
#        mapped = RELATIONSHIPS[RELATIONSHIPS["mapping type"] == "mitigates"]
#        mapped = mapped[mapped["source type"] == "mitigation"]
#        relevant = mapped[mapped["target ID"].isin(techniques)]
#
#    relevant = relevant.replace(r'\n',' ', regex=True)
#    relevant = relevant[['source name', 'target name', 'mapping description']]
#    relevant = relevant.rename(columns = {'source name':mapping.capitalize(),
#                                          'target name':'Technique',
#                                          'mapping description': 'Description'})
#
#    relevant = relevant.dropna(subset=['Description'])
#    relevant = relevant.sort_values(by=['Technique'])
#
#    recommendations = relevant.to_markdown(index=False)
#
#    return recommendations

# def gen_cloud_recommendations(kind, platform, techniques):
#
#
#    if kind == "detections":
#        locator = ["Detect"]
#    elif kind == "controls":
#        locator = ["Protect", "Respond"]
#
#    recommendations = list()
#
#    for entry in CLOUD_MAPPINGS_INDEX[platform]:
#        for t in entry["techniques"]:
#            if t["id"] in techniques:
#                if t["technique-scores"][0].get("category") in locator and "comments" in t["technique-scores"][0].keys():
#                    buf = dict()
#                    buf["Service"] = entry["name"]
#                    buf["Technique"] = t["name"]
#                    buf["Type"] = t["technique-scores"][0].get("category")
#                    buf["Effectiveness"] = t["technique-scores"][0].get("value")
#                    buf["Description"] = t["technique-scores"][0].get("comments").replace("\n","")
#                    recommendations.append(buf)
#
#            elif "sub-techniques-scores" in t.keys():
#                for s in t["sub-techniques-scores"]:
#                    if s["sub-techniques"][0].get("id") in techniques:
#                        if s["scores"][0].get("category") in locator:
#                            buf = dict()
#                            buf["Service"] = entry["name"]
#                            buf["Technique"] = s["sub-techniques"][0].get("name")
#                            buf["Type"] = s["scores"][0].get("category")
#                            buf["Effectiveness"] = s["scores"][0].get("value")
#                            buf["Description"] = s["scores"][0].get("comments")
#                            recommendations.append(buf)
#
#    if len(recommendations) == 0:
#        table = ""
#    else:
#        table = pd.DataFrame(recommendations).to_markdown(index=False)
#
#    return table


def make_attack_link(
    technique: str, fmt: Literal["full", "compact"] = "full", hover=True
) -> str:

    details = VOCAB_INDEX["att&ck"]["entries"][technique]
    technique_link = details["link"]

    if fmt == "full":
        link_title = technique + " : " + details["name"]

    elif fmt == "compact":
        link_title = technique

    if hover:
        technique_description = details["description"]
        technique_link += f' "{sanitize_hover(technique_description)}"'

    link = f"[{link_title}]({technique_link})"

    return link


def rich_attack_links(
    techniques: list[str],
    wrap=20,
    output: Literal["string", "list"] = "string",
    hover=True,
) -> str:
    """
    Make an enriched string of attack techniques, with wrapping

    hover: Add an infobubble with the description of the technique, accessible when hovering
    """
    if not techniques:
        return ""

    rich_techniques = str()

    if len(techniques) < wrap:
        techniques = [make_attack_link(x, hover=hover) for x in techniques]
    else:
        techniques = [
            make_attack_link(x, fmt="compact", hover=hover) for x in techniques
        ]

    if output == "string":
        rich_techniques = ", ".join(techniques)

    elif output == "list":
        if len(techniques) > 1:
            rich_techniques = "\n- " + "\n- ".join(techniques)

    return rich_techniques


# def make_atomics_links(techniques, platforms):
#    KB_TO_ATOMIC = Path("../atomics/")
#
#    mappings = {
#        "Windows": "windows",
#        "macOS": "macos",
#        "Linux": "linux",
#        "Office 365": "office-365",
#        "Azure AD": "azure-ad",
#        "Software Containers": "containers",
#        "AWS": "iaas:aws",
#        "Azure": "iaas:azure",
#        "GCP": "iaas:gcp"
#        }
#
#    atomic_links = list()
#
#    for t in techniques:
#        if t in ATOMICS_INDEX.keys():
#            for r in ATOMICS_INDEX[t]["atomic_tests"]:
#                for p in platforms:
#                    if mappings.get(p) in r["supported_platforms"]:
#                        index = ATOMICS_INDEX[t]["atomic_tests"].index(r) + 1
#                        name = r["name"]
#
#                        title = f"Atomic Test #{index} {name}"
#                        full_title = ATOMICS_INDEX[t]["display_name"] + " - " + title
#                        #Need to fix hyperlinks for atomics, won't work in wiki.
#
#
#                        atomic_technique = ATOMICS_INDEX[t]["attack_technique"]
#                        atomic_name = ATOMICS_INDEX[t]["display_name"].replace("/", " ").replace(":", "")
#                        link = f"{atomic_technique} {atomic_name}.md"
#
#
#                        anchor = title.replace("#","").lower()
#
#                        if DOCUMENTATION_TYPE == "GLFM":
#                            link = f"{get_icon('atomics')} {link}".replace(" ", "-")
#                            if link[-3:] == ".md": #Just by safety in case some technique contain something with this in middle of string
#                                link = link[:-3]
#                            anchor = anchor.replace(" ", "-")
#                        elif DOCUMENTATION_TYPE == "MARKDOWN":
#                            link = f"{get_icon('atomics')} {link}".replace(" ", "%20")
#                            anchor = anchor.replace(" ", "%20")
#
#
#                        full_link = f"{KB_TO_ATOMIC.as_posix()}/{link}"
#
#
#
#                        link = f"[{full_title}]({full_link}#{anchor})"
#                        atomic_links.append(link)
#
#    return atomic_links


def backlink_resolver(model_id, raw_link=False):

    model_type = get_type(model_id)
    model_data = dict()
    file_link = backlink_name = icon = str()

    if model_type != "rpt":
        model_data = MODELS_INDEX[model_type][model_id]
        icon = ICONS[model_type]

    doc_path = "../" + DOCUMENTATION_CONFIG.object_names[model_type] + "/"
    hover = ""

    def mdr_statuses(mdr_id):
        mdr_configs = MODELS_INDEX["mdr"][mdr_id]["configurations"]
        system_statuses = {}
        for system in mdr_configs:
            sys_status = mdr_configs[system]["status"]
            sys_status_icon = get_icon(sys_status, "status")
            system_statuses[system.upper()] = f"{sys_status_icon} {sys_status}"

        return [f"[{s}] : {status}" for s, status in system_statuses.items()]

    if model_type in ["tam", "tvm", "bdr"]:
        hover = model_value(model_id, "description")
    if model_type in ["cdm"]:
        hover = model_value(model_id, "guidelines")

    if model_type == "mdr":
        if get_type(model_id, get_version=True) == "mdrv2":
            model_name = model_data["title"].split("$")[0].strip()
        else:
            model_name = model_data["name"]

        backlink_name = model_name.replace("_", " ")
        hover = "&#013;&#010;".join(
            mdr_statuses(model_id)
        )  # Magic entity codes to break in tooltips
        mdr_description = model_value(model_id, "description") or ""
        mdr_description = mdr_description
        hover += f"&#013;&#010;&#013;&#010;{mdr_description}"
        file_link = f"{doc_path}{icon} {model_name}"

    elif model_type == "rpt":
        report_data = get_vocab_entry("reports", model_id)
        if type(report_data) is dict:
            backlink_name = f"{model_id} - {report_data['name']}"
            hover = report_data["description"]
            file_link = f"{doc_path}{report_data['file_name']}"

    else:
        model_name = model_data["name"].strip()
        backlink_name = "[{}] {}".format(model_id, model_name)
        file_link = f"{doc_path}{icon} {backlink_name}"

    if DOCUMENTATION_TYPE == "MARKDOWN":
        file_link = file_link.replace(" ", "%20")
        if model_type != "rpt":
            file_link += ".md"

    elif DOCUMENTATION_TYPE == "GLFM":
        file_link = file_link.replace(" ", "-").replace("_", "-")

    hover = sanitize_hover(str(hover))
    backlink = f'[{backlink_name}]({file_link} "{hover}")'
    if raw_link:
        backlink = file_link
    return backlink


def get_field_title(field, metaschema, icon=True):
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
    if metaschema:
        if field in metaschema.keys():

            title = metaschema[field].get("title")

            if not title:
                if metaschema[field].get("tide.vocab"):
                    if metaschema[field]["tide.vocab"] == True:
                        vocab_name = metaschema[field]["tide.vocab"]
                    else:
                        vocab_name = field
                    title = VOCAB_INDEX[vocab_name]["metadata"]["name"]

            if icon is True:
                title_icon = metaschema[field].get("icon") or get_icon(field) or ""
                title = title_icon + " " + title

            return title.strip()

        else:
            for key in metaschema.keys():

                if metaschema[key].get("type") in ["object"] and not metaschema[
                    key
                ].get("patternProperties"):
                    # Trick since recursive function would not return for all
                    # occurence, would break on first return. If the return is not
                    # None, it means it's the title and thus returns.
                    if get_field_title(
                        field, metaschema[key].get("properties"), icon=icon
                    ):
                        return get_field_title(
                            field, metaschema[key].get("properties"), icon=icon
                        )

                elif metadef := metaschema[key].get("tide.meta.definition"):
                    if metadef is True:
                        definition = DEFINITIONS_INDEX[key]
                    else:
                        definition = DEFINITIONS_INDEX[metadef]
                    if field == key:
                        return definition["title"].strip()
                    else:
                        if get_field_title(
                            field, definition.get("properties"), icon=icon
                        ):
                            return get_field_title(
                                field, definition.get("properties"), icon=icon
                            )


def get_vocab_description(vocab, key):

    description = get_vocab_entry(vocab, key, "description")
    description = description.replace("\n", " ")

    return description


def make_vocab_link(field, key):
    if field not in VOCAB_INDEX.keys():
        return key

    entry = VOCAB_INDEX[field]["entries"].get(key)
    vocab_reference = VOCAB_INDEX[field]["metadata"].get("reference")

    key = (get_icon(key, vocab=field, parent_icon=False) or "") + " " + key

    if "link" in entry.keys():
        link = "[`" + key + "`]" + "(" + entry["link"] + ")"
    elif vocab_reference is not None:
        link = "[`" + key + "`]" + "(" + vocab_reference.split(",")[0] + ")"
    else:
        link = f"`{key}`"

    return link


def model_value_doc(model_id, key, with_icon=False, max_chars=None, legacy=False):
    """
    Version of model_value() that add icon and data enrichment functions
    """
    from Engines.modules.framework import get_type, model_value

    value = model_value(model_id, key)

    if value:
        if with_icon:
            if type(value) is list:
                value = [
                    f"{get_icon(v, vocab=key, parent_icon=False, legacy=legacy)} {v}".strip()
                    for v in value
                ]
            elif type(value) is str:
                value_icon = get_icon(
                    value, vocab=key, parent_icon=False, legacy=legacy
                )
                value = f"{value_icon} {value}".strip()

                if max_chars:
                    if len(value) > max_chars:
                        value = value[:max_chars] + "..."

    return value


def name_subschema_doc(
    recomposition: str, identifier: str, with_icon: bool = True
) -> str:
    SUFFIX = "Sub Schema"
    subschema_name = str()
    composition_name = str()
    recomp_config = CONFIG_INDEX[recomposition][identifier]
    if recomp_config:
        subschema_name = recomp_config["tide"]["subschema"]
        composition_name = recomp_config["tide"]["name"]

    if not subschema_name:
        log(
            "INFO",
            f"No subschema name in config.yaml for {identifier}",
            f"Defaulting to taking {identifier} base name",
            "You can add a custom subschema name in config.yaml",
        )
        subschema_name = composition_name + SUFFIX

        if not composition_name:
            log(
                "INFO",
                f"There is no name assigned to {identifier}",
                "A name is strongly recommended for most documentation functions",
                "Ensure to add a name to 'config.yaml'",
            )
            subschema_name = identifier.replace("_", " ").title() + SUFFIX

    if with_icon:
        subschema_name = str(ICONS.get("subschemas")) + " " + subschema_name

    return subschema_name
