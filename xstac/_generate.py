"""
Generate STAC Collections for Daymet from the Zarr Groups.

xstac template.json asset-key output.json
"""
import copy
import sys
import argparse
import json
import fsspec
import cf_xarray  # noqa: F401
import xarray as xr

import xstac
import pystac

ZARR_MEDIA_TYPE = "application/vnd+zarr"
SCHEMA_URI = "https://stac-extensions.github.io/datacube/v2.0.0/schema.json"


def parse_args(args=None):
    parser = argparse.ArgumentParser(usage=__doc__)
    parser.add_argument(
        "template",
        nargs="?",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="Template STAC Collection to merge with the result.",
    )
    parser.add_argument(
        "asset",
        help="Asset key to use to load the data. Must be present in the template file's 'assets'.",
    )
    parser.add_argument(
        "outfile",
        nargs="?",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="Output file to write to. Defaults to stdout.",
    )

    parser.add_argument("--reference-system", default=None)
    parser.add_argument(
        "--temporal_dimension", help="Coordinate name for the 'time' dimension"
    )
    parser.add_argument("--x-dimension", help="Coordinate name for the 'x' dimension")
    parser.add_argument("--y-dimension", help="Coordinate name for the 'y' dimension")
    parser.add_argument(
        "--no-validate",
        action="store_false",
        help="Whether to skip validation of the collection.",
    )

    return parser.parse_args(args)


def generate(
    template,
    asset_key,
    x_dimension=None,
    y_dimension=None,
    temporal_dimension=None,
    reference_system=None,
    validate: bool = True,
):
    template = copy.deepcopy(template)
    template.setdefault("type", "Collection")
    template.setdefault("stac_version", pystac.get_stac_version())
    template.setdefault("links", [])
    asset = template["assets"][asset_key]

    store = fsspec.get_mapper(asset["href"], **asset.get("xarray:storage_options", {}))
    ds = xr.open_zarr(store, **asset.get("xarray:open_kwargs", {}))

    collection = xstac.xarray_to_stac(
        ds,
        template,
        reference_system=reference_system,
        temporal_dimension=temporal_dimension,
        x_dimension=x_dimension,
        y_dimension=y_dimension,
        validate=validate,
    )
    collection.set_self_href("collection.json")
    result = collection.to_dict(include_self_link=False)
    # Remove the root link. Do we want to do this?
    result["links"] = [x for x in result["links"] if x["rel"] != "root"]
    collection.validate()

    return result


def main(args=None):
    args = parse_args(args)
    outfile = args.outfile
    asset_key = args.asset
    reference_system = args.reference_system
    temporal_dimension = args.temporal_dimension
    x_dimension = args.x_dimension
    y_dimension = args.y_dimension
    validate = not args.no_validate

    if reference_system and reference_system.isdigit():
        reference_system = int(reference_system)

    with args.template as f:
        template = json.load(f)

    result = generate(
        template,
        asset_key=asset_key,
        x_dimension=x_dimension,
        y_dimension=y_dimension,
        temporal_dimension=temporal_dimension,
        reference_system=reference_system,
        validate=validate,
    )

    with outfile as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    sys.exit(main())
