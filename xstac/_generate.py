"""
Generate STAC Collections for Daymet from the Zarr Groups.

xstac template.json asset-key output.json
"""
import sys
import argparse
import json
import fsspec
import xarray as xr

import xstac
import pystac

ZARR_MEDIA_TYPE = "application/vnd+zarr"


def parse_args(args=None):
    parser = argparse.ArgumentParser(usage=__doc__)
    parser.add_argument(
        "template", nargs="?", type=argparse.FileType("r"), default=sys.stdin,
        help="Template STAC Collection to merge with the result."
    )
    parser.add_argument(
        "asset", help="Asset key to use to load the data. Must be present in the template file's 'assets'."
    )
    parser.add_argument(
        "outfile", nargs="?", type=argparse.FileType("w"), default=sys.stdout,
        help="Output file to write to. Defaults to stdout."
    )

    parser.add_argument(
        "--reference-system", default=None,
    )
    parser.add_argument(
        "--temporal_dimension", default="time", help="Coordinate name for the 'time' dimension",
    )
    parser.add_argument(
        "--x-dimension", default="x", help="Coordinate name for the 'x' dimension",
    )
    parser.add_argument(
        "--y-dimension", default="y", help="Coordinate name for the 'y' dimension",
    )

    return parser.parse_args(args)


def main(args=None):
    args = parse_args(args)
    outfile = args.outfile
    asset_key = args.asset
    reference_system = args.reference_system
    temporal_dimension = args.temporal_dimension
    x_dimension = args.x_dimension
    y_dimension = args.y_dimension

    with args.template as f:
        template = json.load(f)

    template.setdefault("type", "Collection")
    template.setdefault("stac_version", pystac.get_stac_version())
    template.setdefault("links", [])
    asset = template["assets"][asset_key]

    store = fsspec.get_mapper(
        asset["href"], **asset.get("storage_options", {})
    )
    ds = xr.open_zarr(store, **asset.get("xarray_kwargs", {}))

    collection = xstac.xarray_to_stac(
        ds,
        template,
        reference_system=reference_system,
        temporal_dimension=temporal_dimension,
        x_dimension=x_dimension,
        y_dimension=y_dimension,
    )
    collection.set_self_href("collection.json")
    collection.validate()
    # getting a failure I don't understand when actually validating with the extension.
    # Seems to think that the extent for items should be string, but extent_closed in the schema is a number.
    #     ValidationError: -179.97916666666666 is not of type 'string', 'null'
    #     Failed validating 'type' in schema[3]['properties']['extent']['items']:
    #         {'type': ['string', 'null']}

    #     On instance['extent'][0]:
    #         -179.97916666666666
    collection.stac_extensions.append(
        "https://stac-extensions.github.io/datacube/v1.0.0/schema.json"
    )
    # collection.normalize_hrefs("/")
    result = collection.to_dict(include_self_link=False)

    # remove unset values
    for obj in ["cube:variables", "cube:dimensions"]:
        for var in list(result[obj]):
            for k, v in list(result[obj][var].items()):
                if v is None:
                    del result[obj][var][k]

    # Remove the root link. Do we want to do this?
    result["links"] = [
        x for x in result["links"]
        if x["rel"] != "root"
    ]

    with outfile as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    sys.exit(main())
