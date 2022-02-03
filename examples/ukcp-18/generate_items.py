import json
import collections
import datetime

import adlfs
import planetary_computer
import pystac
import xstac
import xarray as xr


Parts = collections.namedtuple(
    "Parts", "member_id variable time_resolution filename start_datetime end_datetime"
)


def parts_of(x):
    _, _, _, _, _, _, _, _, member_id, variable, time_resolution, _, filename = x.split(
        "/"
    )
    date_range = filename.split("_")[-1].rstrip(".nc").split("-")

    return Parts(
        member_id, variable, time_resolution, filename, date_range[0], date_range[1]
    )


def path_to_item_id(x):
    parts = parts_of(x)
    return "-".join(
        [
            "ukcp18",
            parts.member_id,
            parts.time_resolution,
            parts.start_datetime,
            parts.end_datetime,
        ]
    )


def create_item(path, fs):
    ds = xr.open_dataset(fs.open(path), engine="h5netcdf", chunks={})
    for k, v in ds.variables.items():
        attrs = {
            name: xr.backends.zarr.encode_zarr_attr_value(value)
            for name, value in v.attrs.items()
        }
        ds[k].attrs = attrs

    parts = parts_of(path)
    fmt = "%Y%m%d"
    start_datetime = (
        datetime.datetime.strptime(parts.start_datetime, fmt).isoformat() + "Z"
    )
    end_datetime = datetime.datetime.strptime(parts.end_datetime, fmt).isoformat() + "Z"

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
        properties={"start_datetime": start_datetime, "end_datetime": end_datetime},
    )

    r = xstac.xarray_to_stac(ds, template, reference_system=4326)
    r.id = path_to_item_id(path)
    asset = pystac.Asset(
        f"https://ukmetuewest.blob.core.windows.net/{path}",
        media_type="application/netcdf",
        roles=["data"],
    )
    r.add_asset("data", asset)
    r.properties["ukcp18:member_id"] = int(parts.member_id)
    r.properties["ukcp18:time_resolution"] = parts.time_resolution
    r.validate()
    return r


def main():
    credential = planetary_computer.sas.get_token("ukmeteuwest", "ukcp18").token
    fs = adlfs.AzureBlobFileSystem("ukmeteuwest", credential=credential)
    files = [x for x in fs.find("ukcp18/") if x.endswith(".nc")]
    for file in files[:5]:
        item = create_item(file, fs)
        with open(f"{item.id}.json", "w") as f:
            json.dump(item.to_dict(), f)


if __name__ == "__main__":
    main()
