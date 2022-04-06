import json
import xstac
import datetime
import adlfs
import pystac
import xarray as xr
import itertools
import pathlib
import fsspec


def key(path):
    fc_vars = {
        "air_temperature_at_2_metres_1hour_Maximum",
        "air_temperature_at_2_metres_1hour_Minimum",
        "integral_wrt_time_of_surface_direct_downwelling_shortwave_flux_in_air_1hour_Accumulation",
        "precipitation_amount_1hour_Accumulation",
    }
    p = pathlib.Path(path)
    return p.stem in fc_vars


def group_paths(paths):
    paths = sorted(paths, key=key)
    for k, v in itertools.groupby(paths, key=key):
        v = list(v)
        k2 = "fc" if k else "an"
        yield k2, v


def name_item(root, kind):
    *_, year, month = root.rstrip("/").split("/")
    return "-".join(["era5-pds", year, month, kind])


def make_item(kind, store_paths, protocol, storage_options=None):
    """
    root like 'era5/ERA5/1979/01/'
    """
    storage_options = storage_options or {}
    fs = fsspec.filesystem(protocol, **storage_options)
    dss = [
        xr.open_dataset(fs.get_mapper(store), engine="zarr", consolidated=True)
        for store in store_paths
    ]
    ds = xr.combine_by_coords(dss, join="exact")
    properties = {"start_datetime": None, "end_datetime": None, "era5:kind": kind}
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
    item_id = name_item(store_paths[0].rsplit("/", 1)[0], kind)

    template = pystac.Item(
        item_id,
        geometry=geometry,
        bbox=bbox,
        datetime=None,
        properties=properties,
    )
    item = xstac.xarray_to_stac(
        ds,
        template,
        temporal_dimension="time",
        x_dimension="lon",
        y_dimension="lat",
        reference_system="epsg:4326",
    )

    # ds_stores = [x for x in store_paths if pathlib.Path(x).stem in ds.data_vars]

    asset_extra_fields = {
        "xarray:open_kwargs": {
            "engine": "zarr",
            "chunks": {},
            "consolidated": True,
            "storage_options": {"account_name": fs.account_name},
        }
    }
    for store in store_paths:
        p = pathlib.Path(store)
        v = ds[p.stem]
        item.add_asset(
            p.stem,
            pystac.Asset(
                f"{fs.protocol}://{store}",
                title=v.attrs["long_name"],
                media_type="application/vnd+zarr",
                roles=["data"],
                extra_fields=asset_extra_fields,
            ),
        )

    return item


def make_collection():
    with open("collection_datacube.json") as f:
        collection_datacube = json.load(f)

    extent = pystac.Extent(
        spatial=pystac.SpatialExtent(bboxes=[[-180, -90, 180, 90]]),
        temporal=pystac.TemporalExtent(
            intervals=[
                datetime.datetime(1979, 1, 1),
                None,
            ]
        ),
    )
    keywords = [
        "ERA5",
        "ECMWF",
        "Precipitation",
        "Temperature",
        "Reanalysis",
        "Weather",
    ]
    providers = [
        pystac.Provider(
            "ECMWF",
            roles=[pystac.ProviderRole.PRODUCER, pystac.ProviderRole.LICENSOR],
            url="https://www.ecmwf.int/",
        ),
        pystac.Provider(
            "Planet OS",
            roles=[pystac.ProviderRole.PROCESSOR],
            url="https://planetos.com/",
        ),
        pystac.Provider(
            "Microsoft",
            roles=[pystac.ProviderRole.HOST],
            url="https://planetarycomputer.microsoft.com/",
        ),
    ]
    extra_fields = {
        "msft:storage_account": "cpdataeuwest",
        "msft:container": "era5",
        "msft:short_description": (
            "A comprehensive reanalysis, which assimilates as many observations "
            "as possible in the upper air and near surface."
        ),
    }
    extra_fields.update(collection_datacube)
    collection_id = "era5-pds"

    r = pystac.Collection(
        collection_id,
        description="{{ collection.description }}",
        extent=extent,
        keywords=keywords,
        extra_fields=extra_fields,
        providers=providers,
        title="ERA5 PDS",
        license="proprietary",
    )
    r.add_links(
        [
            pystac.Link(
                rel=pystac.RelType.LICENSE,
                target="https://apps.ecmwf.int/datasets/licences/copernicus/",
                media_type="application/pdf",
                title="License to Use Copernicus Products",
            ),
            pystac.Link(
                rel="describedby",
                target="https://confluence.ecmwf.int/display/CKB/ERA5",
                media_type="text/html",
                title="Project homepage",
            ),
            pystac.Link(
                rel="describedby",
                target="https://confluence.ecmwf.int/display/CKB/How+to+acknowledge+and+cite+a+Climate+Data+Store+%28CDS%29+catalogue+entry+and+the+data+published+as+part+of+it",  # noqa
                media_type="text/html",
                title="How to cite",
            ),
        ]
    )
    r.add_asset(
        "thumbnail",
        pystac.Asset(
            "https://ai4edatasetspublicassets.blob.core.windows.net/assets/pc_thumbnails/gdpcir.png",
            title="Thumbnail",
            media_type=pystac.MediaType.PNG,
        ),
    )

    # Summaries
    r.summaries.maxcount = 50
    summaries = {
        "era5:kind": ["fc", "an"],
    }
    for k, v in summaries.items():
        r.summaries.add(k, v)

    r.stac_extensions.append(
        "https://stac-extensions.github.io/datacube/v2.0.0/schema.json"
    )
    # pystac.extensions.item_assets.ItemAssetsExtension.ext(r, add_if_missing=True)
    # r.extra_fields["item_assets"] = item_assets
    r.set_self_href("collection.json")

    r.validate()
    r.remove_links(pystac.RelType.SELF)
    r.remove_links(pystac.RelType.ROOT)

    pathlib.Path(f"{r.id}.json").write_text(json.dumps(r.to_dict(), indent=2))


def do():
    import tqdm.notebook
    import dask
    import dask.distributed

    asset_credential = ""
    storage_options = dict(account_name="cpdataeuwest", credential=asset_credential)
    fs = adlfs.AzureBlobFileSystem(**storage_options)
    roots = fs.glob("era5/ERA5/*/*")
    client = dask.distributed.Client()
    print(client.dashboard_address)

    ditems = []
    for root in tqdm.notebook.tqdm(roots):
        paths = fs.ls(root)
        for kind, store_paths in group_paths(paths):
            ditems.append(
                dask.delayed(make_item)(kind, store_paths, "abfs", storage_options)
            )

    items = dask.compute(ditems)
    print(len(items))


def make_collection_datacube(items):
    # generate from 2 items
    import copy

    collection_datacube = {"cube:variables": {}}
    for item in items:
        collection_datacube["cube:dimensions"] = copy.deepcopy(
            item.properties["cube:dimensions"]
        )
        collection_datacube["cube:dimensions"]["time"]["extent"] = [
            "1970-01-01T00:00:00Z",
            None,
        ]
        # variable by month
        collection_datacube["cube:variables"].update(
            copy.deepcopy(item.properties["cube:variables"])
        )

        for k, v in collection_datacube["cube:variables"].items():
            # variable length months
            v["shape"] = [None] + v["shape"][1:]

    return collection_datacube


if __name__ == "__main__":
    make_collection()
