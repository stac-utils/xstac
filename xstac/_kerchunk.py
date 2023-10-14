from typing import Any

import collections
import json
import pystac


def add_kerchunk_indices(d: dict[str, Any], item: pystac.Item) -> pystac.Item:
    """
    Add Kerchunk metadata to a STAC item.

    Notes
    -----
    We follow some high-level guidelines:

    1. STAC metadata should always be concrete objects (no JSON strings
       in the properties)
    2. We don't duplicate anything already in the STAC metadata
       (modulo some TODOs around zattrs).

    The output STAC item will have some additional properties:

    - Global `.zgroup` and `.zattrs` are added add `kerchunk:zgroup` and
      and `kerchunk:zattrs`.
    - For each dimension and variable, `.zarray` and `.zattrs` are added as
        `kerchunk:zarray` and `kerchunk:zattrs`.
    - For each chunk of a variable, the index is added under `kerchunk:value`,
      as a mapping `kerchunk:value[i.j.k]`.
    """
    item = item.clone()
    refs = d["refs"]
    for k, v in refs.items():
        match k.split("/"):
            case [".zgroup"]:
                item.properties["kerchunk:zgroup"] = json.loads(v)
            case [".zattrs"]:
                item.properties["kerchunk:zattrs"] = json.loads(v)
            case [variable, ".zarray"]:
                if v := item.properties["cube:dimensions"].get(variable):
                    v["kerchunk:zarray"] = json.loads(refs[k])
                elif v := item.properties["cube:variables"].get(variable):
                    v["kerchunk:zarray"] = json.loads(refs[k])
            case [variable, ".zattrs"]:
                # TODO(Tom): we ideally can get zattrs from the variable.
                # I think we don't need this?
                if v := item.properties["cube:dimensions"].get(variable):
                    v["kerchunk:zattrs"] = json.loads(refs[k])
                elif v := item.properties["cube:variables"].get(variable):
                    v["kerchunk:zattrs"] = json.loads(refs[k])
            case [variable, index]:
                if v := item.properties["cube:dimensions"].get(variable):
                    v.setdefault("kerchunk:value", collections.defaultdict(dict))
                    v["kerchunk:value"][index] = refs[k]
                elif v := item.properties["cube:variables"].get(variable):
                    v.setdefault("kerchunk:value", collections.defaultdict(dict))
                    v["kerchunk:value"][index] = refs[k]

    for attr in ["cube:dimensions", "cube:variables"]:
        for k in item.properties[attr]:
            v = item.properties[attr][k].get("kerchunk:value")
            if v:
                item.properties[attr][k]["kerchunk:value"] = dict(v)
    return item


def stac_to_kerchunk(item: pystac.Item, kerchunk_version: int = 1) -> dict[str, Any]:
    """
    Derive Kerchunk indices from a STAC item.
    """
    refs = {}
    refs[".zgroup"] = json.dumps(item.properties["kerchunk:zgroup"])
    refs[".zattrs"] = json.dumps(item.properties["kerchunk:zattrs"])

    for attr in ["cube:dimensions", "cube:variables"]:
        cd = item.properties[attr]
        for k in cd:
            refs[f"{k}/.zarray"] = json.dumps(cd[k]["kerchunk:zarray"])
            # TODO: derive from datacube stuff, ARRAY_DIMENSIONS
            refs[f"{k}/.zattrs"] = json.dumps(cd[k]["kerchunk:zattrs"])
            for i in cd[k]["kerchunk:value"]:
                refs[f"{k}/{i}"] = cd[k]["kerchunk:value"][i]

    d = {"version": kerchunk_version, "refs": refs}
    return d
