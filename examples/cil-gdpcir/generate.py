import datetime
import json
import pathlib

# import adlfs
import fsspec
import xarray as xr

# import requests
import dataclasses
import xstac
import pystac

GROUPS = [
    "BCC",
    "CAS",
    "CCCma",
    "CMCC",
    "CSIRO",
    "CSIRO-ARCCSS",
    "DKRZ",
    "EC-Earth-Consortium",
    "INM",
    "MIROC",
    "MOHC",
    "MPI-M",
    "NCC",
    "NOAA-GFDL",
    "NUIST",
]
MODELS = [
    "ACCESS-CM2",
    "ACCESS-ESM1-5",
    "BCC-CSM2-MR",
    "CMCC-CM2-SR5",
    "CMCC-ESM2",
    "CanESM5",
    "EC-Earth3",
    "EC-Earth3-AerChem",
    "EC-Earth3-CC",
    "EC-Earth3-Veg",
    "EC-Earth3-Veg-LR",
    "FGOALS-g3",
    "GFDL-CM4",
    "GFDL-ESM4",
    "HadGEM3-GC31-LL",
    "INM-CM4-8",
    "INM-CM5-0",
    "MIROC-ES2L",
    "MIROC6",
    "MPI-ESM1-2-HR",
    "MPI-ESM1-2-LR",
    "NESM3",
    "NorESM2-LM",
    "NorESM2-MM",
    "UKESM1-0-LL",
]
SCENARIOS = ["historical", "ssp126", "ssp245", "ssp370", "ssp585"]
VARIABLES = ["pr", "tasmax", "tasmin"]
cmip6_item_attrs = [
    "Conventions",
    "activity_id",
    "data_specs_version",
    "experiment",
    "experiment_id",
    "forcing_index",
    "frequency",
    "further_info_url",
    "initialization_index",
    "institution",
    "institution_id",
    "license",
    "mip_era",
    "nominal_resolution",
    "physics_index",
    "product",
    "realization_index",
    "realm",
    "source",
    "source_id",
    "source_type",
    "sub_experiment",
    "sub_experiment_id",
    "table_id",
    "variant_label",
]

cmip6_asset_attrs = [
    "creation_date",
    "tracking_id",
    "variable_id",
    "grid",
    "grid_label",
]

# TODO: note in the description
# The shape can be either  {(23725, 720, 1440), (31390, 720, 1440)}
# Not all files contain "pr"

collection_datacube = {
    "cube:dimensions": {
        "time": {
            "extent": ["1950-01-01T12:00:00Z", "2100-12-31T12:00:00Z"],
            "description": "time",
            "step": "P1DT0H0M0S",
            "type": "temporal",
        },
        "lon": {
            "axis": "y",
            "extent": [-179.875, 179.875],
            "step": 0.25,
            "reference_system": "epsg:4326",
            "type": "spatial",
        },
        "lat": {
            "axis": "y",
            "extent": [-89.875, 89.875],
            "step": 0.25,
            "reference_system": "epsg:4326",
            "type": "spatial",
        },
    },
    "cube:variables": {
        "pr": {
            "type": "data",
            "dimensions": ["time", "lat", "lon"],
            "unit": "mm day-1",
            "attrs": {"units": "mm day-1"},
        },
        "tasmax": {
            "type": "data",
            "description": "Daily Maximum Near-Surface Air Temperature",
            "dimensions": ["time", "lat", "lon"],
            "unit": "K",
            "attrs": {
                "cell_measures": "area: areacella",
                "cell_methods": "area: mean time: maximum (interval: 5 minutes)",
                "comment": (
                    "maximum near-surface (usually, 2 meter) air temperature "
                    "(add cell_method attribute 'time: max')"
                ),
                "coordinates": "height",
                "long_name": "Daily Maximum Near-Surface Air Temperature",
                "original_name": "TREFHTMX",
                "standard_name": "air_temperature",
                "units": "K",
            },
        },
        "tasmin": {
            "type": "data",
            "description": "Daily Minimum Near-Surface Air Temperature",
            "dimensions": ["time", "lat", "lon"],
            "unit": "K",
            "attrs": {
                "cell_measures": "area: areacella",
                "cell_methods": "area: mean time: minimum (interval: 5 minutes)",
                "comment": (
                    "minimum near-surface (usually, 2 meter) air temperature "
                    "(add cell_method attribute 'time: min')"
                ),
                "coordinates": "height",
                "long_name": "Daily Minimum Near-Surface Air Temperature",
                "original_name": "TREFHTMN",
                "standard_name": "air_temperature",
                "units": "K",
            },
        },
    },
}
item_assets = {
    "pr": {
        "type": "application/vnd+zarr",
        "roles": ["data"],
        "title": "Precipitation",
        "description": "Precipitation",
    },
    "tasmax": {
        "type": "application/vnd+zarr",
        "roles": ["data"],
        "title": "Daily Maximum Near-Surface Air Temperature",
        "description": "Daily Maximum Near-Surface Air Temperature",
    },
    "tasmin": {
        "type": "application/vnd+zarr",
        "roles": ["data"],
        "title": "Daily Minimum Near-Surface Air Temperature",
        "description": "Daily Minimum Near-Surface Air Temperature",
    },
}


@dataclasses.dataclass
class Parts:
    group: str
    model: str
    scenario: str
    rthing: str
    temporal_frequency: str
    variable_id: str
    filename: str

    @property
    def item_id(self):
        return "-".join(
            [
                "cil-gdpcir",
                self.group,
                self.model,
                self.scenario,
                self.rthing,
                self.temporal_frequency,
            ]
        )

    @classmethod
    def from_path(cls, path):
        (
            *prefix,
            kind,
            group,
            model,
            scenario,
            rthing,
            temporal_frequency,
            variable_id,
            store,
        ) = path.split("/")
        return cls(
            group=group,
            model=model,
            scenario=scenario,
            rthing=rthing,
            temporal_frequency=temporal_frequency,
            variable_id=variable_id,
            filename=path,
        )


