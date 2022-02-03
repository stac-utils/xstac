import datetime
import json

import adlfs
import pystac
import planetary_computer
import xstac
import xarray as xr


VARIABLES = [
    "clt",
    "hurs",
    "huss",
    "pr",
    "psl",
    "rls",
    "rss",
    "sfcWind",
    "tas",
    "tasmax",
    "tasmin",
    "uas",
    "vas",
]
TEMPORAL_RESOLUTIONS = ["day", "mon"]


def main():
    # ------------------ Collection ------------------
    # this takes a little while outside of west europe.
    # we need separate for each daily, mon, etc. time_resolution
    account_name = "ukmeteuwest"
    container_name = "ukcp18"
    credential = planetary_computer.sas.get_token(account_name, container_name).token

    fs = adlfs.AzureBlobFileSystem("ukmeteuwest", credential=credential)
    paths = fs.glob(
        "ukcp18/badc/ukcp18/data/land-gcm/global/60km/rcp26/01/*/day/*/*18991201-19091130.nc"
    )
    print(len(paths))
    # hmm, 'sfcWind', 'uas' and 'vas' are apparently on a different grid? size 325 instead of 324.
    # so we exclude those three variables... We *might* be able to fake it and just load them up
    # up regardless.
    paths = [x for x in paths if x.split("/")[9] not in {"sfcWind", "uas", "vas"}]

    datasets = [xr.open_dataset(fs.open(path)) for path in paths]

    ds = xr.merge(datasets, join="exact")
    for k, v in ds.variables.items():
        attrs = {
            name: xr.backends.zarr.encode_zarr_attr_value(value)
            for name, value in v.attrs.items()
        }
        ds[k].attrs = attrs

    extent = pystac.Extent(
        spatial=pystac.SpatialExtent(bboxes=[[-180, -90, 180, 90]]),
        temporal=pystac.TemporalExtent(
            intervals=[datetime.datetime(1899, 12, 1), datetime.datetime(2100, 12, 31)]
        ),
    )
    keywords = ["UKCP18", "UK Met Office", "Climate"]
    extra_fields = {
        "msft:storage_account": "ukmeteuwest",
        "msft:container": "ukcp18",
        "msft:short_description": (
            "Global climate model runs from 1900-2100 produced by the Met Office for UK Climate "
            "Projections 2018 (UKCP18) using the HadGEM3 climate model."
        ),
    }
    providers = [
        pystac.Provider(
            "Met Office Hadley Centre",
            roles=[pystac.ProviderRole.PRODUCER],
            url="https://www.metoffice.gov.uk/weather/climate/met-office-hadley-centre/index",
        ),
        pystac.Provider(
            "The CEDA Archive",
            roles=[pystac.ProviderRole.HOST],
            url="https://archive.ceda.ac.uk/",
        ),
        pystac.Provider(
            "Microsoft",
            roles=[pystac.ProviderRole.HOST, pystac.ProviderRole.PROCESSOR],
            url="https://planetarycomputer.microsoft.com/",
        ),
    ]
    template = pystac.Collection(
        "ukcp-18",
        description="{{ collection.description }}",
        extent=extent,
        keywords=keywords,
        extra_fields=extra_fields,
        providers=providers,
        title="UKCP18 Global Climate Model Projections for the entire globe",
    )

    template.add_link(
        pystac.Link(
            rel=pystac.RelType.LICENSE,
            target="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
            title="Open Government License",
            media_type="text/html",
        )
    )
    template.add_link(
        pystac.Link(
            rel="documentation",
            title="UKCP18 Guidance: Data availability, access and formats",
            target=(
                "https://www.metoffice.gov.uk/binaries/content/assets/metofficegovuk/pdf/"
                "research/ukcp/ukcp18-guidance-data-availability-access-and-formats.pdf"
            ),
            media_type="application/pdf",
        )
    )
    template.add_link(
        pystac.Link(
            rel="documentation",
            title="UKCP18 Guidance: Caveats and limitations",
            target=(
                "https://www.metoffice.gov.uk/binaries/content/assets/metofficegovuk/pdf/"
                "research/ukcp/ukcp18-guidance---caveats-and-limitations.pdf"
            ),
            media_type="application/pdf",
        )
    )
    template.add_link(
        pystac.Link(
            rel="documentation",
            title="UKCP18 Science Reports",
            target="https://www.metoffice.gov.uk/research/approach/collaboration/ukcp/guidance-science-reports",
            media_type="text/html",
        )
    )
    template.add_link(
        pystac.Link(
            rel="documentation",
            title="CEDA Archive dataset",
            target="https://catalogue.ceda.ac.uk/uuid/97bc0c622a24489aa105f5b8a8efa3f0",
            media_type="text/html",
        )
    )

    r = xstac.xarray_to_stac(ds, template, reference_system=4326)

    # We only loaded metadata for the first year. It actually runs through 2100.
    ext = pystac.extensions.datacube.DatacubeExtension.ext(r)
    time = ext.dimensions["time"]
    time.extent[1] = extent.temporal.intervals[0][1].isoformat() + "Z"

    definitions = {}
    for k, v in ext.variables.items():
        asset = pystac.extensions.item_assets.AssetDefinition({})
        asset.description = v.description
        asset.title = v.properties["attrs"].get("long_name", k)
        asset.media_type = "application/netcdf"
        asset.roles = ["data"]
        definitions[k] = asset

    # Item assets
    item_assets = pystac.extensions.item_assets.ItemAssetsExtension.ext(
        r, add_if_missing=True
    )

    item_assets.item_assets = definitions

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
        "Met Office Hadley Centre (2018): UKCP18 Global Climate Model Projections for the entire "
        "globe. Centre for Environmental Data Analysis, date of citation. "
        "http://catalogue.ceda.ac.uk/uuid/f1a2fc3c120f400396a92f5de84d596a"
    )

    # Summaries
    r.summaries.maxcount = 50
    summaries = {
        "ukcp18:variable": VARIABLES,
        "ukcp18:temporal_resolution": TEMPORAL_RESOLUTIONS,
    }
    for k, v in summaries.items():
        r.summaries.add(k, v)

    r.validate()

    with open("collection.json", "w") as f:
        json.dump(r.to_dict(), f, indent=2)


if __name__ == "__main__":
    main()
