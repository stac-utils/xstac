import pystac

import xarray as xr
import kerchunk.hdf
import fsspec

import xstac


def test_add_kerchunk(ds: xr.Dataset, item_template, tmp_path):
    p = tmp_path / "test.nc"
    ds.to_netcdf(p, engine="h5netcdf")

    indices = kerchunk.hdf.SingleHdf5ToZarr(str(p)).translate()
    result: pystac.Item = xstac.xarray_to_stac(
        ds, template=item_template, kerchunk_indices=indices
    )

    assert result.properties["kerchunk:zattrs"] == {
        "Conventions": "CF-1.6",
        "Version_data": "Daymet Data Version 4.0",
        "Version_software": "Daymet Software Version 4.0",
        "citation": "Please see http://daymet.ornl.gov/ for "
        "current Daymet data citation information",
        "references": "Please see http://daymet.ornl.gov/ for "
        "current information on Daymet references",
        "source": "Daymet Software Version 4.0",
        "start_year": 1980,
    }
    assert result.properties["kerchunk:zgroup"] == {"zarr_format": 2}

    assert result.properties["cube:dimensions"]["time"]["kerchunk:zarray"] == {
        "chunks": [40],
        "compressor": None,
        "dtype": "<i8",
        "fill_value": None,
        "filters": None,
        "order": "C",
        "shape": [40],
        "zarr_format": 2,
    }
    assert result.properties["cube:variables"]["prcp"]["kerchunk:zarray"] == {
        "chunks": [40, 584, 284],
        "compressor": None,
        "dtype": "<f4",
        "fill_value": "NaN",
        "filters": None,
        "order": "C",
        "shape": [40, 584, 284],
        "zarr_format": 2,
    }

    for attr in ["cube:dimensions", "cube:variables"]:
        for v in result.properties[attr].values():
            assert {"kerchunk:value", "kerchunk:zarray", "kerchunk:zattrs"} <= set(
                v.keys()
            )


def test_stac_to_kerchunk(ds: xr.Dataset, item_template, tmp_path):
    p = tmp_path / "test.nc"
    ds.to_netcdf(p, engine="h5netcdf")

    indices = kerchunk.hdf.SingleHdf5ToZarr(str(p)).translate()
    item: pystac.Item = xstac.xarray_to_stac(
        ds, template=item_template, kerchunk_indices=indices
    )

    indices = xstac.kerchunk.stac_to_kerchunk(item)

    result = xr.open_dataset(
        fsspec.filesystem("reference", fo=indices).get_mapper(),
        engine="zarr",
        consolidated=False,
    )

    xr.testing.assert_equal(ds, result)
