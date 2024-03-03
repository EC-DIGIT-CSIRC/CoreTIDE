import os
import git
import uuid
import sys
from collections.abc import MutableMapping as Map
from typing import Literal

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.tide import DataTide
from Engines.modules.logging import log

DEFINITIONS_INDEX = DataTide.TideSchemas.definitions
VOCAB_INDEX = DataTide.Vocabularies.Index
MODELS_INDEX = DataTide.Models.Index
CHAINING_INDEX = DataTide.Models.chaining


def recursive_dict_merge(source_dict, merge_dict):
    """
    Recursive dict merge. Mitigation for dict.update() which will not resolve
    two dictionaries with common nested keys and just overwrite from the top level.
    """
    for key in merge_dict:
        if (
            key in source_dict
            and isinstance(source_dict[key], Map)
            and isinstance(merge_dict[key], Map)
        ):
            recursive_dict_merge(source_dict[key], merge_dict[key])
        else:
            source_dict[key] = merge_dict[key]


def unroll_dot_dict(dot_dict, separator="."):
    """
    Processes a dot (or other arbitrary symbol) separated dictionary into a nested dictionary
    Useful for turning nested params into a data structure that
    can be merged into another config dictionary.
    """
    if len(dot_dict.keys()) > 1:
        print(
            f"⚠️ Cannot process dictionary {str(dot_dict)}, expecting a single item dictionary"
        )
        return None

    ((long_key, value),) = dot_dict.items()
    nested_keys = long_key.split(separator)

    # Reverse dictionary so it can nest dictionaries backwards
    nested_keys.reverse()

    unrolled = dict()

    for key in nested_keys:

        current_index = nested_keys.index(key)

        # Check if first item in reversed keys, and assign terminal value to the key
        if current_index == 0:
            unrolled[key] = value

        else:
            # Copy dictionary, empty it and nest it
            copy_dict = unrolled.copy()
            unrolled = {}
            unrolled[key] = copy_dict.copy()

    return unrolled


def key_value_transform(kv_store_list: list) -> dict:
    kv_store = dict()
    for elem in kv_store_list:
        kv_store[elem["key"]] = elem["value"]
    return kv_store


# def rename_param_nest(nest, schema):
#
#    nest_copy= nest.copy()
#
#    for item in nest_copy:
#        if type(nest_copy[item]) == list:
#            parameter_name = get_value_metaschema(item, schema, "tide.mdr.parameter")
#
#            # Case for key:value format
#            if get_value_metaschema(item, schema, "key_value_store"):
#                nest[parameter_name] = key_value_transform(nest.pop(item))
#
#            else:
#                nest[parameter_name] = nest.pop(item)
#                for elem in nest_copy[item]:
#                    rename_param_nest(elem,schema)
#
#        elif type(nest_copy[item]) == dict:
#            parameter_name = get_value_metaschema(item, schema, "tide.mdr.parameter")
#            nest[parameter_name] = nest.pop(item)
#            rename_param_nest(nest[parameter_name], schema)
#
#        else:
#            parameter_name = get_value_metaschema(item, schema, "tide.mdr.parameter")
#            temp = nest[item] #Avoids conflicts if tidemec name and param names are the same
#            nest.pop(item)
#            nest[parameter_name] = temp
#
#    return nest


