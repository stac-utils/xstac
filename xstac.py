import xarray as xr
import numpy as np
import pandas as pd
from pyproj import CRS

from _types import (
    TemporalDimension,
    HorizontalSpatialDimension,
    Datacube
)


def _build_temporal_dimension(ds, name, extent, values, step):
    time = ds.coords[name]
    extent = pd.to_datetime(np.concatenate([time.min(keepdims=True), time.max(keepdims=True)])).strftime("%Y-%m-%dT%H:%M:%SZ").tolist()
    if values is True:
        values = np.asarray(time).tolist()
    elif values is False:
        values = None

    if step is None:
        # infer the step
        delta = time.diff(name)
        if len(delta) > 1 and (delta[0] == delta[1:]).all():
            step = pd.to_timedelta(np.asarray(delta))[0].isoformat()
    elif step is False:
        step = None

    return TemporalDimension(type="temporal", extent=extent, description=time.attrs.get("long_name"), values=values, step=step)

def _build_horizontal_dimension(ds, name, axis, extent, values, step, reference_system):
    da = ds[name]
    if extent is None:
        extent = np.asarray(np.concatenate([da.min(keepdims=True), da.max(keepdims=True)])).tolist()
    if step is None:
        # infer the step
        delta = da.diff(name)
        if len(delta) > 1 and (delta[0] == delta[1:]).all():
            step = delta[0].item()
    elif step is False:
        step = None
    if values is True:
        values = np.asarray(da).tolist()
    elif values is False:
        values = None

    if reference_system is None:
        # try to infer it
        reference_system = _infer_reference_system(ds)
    elif reference_system is False:
        reference_system = None

    return HorizontalSpatialDimension(type="spatial", axis=axis, extent=extent, step=step, values=values, description=da.attrs.get("long_name"), reference_system=reference_system)


def _infer_reference_system(ds) -> dict:
    names = [
        k for k, v in ds.items() if "grid_mapping_name" in v.attrs
    ]
    if not names:
        raise ValueError("Couldn't find a reference system")
    elif len(names) > 1:
        raise ValueError("Too many reference systems: %s", names)
    name, = names
    crs = CRS.from_cf(ds[name].attrs)
    return crs.to_json_dict()
    

def xarray_to_stac(ds: xr.Dataset, *,
                   temporal_dimension=None, temporal_extent=None, temporal_values=False, temporal_step=None,
                   x_dimension=None, x_extent=None, x_values=False, x_step=None,
                   y_dimension=None, y_extent=None, y_values=False, y_step=None,
                   vertical_dimension=None, additional_dimensions=None,
                   reference_system=None):
    """
    Construct a Datacube from an xarray Dataset.

    Parameters
    ----------
    temporal_dimension : str, optional
    """
    dimensions = {}
    variables = {}
    coods = set(ds.coords)
    
    if temporal_dimension is not None:
        dimensions[temporal_dimension] = _build_temporal_dimension(ds, temporal_dimension, temporal_extent, temporal_values, temporal_step)
        
    if x_dimension:
        dimensions[x_dimension] = _build_horizontal_dimension(ds, x_dimension, "x", x_extent, x_values, x_step, reference_system=reference_system)
    if y_dimension:
        dimensions[y_dimension] = _build_horizontal_dimension(ds, y_dimension, "y", y_extent, y_values, y_step, reference_system=reference_system)
    
    variables = {}

    return Datacube(**{"cube:dimensions": dimensions, "cube:variables": variables})
