"""
NASA NEX-GDDP-CMIP6

A global daily downscaled CMIP6 product.

## STAC Collection

We'll have... a single STAC collection. We'll use the `cube:variables` to include the

* dimensions (time, lon, lat)
* variables (hurs, huss, etc.)

We'll generate it using `xstac` from one specific dataset.

* https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6
* https://www.nccs.nasa.gov/sites/default/files/NEX-GDDP-CMIP6-Tech_Note.pdf
"""
import datetime
import pathlib
import json
from collections import namedtuple

import adlfs
import planetary_computer
import pystac
import xarray as xr
import xstac


HERE = pathlib.Path(__file__).parent
Parts = namedtuple("Parts", "model scenario variable year")


def split_path(path):
    _, _, _, model, scenario, _, variable, file = path.split("/")
    year = int(file.split(".")[0].split("_")[-1])
    return Parts(model, scenario, variable, year)


def path_to_item_id(path):
    """
    Item IDs are {model}.{scenario}.{variable}.{year}
    """
    p = split_path(path)
    return ".".join(list(map(str, p)))


def create_item(path):
    credential = planetary_computer.sas.get_token("nasagddp", "nex-gddp-cmip6").token
    fs = adlfs.AzureBlobFileSystem("nasagddp", credential=credential)

    template = pystac.Item(
        "item",
        geometry={
            "type": "Polygon",
            "coordinates": [
                [
                    [180.0, -90.0],
                    [180.0, 90.0],
                    [-180.0, 90.0],
                    [-180.0, -90.0],
                    [180.0, -90.0],
                ]
            ],
        },
        bbox=[-180, -90, 180, 90],
        datetime=None,
        properties={"start_datetime": None, "end_datetime": None},
    )
    ds = xr.open_dataset(fs.open(path))

    r = xstac.xarray_to_stac(ds, template, reference_system=4326)
    r.id = path_to_item_id(path)
    asset = pystac.Asset(
        f"https://nasagddp.blob.core.windows.net/{path}",
        media_type="application/netcdf",
        roles=["data"],
    )
    r.add_asset("data", asset)
    parts = split_path(path)

    for k, v in parts._asdict().items():
        r.extra_fields[f"cmip6:{k}"] = v

    return r


def main():
    # ------------------ Item ------------------
    path = (
        "nex-gddp-cmip6/NEX/GDDP-CMIP6/ACCESS-CM2/historical/r1i1p1f1/hurs/"
        "hurs_day_ACCESS-CM2_historical_r1i1p1f1_gn_1950.nc"
    )
    r = create_item(path)

    with open(HERE / "item.json", "w") as f:
        json.dump(r.to_dict(), f, indent=2)

    # ------------------ Collection ------------------
    # this takes a little while outside of west europe.
    credential = planetary_computer.sas.get_token("nasagddp", "nex-gddp-cmip6").token
    fs = adlfs.AzureBlobFileSystem("nasagddp", credential=credential)

    paths = fs.glob(
        "nex-gddp-cmip6/NEX/GDDP-CMIP6/ACCESS-CM2/historical/r1i1p1f1/*/*1950.nc"
    )
    datasets = [xr.open_dataset(fs.open(path)) for path in paths]
    ds = xr.merge(datasets)

    extent = pystac.Extent(
        spatial=pystac.SpatialExtent(bboxes=[[-180, -90, 180, 90]]),
        temporal=pystac.TemporalExtent(
            intervals=[datetime.datetime(1950, 1, 1), datetime.datetime(2100, 12, 31)]
        ),
    )
    template = pystac.Collection(
        "nasa-nex-gddp-cmip6", description="{{ collection.description }}", extent=extent
    )

    template.add_link(
        pystac.Link(
            rel=pystac.RelType.LICENSE,
            target="https://pcmdi.llnl.gov/CMIP6/TermsOfUse/TermsOfUse6-1.html",
            media_type="text/html",
        )
    )
    template.add_link(
        pystac.Link(
            "documentation",
            target="https://www.nccs.nasa.gov/sites/default/files/NEX-GDDP-CMIP6-Tech_Note.pdf",
            media_type="application/pdf",
        )
    )
    r = xstac.xarray_to_stac(ds, template, reference_system=4326)

    # We only loaded metadata for the first year. It actually runs through 2100.
    ext = pystac.extensions.datacube.DatacubeExtension.ext(r)
    time = ext.dimensions["time"]
    time.extent[1] = extent.temporal.intervals[0][1].isoformat() + "Z"
    # Assets aren't cloned, so set it here
    r.add_asset(
        "thumbnail",
        pystac.Asset(
            "https://ai4edatasetspublicassets.blob.core.windows.net/assets/pc_thumbnails/nasa-nex-gddp-thumbnail.png",
            title="thumbnail",
            media_type=pystac.MediaType.PNG,
            roles=["thumbnail"],
        ),
    )

    sci_ext = pystac.extensions.scientific.ScientificExtension.ext(
        r, add_if_missing=True
    )
    sci_ext.citation = (
        "Climate scenarios used were from the NEX-GDDP-CMIP6 dataset, prepared by the Climate "
        "Analytics Group and NASA Ames Research Center using the NASA Earth Exchange, and "
        "distributed by the NASA Center for Climate Simulation (NCCS)."
    )

    r.validate()

    # TODO: Add kerchunk assets.

    with open(HERE / "collection.json", "w") as f:
        json.dump(r.to_dict(), f, indent=2)


if __name__ == "__main__":
    main()