def get_value_metaschema(
    field, metaschema: dict, retrieve: str | Literal["tide.meta"], scope=None
):
    """
    Retreives any field from the metaschema at any depth

    Parameters
    ----------
    field : from which the corresponding title will be retrieved
    metaschema : search space
    retrieve: the key to be retrieved.
    scope: Allows to first narrow down a search namespace. Useful to allow for keys named in the same way at different
    nesting levels throughout the template

    Returns
    -------
    title: the title of the field to research.

    """
    if not metaschema:
        return None

    if scope:
        scoped_meta = get_value_metaschema(scope, metaschema, retrieve="tide.meta")
        if scope == "threat_objects":
            return get_value_metaschema(field, scoped_meta, retrieve)  # type: ignore

    if field in metaschema.keys():
        if retrieve == "tide.meta":
            return {field: metaschema[field]}
        else:
            return metaschema[field].get(retrieve)

    else:
        for key in metaschema.keys():
            if metadef := metaschema[key].get("tide.meta.definition"):
                if metadef is True:
                    definition = DEFINITIONS_INDEX[key]
                else:
                    definition = DEFINITIONS_INDEX[metadef]
                if field == key:
                    return DEFINITIONS_INDEX[key].get(retrieve)
                elif (
                    get_value_metaschema(field, definition.get("properties"), retrieve)
                    != None
                ):
                    return get_value_metaschema(
                        field, definition.get("properties"), retrieve
                    )

            if (
                metaschema[key].get("type") == "object"
                and "recomposition" not in metaschema[key].keys()
            ):
                if "additionalProperties" not in metaschema[key].keys():
                    # Trick since recursive function would not return for all
                    # occurence, would break on first return. If the return is not
                    # None, it means it's the title and thus returns.
                    if (
                        get_value_metaschema(
                            field, metaschema[key].get("properties"), retrieve
                        )
                        != None
                    ):
                        return get_value_metaschema(
                            field, metaschema[key].get("properties"), retrieve
                        )

            # Handle case for arrays of items
            if (
                metaschema[key].get("type") == "array"
                and "properties" in metaschema[key].get("items", {}).keys()
            ):
                if (
                    get_value_metaschema(
                        field, metaschema[key]["items"].get("properties"), retrieve
                    )
                    != None
                ):
                    return get_value_metaschema(
                        field, metaschema[key]["items"].get("properties"), retrieve
                    )


def rename_param_nest(nest, schema, scope=None):
    print("SCOPE ", scope)
    nest_copy = nest.copy()

    for item in nest_copy:
        parameter_name = get_value_metaschema(
            item, schema, "tide.mdr.parameter", scope=scope
        )
        temp = nest[
            item
        ]  # Avoids conflicts if tidemec name and param names are the same
        nest.pop(item)
        nest[parameter_name] = temp

        if type(nest_copy[item]) == list:
            # Case for key:value format
            if get_value_metaschema(item, schema, "key_value_store"):
                nest[parameter_name] = key_value_transform(nest_copy[item])
            else:
                for elem in nest_copy[item]:
                    rename_param_nest(elem, schema, scope=item)

        elif type(nest_copy[item]) == dict:
            rename_param_nest(nest[parameter_name], schema, scope=item)

    return nest


def deep_update(dictionary, key, new_value):
    """
    Walks a nested dictionary at all depth until it meets key, then updates with new_value
    Note that the dictionary must contain the expected key at some depth, else
    will return None.
    """

    dict_copy = dictionary.copy()

    if key in dict_copy.keys():
        dictionary[key] = new_value

    else:
        for k in dict_copy:
            if type(dict_copy[k]) == dict:
                deep_update(dictionary[k], key, new_value)

    return dictionary


def vocab_metadata(vocab: str, field=None) -> str | dict:
    """
    Returns the metadata (description, links, icon etc.) for a given vocabulary.
    If field is set to None returns the entire metadata
    """

    if vocab not in VOCAB_INDEX.keys():
        return ""

    vocab_data = VOCAB_INDEX[vocab]["metadata"]

    if field:
        if field not in vocab_data:
            log("FAILURE", f"{field} does not exist in vocab", vocab)
            return ""
        else:
            return vocab_data.get(field)
    else:
        return vocab_data


