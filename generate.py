"""
Generate STAC Collections for Daymet from the Zarr Groups.

python generate.py hi daily examples/daymet/daily/hi.json
python generate.py hi monthly examples/daymet/monthly/hi.json
python generate.py hi annual examples/daymet/annual/hi.json

python generate.py na daily examples/daymet/daily/na.json
python generate.py na monthly examples/daymet/monthly/na.json
python generate.py na annual examples/daymet/annual/na.json

python generate.py pr daily examples/daymet/daily/pr.json
python generate.py pr monthly examples/daymet/monthly/pr.json
python generate.py pr annual examples/daymet/annual/pr.json


"""
import sys
import argparse
import json
import fsspec
import xarray as xr

import xstac
import pystac

BBOX = {
    "hi": [-160.3056, 17.9539, -154.772, 23.5186],
    "na": [-178.1333, 14.0749, -53.0567, 82.9143],
    "pr": [-67.9927, 16.8444, -64.1196, 19.9382],
}
TITLE = {
    ("hi", "daily"): "Daymet daily Hawaii",
    ("hi", "monthly"): "Daymet monthly Hawaii",
    ("hi", "annual"): "Daymet annual Hawaii",
    ("na", "daily"): "Daymet daily North America",
    ("na", "monthly"): "Daymet monthly North America",
    ("na", "annual"): "Daymet annual North America",
    ("pr", "daily"): "Daymet daily Puerto Rico",
    ("pr", "monthly"): "Daymet monthly Puerto Rico",
    ("pr", "annual"): "Daymet annual Puerto Rico",
}
CITATION_URLS = {
    "daily": "https://doi.org/10.3334/ORNLDAAC/1840",
    "monthly": "https://doi.org/10.3334/ORNLDAAC/1855",
    "annual": "https://doi.org/10.3334/ORNLDAAC/1852",
}

FULL_REGIONS = {
    "hi": "Hawaii",
    "na": "North America",
    "pr": "Puerto Rico",
}
ZARR_MEDIA_TYPE = "application/vnd+zarr"


def parse_args(args=None):
    parser = argparse.ArgumentParser(usage=__doc__)
    parser.add_argument("region", type=str, choices=["hi", "pr", "na"])
    parser.add_argument("frequency", type=str, choices=["daily", "monthly", "annual"])
    parser.add_argument(
        "outfile", nargs="?", type=argparse.FileType("w"), default=sys.stdout
    )

    return parser.parse_args(args)


def main(args=None):
    args = parse_args(args)
    region = args.region
    frequency = args.frequency
    outfile = args.outfile

    store = fsspec.get_mapper(
        f"az://daymet-zarr/{frequency}/{region}.zarr", account_name="daymeteuwest"
    )
    ds = xr.open_zarr(store, consolidated=True)

    # Fix bad metadata
    for k, v in ds.lambert_conformal_conic.attrs.items():
        if isinstance(v, list) and len(v) == 1:
            ds.lambert_conformal_conic.attrs[k] = v[0]

    collection = xstac.xarray_to_stac(
        ds,
        f"daymet-{frequency}-{region}",
        description="Estimates of daily weather parameters in North America on a one-kilometer grid, with monthly and annual summaries.\n\n[Daymet](https://daymet.ornl.gov/) provides measurements of near-surface meteorological conditions; the main purpose of Daymet is provide data estimates where no instrumentation exists.\n\nThis dataset provides Daymet Version 4 data for North America, including the island areas of Hawaii and Puerto Rico (which are available as files separate from the continental land mass). Daymet output variables include minimum temperature, maximum temperature, precipitation, shortwave radiation, vapor pressure, snow water equivalent, and day length. The dataset covers the period from January 1, 1980 to the present. Each year is processed individually at the close of a calendar year. Daymet variables are continuous surfaces  at 1-kilometer spatial resolution and daily temporal resolution. Data are in a Lambert Conformal Conic projection for North America and are distributed in Zarr format and netCDF format compliant with [Climate and Forecast (CF) metadata conventions (version 1.6)](http://cfconventions.org/).",  # noqa
        license="proprietary",
        stac_version="1.0.0",
        temporal_dimension="time",
        x_dimension="x",
        y_dimension="y",
    )

    # fixups
    # bboxes doesn't handle the half pixel yet
    collection.extent.spatial.bboxes[0] = BBOX[region]

    collection.title = f"Daymet {frequency.title()} {FULL_REGIONS[region]}"
    collection.links.append(
        pystac.Link(
            rel="license",
            target="https://science.nasa.gov/earth-science/earth-science-data/data-information-policy",
        )
    )
    collection.providers = [
        pystac.Provider(
            name="Microsoft",
            roles=["host", "processor"],
            url="https://planetarycomputer.microsoft.com",
        ),
        pystac.Provider(
            name="ORNL DAAC",
            roles=["producer"],
            url=CITATION_URLS[frequency],
        ),
    ]
    collection.add_asset(
        key="zarr-https",
        asset=pystac.Asset(
            href=f"https://daymeteuwest.blob.core.windows.net/daymet-zarr/{frequency}/{region}.zarr",
            title=f"{frequency.title()} {FULL_REGIONS[region]} Daymet HTTPS Zarr root",
            description=f"HTTPS URI of the {frequency} {FULL_REGIONS[region]} Daymet Zarr Group on Azure Blob Storage.",
            roles=["data", "zarr", "https"],
            media_type=ZARR_MEDIA_TYPE,
        ),
    )
    collection.add_asset(
        key="zarr-abfs",
        asset=pystac.Asset(
            href=f"abfs://daymet-zarr/{frequency}/{region}.zarr",
            title=f"{frequency.title()} {FULL_REGIONS[region]} Daymet Azure Blob File System Zarr root",
            description=f"Azure Blob File System of the {frequency} {FULL_REGIONS[region]} Daymet Zarr Group on Azure Blob Storage for use with adlfs.",
            roles=["data", "zarr", "abfs"],
            media_type=ZARR_MEDIA_TYPE,
        ),
    )
    collection.add_asset(
        key="thumbnail",
        asset=pystac.Asset(
            title="Daymet North America Temperature Map",
            href="https://ai4edatasetspublicassets.blob.core.windows.net/assets/pc_thumbnails/daymet-na.jpg",
            media_type="image/png",
        ),
    )

    # getting a failure I don't understand when actually validating with the extension.
    collection.stac_extensions.append(
        "https://stac-extensions.github.io/datacube/v1.0.0/schema.json"
    )
    # collection.normalize_hrefs("/")
    # collection.validate_all()
    result = collection.to_dict(include_self_link=False)
    result[
        "msft:short_description"
    ] = "Estimates of daily weather parameters in North America on a one-kilometer grid, with monthly and annual summaries."
    result["msft:storage_account"] = "daymeteuwest"
    result["msft:container"] = "daymet-zarr"

    # additional dimensions not implemented in xstac
    result["cube:dimensions"]["nv"] = {
        "type": "count",
        "description": "Size of the 'time_bnds' variable.",
        "values": [0, 1],
    }

    # remove unset values
    for obj in ["cube:variables", "cube:dimensions"]:
        for var in list(result[obj]):
            for k, v in list(result[obj][var].items()):
                if v is None:
                    del result[obj][var][k]

    for link in result["links"]:
        if link["rel"] == "root":
            link["href"] = "../collection.json"

    with outfile as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    sys.exit(main())

