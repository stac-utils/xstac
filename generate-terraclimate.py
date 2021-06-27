"""
Generate STAC Collections for Daymet from the Zarr Groups.

python generate-terraclimate.py examples/terraclimate.json
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
        "outfile", nargs="?", type=argparse.FileType("w"), default=sys.stdout
    )

    return parser.parse_args(args)


def main(args=None):
    args = parse_args(args)
    outfile = args.outfile

    store = fsspec.get_mapper(
        "az://cpdata/raw/terraclimate/4000m/raster.zarr", account_name="cpdataeuwest"
    )
    ds = xr.open_zarr(store, consolidated=True)

    collection = xstac.xarray_to_stac(
        ds,
        f"terraclimate",
        description=f"TerraClimate is a dataset of monthly climate and climatic water balance for global terrestrial surfaces from 1958-2019. These data provide important inputs for ecological and hydrological studies at global scales that require high spatial resolution and time-varying data. All data have monthly temporal resolution and a ~4-km (1/24th degree) spatial resolution. The data cover the period from 1958-2020. We plan to update these data periodically (annually).",  # noqa
        license="proprietary",
        reference_system=4326,
        keywords=[
            "terraclimate",
            "actual evapotransporation",
            "climatic water deficit",
            "palmer drought severity index",
            "reference evapotransporation",
            "acculumated precipitation",
            "runoff",
            "soil moisture",
            "downward shortwave radiance flux",
            "snow water equivalent",
            "temperature",
            "vapor pressure",
            "wind speed",
        ],
        stac_version="1.0.0",
        temporal_dimension="time",
        x_dimension="lon",
        y_dimension="lat",
    )

    # fixups
    collection.extent.spatial.bboxes[0] = [[-180, -90, 180, 90]]

    collection.title = f"Terraclimate"
    # collection.links.append(
    #     pystac.Link(
    #         rel="license",
    #         target="https://science.nasa.gov/earth-science/earth-science-data/data-information-policy",
    #     )
    # )
    collection.providers = [
        pystac.Provider(
            name="Microsoft",
            roles=["host", "processor"],
            url="https://planetarycomputer.microsoft.com",
        ),
        pystac.Provider(
            name="Climatology Lab",
            roles=["producer"],
            url="http://www.climatologylab.org/terraclimate.html",
        ),

        pystac.Provider(
            name="Abatzoglou, J.T., S.Z. Dobrowski, S.A. Parks, K.C. Hegewisch",
            roles=["producer"],
            url="https://www.nature.com/articles/sdata2017191",
        ),
    ]
    collection.add_asset(
        key="zarr-https",
        asset=pystac.Asset(
            href=f"https://cpdataeuwest.blob.core.windows.net/cpdata/raw/terraclimate/4000m/raster.zarr",
            title=f"Terraclimate HTTPS Zarr root",
            description=f"HTTPS URI of the Terraclimate Zarr Group on Azure Blob Storage.",
            roles=["data", "zarr", "https"],
            media_type=ZARR_MEDIA_TYPE,
        ),
    )
    collection.add_asset(
        key="zarr-abfs",
        asset=pystac.Asset(
            href=f"az://cpdata/raw/terraclimate/4000m/raster.zarr",
            title=f"Terraclimate Azure Blob File System Zarr root",
            description=f"Azure Blob File System URI of the Terraclimate Zarr Group on Azure Blob Storage for use with adlfs.",
            roles=["data", "zarr", "abfs"],
            media_type=ZARR_MEDIA_TYPE,
        ),
    )
    collection.add_asset(
        key="thumbnail",
        asset=pystac.Asset(
            title=f"Terraclimate thumbnail",
            href=f"https://ai4edatasetspublicassets.blob.core.windows.net/assets/pc_thumbnails/additional_datasets/RWz0Zk.jpg",
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
    ] = f"High-resolution global dataset of monthly climate and climatic water balance."
    result["msft:storage_account"] = "cpdataeuwest"
    result["msft:container"] = "cpdata"

    # additional dimensions not implemented in xstac
    # result["cube:dimensions"]["nv"] = {
    #     "type": "count",
    #     "description": "Size of the 'time_bnds' variable.",
    #     "values": [0, 1],
    # }

    # remove unset values
    for obj in ["cube:variables", "cube:dimensions"]:
        for var in list(result[obj]):
            for k, v in list(result[obj][var].items()):
                if v is None:
                    del result[obj][var][k]

    for link in result["links"]:
        if link["rel"] == "root":
            link["href"] = "../catalog.json"

    with outfile as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    sys.exit(main())
