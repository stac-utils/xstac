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

variables = ["hurs", "huss", "pr", "rlds", "rsds", "sfcWind", "tas", "tasmax", "tasmin"]
historical_years = set(range(1950, 2015))
ssp_years = list(range(2015, 2101))
models = [
    "ACCESS-CM2",
    "ACCESS-ESM1-5",
    "BCC-CSM2-MR",
    "CESM2",
    "CESM2-WACCM",
    "CMCC-CM2-SR5",
    "CMCC-ESM2",
    "CNRM-CM6-1",
    "CNRM-ESM2-1",
    "CanESM5",
    "EC-Earth3",
    "EC-Earth3-Veg-LR",
    "FGOALS-g3",
    "GFDL-CM4",
    "GFDL-CM4_gr2",
    "GFDL-ESM4",
    "GISS-E2-1-G",
    "HadGEM3-GC31-LL",
    "HadGEM3-GC31-MM",
    "IITM-ESM",
    "INM-CM4-8",
    "INM-CM5-0",
    "IPSL-CM6A-LR",
    "KACE-1-0-G",
    "KIOST-ESM",
    "MIROC-ES2L",
    "MIROC6",
    "MPI-ESM1-2-HR",
    "MPI-ESM1-2-LR",
    "MRI-ESM2-0",
    "NESM3",
    "NorESM2-LM",
    "NorESM2-MM",
    "TaiESM1",
    "UKESM1-0-LL",
]
scenarios = ["historical", "ssp245", "ssp585"]


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
    keywords = ["CMIP6", "NASA", "Climate", "Humidity", "Precipitation", "Temperature"]
    extra_fields = {
        "msft:storage_account": "nasagddp",
        "msft:container": "nex-gddp-cmip6",
        "msft:short_description": (
            "Global downscaled climate scenarios derived from the General Circulation Model "
            "conducted under CMIP6.",
        ),
    }
    providers = [
        pystac.Provider(
            "NASA NEX",
            roles=[pystac.ProviderRole.PRODUCER],
            url="https://www.nasa.gov/nex",
        ),
        pystac.Provider(
            "Microsoft",
            roles=[pystac.ProviderRole.HOST, pystac.ProviderRole.PROCESSOR],
            url="https://planetarycomputer.microsoft.com/",
        ),
    ]
    template = pystac.Collection(
        "nasa-nex-gddp-cmip6",
        description="{{ collection.description }}",
        extent=extent,
        keywords=keywords,
        extra_fields=extra_fields,
        providers=providers,
        title="Earth Exchange Global Daily Downscaled Projections (NEX-GDDP-CMIP6)",
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

    # Summaries
    r.summaries.maxcount = 50
    summaries = {
        "cmip6:model": models,
        "cmip6:variable": variables,
        "cmip6:scenario": scenarios,
    }
    for k, v in summaries.items():
        r.summaries.add(k, v)

    # Item assets
    item_assets = pystac.extensions.item_assets.ItemAssetsExtension.ext(
        r, add_if_missing=True
    )

    definitions = {}
    for k, v in ext.variables.items():
        asset = pystac.extensions.item_assets.AssetDefinition({})
        asset.description = v.description
        asset.title = v.properties["attrs"]["long_name"]
        asset.media_type = "application/netcdf"
        asset.roles = ["data"]
        definitions[k] = asset

    item_assets.item_assets = definitions

    reference_fs = adlfs.AzureBlobFileSystem("nasagddp")
    for reference_file in reference_fs.ls("/nex-gddp-cmip6-references"):
        # TODO: Access from the collection
        model, scenario = pathlib.Path(reference_file).stem.split("_")
        asset = pystac.Asset(
            f"https://nasagddp.blob.core.windows.net/{reference_file}",
            title=f"{model}-{scenario} references",
            media_type="application/json",
            roles=["references"],
            extra_fields={
                "xarray:open_dataset_kwargs": {
                    "engine": "zarr",
                    "backend_kwargs": {"consolidated": False, "chunks": {}},
                },
                "cmip6:model": model,
                "cmip6:scenario": scenario,
            },
        )
        r.add_asset(".".join([model, scenario]), asset)

    r.validate()

    with open(HERE / "collection.json", "w") as f:
        json.dump(r.to_dict(), f, indent=2)


if __name__ == "__main__":
    main()