def create_item(root, protocol, storage_options=None):
    storage_options = storage_options or {}
    fs = fsspec.filesystem(protocol=protocol, **storage_options)
    paths = fs.glob(f"{root}/*/*")
    stores = [fs.get_mapper(v) for v in paths]
    dss = [xr.open_dataset(store, engine="zarr", consolidated=True) for store in stores]

    ds = xr.combine_by_coords(dss, join="exact", combine_attrs="drop_conflicts")
    p0 = Parts.from_path(paths[0])
    geometry = {
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
    }
    bbox = [-180, -90, 180, 90]

    template = pystac.Item(
        p0.item_id,
        geometry=geometry,
        bbox=bbox,
        datetime=None,
        properties={"start_datetime": None, "end_datetime": None},
    )
    item = xstac.xarray_to_stac(
        ds,
        template,
        x_dimension="lon",
        y_dimension="lat",
        temporal_dimension="time",
        reference_system="epsg:4326",
    )
    cmip6_properties = {f"cmip6:{k}": ds.attrs.get(k, None) for k in cmip6_item_attrs}
    item.properties.update(cmip6_properties)

    for i, path in enumerate(paths):
        parts = Parts.from_path(path)
        href = f"abfs://{path}"
        extra_fields = {
            "xarray:open_kwargs": {
                "engine": "zarr",
                "consolidated": True,
                "chunks": {},
                "storage_options": {"account_name": "rhgeuwest"},
            },
            "msft:https-url": f"https://rhgeuwest.blob.core.windows.net/{path}",
            # "cmip6:variable_id": parts.variable_id,
        }
        for k in cmip6_asset_attrs:
            extra_fields[f"cmip6:{k}"] = dss[i].attrs[k]

        item.add_asset(
            parts.variable_id,
            pystac.Asset(
                href, media_type="application/vnd+zarr", extra_fields=extra_fields
            ),
        )

    item.validate()
    return item


def make_collection():
    # TODO: sci
    # TODO: short description

    extent = pystac.Extent(
        spatial=pystac.SpatialExtent(bboxes=[[-180, -90, 180, 90]]),
        temporal=pystac.TemporalExtent(
            intervals=[datetime.datetime(1950, 1, 1), datetime.datetime(2011, 12, 31)]
        ),
    )
    keywords = [
        "CMIP6",
        "Climate Impact Lab",
        "Rhodium Group",
        "Precipitation",
        "Temperature",
    ]
    providers = [
        pystac.Provider(
            "Climate Impact Lab",
            roles=[pystac.ProviderRole.PRODUCER],
            url="https://impactlab.org/",
        ),
        pystac.Provider(
            "Microsoft",
            roles=[pystac.ProviderRole.HOST, pystac.ProviderRole.PROCESSOR],
            url="https://planetarycomputer.microsoft.com/",
        ),
    ]
    extra_fields = {
        "msft:storage_account": "rhgeuwest",
        "msft:container": "cil-gdpcir",
        "msft:short_description": (
            "Climate Impact Lab Global Downscaled Projections for Climate Impacts Research"
        ),
    }

    r = pystac.Collection(
        "cil-gdpcir",
        description="{{ collection.description }}",
        extent=extent,
        keywords=keywords,
        extra_fields=extra_fields,
        providers=providers,
        title="CIL Global Downscaled Projections for Climate Impacts Research",
    )
    r.add_link(
        pystac.Link(
            rel=pystac.RelType.LICENSE,
            target="TODO",
            media_type="text/html",
            title="License",
        ),
        pystac.Link(
            rel="describedby",
            target="https://github.com/ClimateImpactLab/downscaleCMIP6/",
            media_type="text/html",
            title="Project homepage",
        ),
    )
    r.add_asset(
        "thumbnail",
        pystac.Asset(
            "https://ai4edatasetspublicassets.blob.core.windows.net/assets/pc_thumbnails/gdpcir.png",
            title="Thumbnail",
            media_type=pystac.MediaType.PNG,
        ),
    )
    # r = xstac.xarray_to_stac(..., template)
    r.extra_fields.update(collection_datacube)

    # Summaries
    r.summaries.maxcount = 50
    summaries = {
        "cmip6:institution_id": GROUPS,
        "cmip6:source_id": MODELS,
        "cmip6:variable": VARIABLES,
        "cmip6:experiment_id": SCENARIOS,
    }
    for k, v in summaries.items():
        r.summaries.add(k, v)

    pystac.extensions.item_assets.ItemAssetsExtension.ext(r, add_if_missing=True)
    r.extra_fields["item_assets"] = item_assets
    r.set_self_href("collection.json")

    r.validate()
    r.remove_links(pystac.RelType.SELF)
    r.remove_links(pystac.RelType.ROOT)

    pathlib.Path("collection.json").write_text(json.dumps(r.to_dict(), indent=2))


def main():
    # credential = requests.get(
    #     "https://planetarycomputer-staging.microsoft.com/api/sas/v1/token/rhgeuwest/cil-gdpcir"
    # ).json()["token"]
    # fs = adlfs.AzureBlobFileSystem("rhgeuwest", credential=credential)
    # storage_options = {
    #     "account_name": "rhgeuwest",
    #     "credential": credential,
    # }
    make_collection()


if __name__ == "__main__":
    main()
