import planetary_computer
import adlfs
import json
import pystac
import xarray as xr
import xstac

token = planetary_computer.sas.get_token("ai4edataeuwest", "imerg").token
fs = adlfs.AzureBlobFileSystem("ai4edataeuwest", credential=token)
store = fs.get_mapper("/imerg/gpm-imerg-hhr.zarr")
ds = xr.open_zarr(store, consolidated=True, use_cftime=True)
ds["time"] = ds.convert_calendar("gregorian")["time"]

template_file = "collection-template.json"
template = json.load(open(template_file))
collection = xstac.xarray_to_stac(
    ds,
    template,
    temporal_dimension="time",
    x_dimension="lon",
    y_dimension="lat",
    reference_system="4326",
    validate=True,
)
collection.validate()
collection.remove_links(pystac.RelType.SELF)
collection.remove_links(pystac.RelType.ROOT)
with open("collection.json", "w") as f:
    json.dump(collection.to_dict(), f, indent=2)