def get_vocab_entry(vocab, identifier, field=None, newlines=False):
    """
    Returns data for a particular entry of a voacbulary.
    Supports two modes : if field is None, will return all data from
    the entry as a dict, else will fetch the data for the given
    identifier.
    """

    if vocab not in VOCAB_INDEX.keys():
        return ""

    if identifier in VOCAB_INDEX[vocab]["entries"].keys():
        entry_data = VOCAB_INDEX[vocab]["entries"][identifier]

        if field is None:
            return entry_data

        elif field in entry_data.keys():
            data = entry_data[field]
            if newlines is False and type(data) == str:
                return data.replace("\n", "")
            else:
                return data
        else:
            print(
                f"⚠️ Could not retrieve parameter [ {field} ] for entry with identifier [ {identifier} ] from vocabulary data of : {vocab}"
            )
            return ""

    # Lookup for legacy entries in vocab if all things fail
    else:
        vocab_data = VOCAB_INDEX[vocab]["entries"]
        for v in vocab_data:
            if vocab_data[v].get("legacy") == identifier:
                entry_data = VOCAB_INDEX[vocab]["entries"][identifier]
                if field is None:
                    return entry_data

                if field is None:
                    return entry_data

                elif field in entry_data.keys():
                    data = entry_data[field]
                    if newlines is False:
                        return data.replace("\n", "")
                    else:
                        return data

    print(
        f"⚠️ Could not retrieve identifier [ {identifier} ] from vocabulary data of : {vocab}"
    )
    return ""


def get_key_in_model_body(model_body, key):
    """
    Self-recursive function to return the value of a key nested within
    the body of a model data.
    """
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


def model_value(id, key):
    model_type = get_type(id)
    data = MODELS_INDEX[model_type][id]
    value = get_key_in_model_body(data, key)
    return value


def parents(id: str) -> list:
    """
    Returns the list of parents for any given TIDeMEC Object.
    If the Object does not have possible parent relationships,
    or in other word is a top-level Object, returns an empty string.
    """

    model_type = get_type(id)
    parents = []
    parent_mappings = {
        "tvm": {"data": "threat", "parent": "actors"},
        "cdm": {"data": "detection", "parent": "vectors"},
        "mdr": {"parent": "detection_model"},
    }

    if model_type not in parent_mappings:
        return []

    model_data = MODELS_INDEX[model_type][id]
    parent_loc = parent_mappings[model_type]

    if "data" in parent_loc:
        parents = model_data[parent_loc["data"]].get(parent_loc["parent"]) or []

    else:
        parents = model_data.get(parent_loc["parent"]) or []

    if type(parents) is str:
        parents = [parents]

    return parents


def childs(model_id: str) -> list:
    """
    Returns the list of direct descendants for any given TIDeMEC Object,
    by performing a forward search.

    If the object can not have descendants, or in other word is a last-line
    Object (such as MDRs), will return an empty dictionary
    """

    implementations = []

    mappings = {
        "tam": {"child_type": "tvm", "data": "threat", "reference": "actors"},
        "tvm": {"child_type": "cdm", "data": "detection", "reference": "vectors"},
        "cdm": {"child_type": "mdr", "reference": "detection_model"},
        "bdr": {"child_type": "mdr", "reference": "detection_model"},
    }

    model_type = get_type(model_id)

    if model_type not in mappings.keys():
        return []

    child_type = mappings[model_type]["child_type"]
    data = mappings[model_type].get("data", None)
    reference = mappings[model_type]["reference"]

    CHILDS_INDEX = MODELS_INDEX[child_type]
    for child in CHILDS_INDEX:
        if child_type == "mdr":
            child_version = get_type(child, get_version=True)
            if child_version == "mdrv2":
                data = "tags"
            else:
                data = None
        if data:
            if model_id in CHILDS_INDEX[child].get(data, {}).get(reference, []):
                implementations.append(child)
        else:
            if model_id in CHILDS_INDEX[child].get(reference, []):
                implementations.append(child)

    return implementations


def get_type(model_id: str, get_version=False):
    """
    Return the model type based on the model id format
    """

    try:
        # Testing if model_id is a uuid, which would mean an MDR
        uuid.UUID(model_id)
        if get_version == True:
            model_body = MODELS_INDEX["mdr"][model_id]
            if "configurations" not in model_body.keys():
                return "mdrv2"
            else:
                return "mdrv3"
        else:
            return "mdr"

    except:
        model_type = model_id[:3].lower()
        # Catch-all in case the uuid is not valid, so we don't truncate the
        # erroneuous string.
        if (
            model_type in MODELS_INDEX.keys() or model_type == "rpt"
        ):  # Special case for reports
            return model_type
        else:
            return "mdr"


