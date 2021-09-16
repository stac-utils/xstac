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
from pathlib import Path

import xstac
import pystac

BBOX = {
    "hi": [-160.3056, 17.9539, -154.772, 23.5186],
    "na": [-178.1333, 14.0749, -53.0567, 82.9143],
    "pr": [-67.9927, 16.8444, -64.1196, 19.9382],
}
DESC = {
    "daily": "Gridded estimates of daily weather parameters. Daymet Version 4 variables include the following parameters: minimum temperature, maximum temperature, precipitation, shortwave radiation, vapor pressure, snow water equivalent, and day length.",
    "monthly": "Monthly climate summaries derived from Daymet Version 4 daily data at a 1 km x 1 km spatial resolution for five Daymet variables: minimum and maximum temperature, precipitation, vapor pressure, and snow water equivalent. Monthly averages are provided for minimum and maximum temperature, vapor pressure, and snow water equivalent, and monthly totals are provided for the precipitation variable.",
    "annual": "Annual climate summaries derived from Daymet Version 4 daily data at a 1 km x 1 km spatial resolution for five Daymet variables: minimum and maximum temperature, precipitation, vapor pressure, and snow water equivalent. Annual averages are provided for minimum and maximum temperature, vapor pressure, and snow water equivalent, and annual totals are provided for the precipitation variable.",
}
CITATION_URLS = {
    "daily": "https://doi.org/10.3334/ORNLDAAC/1840",
    "monthly": "https://doi.org/10.3334/ORNLDAAC/1855",
    "annual": "https://doi.org/10.3334/ORNLDAAC/1852",
}

FULL_REGIONS = {"hi": "Hawaii", "na": "North America", "pr": "Puerto Rico"}
ZARR_MEDIA_TYPE = "application/vnd+zarr"
FREQUENCIES = ["daily", "monthly", "annual"]


def parse_args(args=None):
    parser = argparse.ArgumentParser(usage=__doc__)
    parser.add_argument(
        "--region", type=str, choices=["all", "hi", "pr", "na"], default="all"
    )
    parser.add_argument(
        "--frequency",
        type=str,
        choices=["all", "daily", "monthly", "annual"],
        default="all",
    )
    return parser.parse_args(args)


def generate(frequency, region):
    other_regions = " and ".join(
        [FULL_REGIONS[key] for key in FULL_REGIONS.keys() if key != region]
    )
    short_desc_snippet = (
        "surface weather data" if frequency == "daily" else "climate summaries"
    )

    template = {
        "id": f"daymet-{frequency}-{region}",
        "description": f"{DESC[frequency]} This dataset provides coverage for {FULL_REGIONS[region]} - {other_regions} are provided in [separate datasets](https://planetarycomputer.microsoft.com/dataset/group/daymet#{frequency}).\n\n[Daymet](https://daymet.ornl.gov/) provides measurements of near-surface meteorological conditions; the main purpose is to provide data estimates where no instrumentation exists.\n\nThe dataset covers the period from January 1, 1980 to the present. Each year is processed individually at the close of a calendar year. Data are in a Lambert Conformal Conic projection for North America and are distributed in Zarr and netCDF format compliant with [Climate and Forecast (CF) metadata conventions (version 1.6)](http://cfconventions.org/).",  # noqa
        "type": "Collection",
        "title": f"Daymet {frequency.title()} {FULL_REGIONS[region]}",
        "license": "proprietary",
        "keywords": [
            "daymet",
            FULL_REGIONS[region].lower(),
            "temperature",
            "precipitation",
            "vapor pressure",
            "swe",
            "weather" if frequency == "daily" else "climate",
        ],
        "stac_version": "1.0.0",
        "links": [
            # {"rel": "root", "href": "../catalog.json", "type": "application/json"},
            {
                "rel": "license",
                "href": "https://science.nasa.gov/earth-science/earth-science-data/data-information-policy",
            }
        ],
        "extent": {"spatial": {"bbox": [BBOX[region]]}},
        "providers": [
            {
                "name": "Microsoft",
                "roles": ["host", "processor"],
                "url": "https://planetarycomputer.microsoft.com",
            },
            {
                "name": "ORNL DAAC",
                "roles": ["producer"],
                "url": CITATION_URLS[frequency],
            },
        ],
        "assets": {
            "zarr-https": {
                "href": f"https://daymeteuwest.blob.core.windows.net/daymet-zarr/{frequency}/{region}.zarr",
                "type": "application/vnd+zarr",
                "title": f"{frequency.title()} {FULL_REGIONS[region]} Daymet HTTPS Zarr root",
                "description": f"HTTPS URI of the {frequency} {FULL_REGIONS[region]} Daymet Zarr Group on Azure Blob Storage.",
                "roles": ["data", "zarr", "https"],
            },
            "zarr-abfs": {
                "href": f"abfs://daymet-zarr/{frequency}/{region}.zarr",
                "type": "application/vnd+zarr",
                "title": f"{frequency.title()} {FULL_REGIONS[region]} Daymet Azure Blob File System Zarr root",
                "description": f"Azure Blob File System of the {frequency} {FULL_REGIONS[region]} Daymet Zarr Group on Azure Blob Storage for use with adlfs.",
                "roles": ["data", "zarr", "abfs"],
            },
            "thumbnail": {
                "href": f"https://ai4edatasetspublicassets.blob.core.windows.net/assets/pc_thumbnails/daymet-{frequency}-{region}.png",
                "type": "image/png",
                "title": f"Daymet {frequency} {FULL_REGIONS[region]} map thumbnail",
            },
        },
        "msft:short_description": f"{frequency.title()} {short_desc_snippet} on a 1-km grid for {FULL_REGIONS[region]}.",
        "msft:storage_account": "daymeteuwest",
        "msft:container": "daymet-zarr",
        "msft:group_id": "daymet",
        "msft:group_keys": [frequency, FULL_REGIONS[region].lower()],
    }

    store = fsspec.get_mapper(
        f"az://daymet-zarr/{frequency}/{region}.zarr", account_name="daymeteuwest"
    )
    ds = xr.open_zarr(store, consolidated=True)
    if "yearday" in ds:
        ds.yearday.attrs["long_name"] = ds.yearday.attrs["long_name"].replace(
            "Januaray", "January"
        )

    collection = xstac.xarray_to_stac(
        ds, template, temporal_dimension="time", x_dimension="x", y_dimension="y"
    )

    # getting a failure I don't understand when actually validating with the extension.
    collection.stac_extensions.append(
        "https://stac-extensions.github.io/datacube/v2.0.0/schema.json"
    )
    result = collection.to_dict(include_self_link=False)

    # additional dimensions not implemented in xstac
    result["cube:dimensions"]["nv"] = {
        "type": "count",
        "description": "Size of the 'time_bnds' variable.",
        "values": [0, 1],
    }

    for link in result["links"]:
        if link["rel"] == "root":
            link["href"] = "../catalog.json"
            link["rel"] = str(link["rel"].value)
            link["type"] = str(link["type"].value)

    return result


def main(args=None):
    args = parse_args(args)
    region = args.region
    frequency = args.frequency

    if region == "all":
        regions = list(FULL_REGIONS)
    else:
        regions = [region]

    if frequency == "all":
        frequencies = FREQUENCIES
    else:
        frequencies = [frequency]

    for region in regions:
        for frequency in frequencies:
            outfile = Path(__file__).parent / f"{frequency}/{region}.json"
            result = generate(frequency, region)

            with open(outfile, "w") as f:
                json.dump(result, f, indent=2)


if __name__ == "__main__":
    sys.exit(main())
