# xstac

Generate STAC Collections from xarray datasets.

## Example - CLI

```console
$ xstac --help
usage:
Generate STAC Collections for Daymet from the Zarr Groups.

xstac template.json asset-key output.json

positional arguments:
  template              Template STAC Collection to merge with the result.
  asset                 Asset key to use to load the data. Must be present in
                        the template file's 'assets'.
  outfile               Output file to write to. Defaults to stdout.

optional arguments:
  -h, --help            show this help message and exit
  --reference-system REFERENCE_SYSTEM
  --temporal_dimension TEMPORAL_DIMENSION
                        Coordinate name for the 'time' dimension
  --x-dimension X_DIMENSION
                        Coordinate name for the 'x' dimension
  --y-dimension Y_DIMENSION
                        Coordinate name for the 'y' dimension
  --no-validate         Whether to skip validation of the collection.

$ xstac examples/terraclimate/terraclimate-template.json \
  zarr-https examples/terraclimate/terraclimate.json \
  --x-dimension=lon --y-dimension=lat --reference-system=4326
```

This generates the [TerraClimate STAC Collection](examples/terraclimate/terraclimate.json)

Alternatively, you can generate STAC items:

```
$ xstac examples/terraclimate/item-template.json \
    zarr-https examples/terraclimate/item.json \
    --x-dimension=lon --y-dimension=lat --reference-system=4326
```

This generates the [TerraClimate STAC item](examples/terraclimate/item.json).

## Example - Python API

See [examples/daymet/generate.py](examples/daymet/generate.py) for an example using the Python API.


## Kerchunk support

[Kerchunk](https://fsspec.github.io/kerchunk/) is a project and specification
for representing chunked, compressed data where only the metadata and
*references* to chunks of remote data are stored. You might want to include the
Kerchunk metadata in a STAC item.

To do this, generate the Kerchunk indices and provide them as the
`kerchunk_indices` argument to `xarray_to_stac`.

```python
>>> from stactools.noaa_nwm import stac
>>> import kerchunk.hdf

>>> href = "https://noaanwm.blob.core.windows.net/nwm/nwm.20231010/short_range/nwm.t00z.short_range.channel_rt.f001.conus.nc"
>>> indices = kerchunk.hdf.SingleHdf5ToZarr(href).translate()
>>> item = stac.create_item(href, kerchunk_indices=indices)
```