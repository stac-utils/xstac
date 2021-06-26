from xstac import xarray_to_stac
import xarray as xr
import numpy as np
import pandas as pd
import pytest
import pystac


data = np.empty((40, 584, 284), dtype="float32")
x = xr.DataArray(
    np.arange(-5802250.0, -5519250 + 1000, 1000),
    name="x",
    dims="x",
    attrs={
        "units": "m",
        "long_name": "x coordinate of projection",
        "standard_name": "projection_x_coordinate",
    },
)
y = xr.DataArray(
    np.arange(-39000.0, -622000.0 - 1000, -1000.0),
    name="y",
    dims="y",
    attrs={
        "units": "m",
        "long_name": "y coordinate of projection",
        "standard_name": "projection_y_coordinate",
    },
)
time = xr.DataArray(
    pd.date_range(start="1980-07-01", freq="A-JUL", periods=40),
    name="time",
    dims="time",
    attrs={
        "standard_name": "time",
        "bounds": "time_bnds",
        "long_name": "24-hour day based on local time",
    },
)
lat = xr.DataArray(
    np.empty((584, 284)),
    coords={"y": y, "x": x},
    dims=("y", "x"),
    name="lat",
    attrs={
        "units": "degrees_north",
        "long_name": "latitude coordinate",
        "standard_name": "latitude",
    },
)
lon = xr.DataArray(
    np.empty((584, 284)),
    coords={"y": y, "x": x},
    dims=("y", "x"),
    name="lon",
    attrs={
        "units": "degrees_east",
        "long_name": "longitude coordinate",
        "standard_name": "longitude",
    },
)
nv = xr.DataArray(
    np.array([0, 1]),
    dims=("nv",),
    name="nv"
)
time_bnds = xr.DataArray(
    np.empty((40, 2)),
    coords={"time": time, "nv": nv},
    dims=("time", "nv")
)

coords = dict(
    time=time,
    y=y,
    x=x,
    lat=lat,
    lon=lon,
)

@pytest.fixture
def ds():
    ds = xr.Dataset(
        {
            "prcp": xr.DataArray(
                data,
                coords=coords,
                dims=("time", "y", "x"),
                attrs={
                    "grid_mapping": "lambert_conformal_conic",
                    "cell_methods": "area: mean time: sum within days time: sum over days",
                    "units": "mm",
                    "long_name": "annual total precipitation",
                },
            ),
            "swe": xr.DataArray(data, coords=coords, dims=("time", "y", "x")),
            "time_bnds": xr.DataArray(
                np.empty((40, 2), dtype="datetime64[ns]"),
                name="time_bnds",
                coords={"time": time},
                dims=("time", "nv"),
                attrs={"time": "days since 1950-01-01 00:00:00"},
            ),
            "lambert_conformal_conic": xr.DataArray(
                np.array(-32767, dtype="int16"),
                name="lambert_conformal_conic",
                attrs={
                    "grid_mapping_name": "lambert_conformal_conic",
                    "longitude_of_central_meridian": -100.0,
                    "latitude_of_projection_origin": 42.5,
                    "false_easting": 0.0,
                    "false_northing": 0.0,
                    "standard_parallel": np.array([25.0, 60.0]),
                    "semi_major_axis": 6378137.0,
                    "inverse_flattening": 298.257223563,
                },
            ),
            "nv": nv
        },
        attrs={
            "Conventions": "CF-1.6",
            "Version_data": "Daymet Data Version 4.0",
            "Version_software": "Daymet Software Version 4.0",
            "citation": "Please see http://daymet.ornl.gov/ for current Daymet data citation information",
            "references": "Please see http://daymet.ornl.gov/ for current information on Daymet references",
            "source": "Daymet Software Version 4.0",
            "start_year": [1980],
        },
    )
    return ds


def test_xarray_to_stac(ds):
    template = {
        "id": "id",
        "type": "Collection",
        "links": [],
        "description": "description",
        "license": "license",
        "stac_version": "1.0.0",
    }
    result = xarray_to_stac(
        ds,
        template=template,
        temporal_dimension="time",
        x_dimension="x",
        y_dimension="y",
        additional_dimensions=dict(
            nv=dict(
                type="count",
                values=True
            )
        )
    )
    assert result.id == "id"
    assert isinstance(result, pystac.Collection)
    assert result.description == "description"
    assert result.license == "license"
    ext = pystac.extensions.datacube.DatacubeExtension.ext(result)