def techniques_resolver(model_id: str, recursive=True) -> list:
    """
    Returns the relevant technique for any object, based on its own
    and its parent properties. WARNING : only works when index is loaded
    in memory.

    Returns
    -------
    techniques: List of resolved techniques.
    """

    techniques = []

    # Find the model_type
    model_type = get_type(model_id)
    # Load Model Data
    model_body = MODELS_INDEX[model_type][model_id]

    if model_type == "bdr":
        return []  # Case for BDR, as they do not relate to a technique concept

    if model_type == "mdr":
        parent_id = model_body.get("detection_model") or model_body.get("tags", {}).get(
            "tidemec"
        )
        if not parent_id:
            return []  # Case when there is no parent CDM
        else:
            if recursive:
                techniques.extend(techniques_resolver(parent_id))
            else:
                return techniques

    if model_type == "cdm":
        if "att&ck" in model_body["detection"]:
            techniques = [model_body["detection"]["att&ck"]]
        else:
            parent_ids = model_body["detection"]["vectors"]
            if recursive:
                for parent_id in parent_ids:
                    techniques.extend(techniques_resolver(parent_id))
            else:
                return techniques

    if model_type == "tvm":
        techniques = model_body["threat"]["att&ck"]

    if model_type == "tam":
        techniques = model_body["actor"]["att&ck"]

    # Deduplicate techniques in case they were present
    # across multiple
    techniques = list(dict.fromkeys(techniques))

    return techniques


def relations_downstream(id):

    tree = {}

    if get_type(id) in ["cdm", "bdr"]:
        tree = childs(id)
    else:
        for c in childs(id):
            tree[c] = relations_downstream(c)

    return tree


def relations_upstream(id):

    tree = {}
    if get_type(id) == "tvm":
        tree = parents(id)
    else:
        for p in parents(id):
            tree[p] = relations_upstream(p)

    return tree


def relations_list(
    id,
    mode: Literal["count", "flat"] = "flat",
    direction: Literal["upstream", "downstream", "both"] = "downstream",
):

    flat = {}

    if direction == "upstream":
        relations = relations_upstream(id)
    elif direction == "downstream":
        relations = relations_downstream(id)
    elif direction == "both":
        merged = relations_list(id, mode, direction="downstream")
        merged.update(relations_list(id, mode, "upstream"))
        return merged

    def recursive_items(dictionary):
        for key, value in dictionary.items():
            if type(value) is dict:
                yield (key, value)
                yield from recursive_items(value)
            else:
                yield (key, value)

    if relations and type(relations) is list:
        flat[get_type(relations[0])] = relations

    if type(relations) is dict:
        for k, v in recursive_items(relations):
            if k:
                if type(k) is list:
                    k_type = get_type(k[0])
                    flat.setdefault(k_type, [])
                    flat[k_type].extend(k)
                if type(k) is str:
                    k_type = get_type(k)
                    flat.setdefault(k_type, [])
                    flat[k_type].append(k)
            if v:
                if type(v) is list:
                    v_type = get_type(v[0])
                    flat.setdefault(v_type, [])
                    flat[v_type].extend(v)
                if type(v) is str:
                    v_type = get_type(v)
                    flat.setdefault(v_type, [])
                    flat[v_type].append(v)

    for k, v in flat.items():
        flat[k] = list(set(v))

    if mode == "count":
        for k, v in flat.items():
            flat[k] = len(v)

    return flat


def chain_resolver(entry_point: str, chain: dict = {}) -> dict:
    """
    Search all chaining nodes and relations links
    of a given tvm to the n node, and recursively search for all returned value
    to reconstruct the full chain.
    """
    vector_chaining = CHAINING_INDEX.get(entry_point)
    if vector_chaining:
        for link in vector_chaining:
            if entry_point not in chain:
                chain[entry_point] = dict()
            if link not in chain[entry_point]:
                chain[entry_point][link] = []
            for v in vector_chaining[link]:
                if v not in chain[entry_point][link]:
                    chain[entry_point][link].append(v)
                    chain = chain_resolver(v, chain)

    return chain
