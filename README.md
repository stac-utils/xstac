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

