"""
xstac
"""
import copy
import json
from pystac import stac_object
import xarray as xr
import numpy as np
import pystac
import pandas as pd
from pyproj import CRS, Transformer
from typing import List, Dict

from ._types import TemporalDimension, HorizontalSpatialDimension, Datacube, Variable


def fix_attrs(ds):
    ds = type(ds)(ds)

    for k, v in ds.items():
        for attr_name, attr_value in v.attrs.items():
            if isinstance(attr_value, np.ndarray):
                ds[k].attrs[attr_name] = list(attr_value)
    return ds


def build_bbox(left, bottom, right, top, src_crs):
    """
    Build a latitude / longitude bounding box from the coordinates.
    """
    # minimum / maximum points from the dataset
    # left, bottom, right, top = (-5802250.0, -622000.0, -5519250.0, -39000.0)
    dst_crs = CRS.from_epsg(4326)

    points = [[left, right, right, left], [bottom, bottom, top, top]]

    transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    lons, lats = transformer.transform(*points)

    west = min(lons)
    east = max(lons)
    north = max(lats)
    south = min(lats)
    return [west, south, east, north]


def maybe_infer_step(da, step):
    if step is None:
        delta = da.diff(da.name)
        if len(delta) > 1 and (delta[0] == delta[1:]).all():
            # TODO: handle timedelta
            step = delta[0].item()
    elif step is False:
        step = None
    return step


def build_temporal_dimension(ds, name, extent, values, step):
    time = ds.coords[name]
    extent = (
        pd.to_datetime(
            np.concatenate([time.min(keepdims=True), time.max(keepdims=True)])
        )
        .strftime("%Y-%m-%dT%H:%M:%SZ")
        .tolist()
    )
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

    return TemporalDimension(
        type="temporal",
        extent=extent,
        description=time.attrs.get("long_name"),
        values=values,
        step=step,
    )


def build_horizontal_dimension(ds, name, axis, extent, values, step, reference_system):
    da = ds[name]
    if extent is None:
        extent = np.asarray(
            np.concatenate([da.min(keepdims=True), da.max(keepdims=True)])
        ).tolist()
    if step is None:
        # infer the step
        delta = da.diff(name)
        if len(delta) > 1 and (delta[0] == delta[1:]).all():
            step = delta[0].item()
    step = maybe_infer_step(da, step)

    if values is True:
        values = np.asarray(da).tolist()
    elif values is False:
        values = None

    reference_system = maybe_infer_reference_system(ds, reference_system)

    return HorizontalSpatialDimension(
        type="spatial",
        axis=axis,
        extent=extent,
        step=step,
        values=values,
        description=da.attrs.get("long_name"),
        reference_system=reference_system,
    )


def build_vertical_dimension(ds, name, axis, extent, values, step, reference_system):
    pass


def maybe_infer_reference_system(ds, reference_system) -> dict:
    """
    Infer a Coordinate Reference System from a Dataset

    Notes
    -----
    This looks through a dataset for an item with `grid_mapping_name` key in its attrs.
    The value associated with that key is assumed to be a cf-compliant grid mapping.
    """
    if reference_system is None:
        # try to infer it
        names = [k for k, v in ds.variables.items() if "grid_mapping_name" in v.attrs]
        if not names:
            raise ValueError("Couldn't find a reference system")
        elif len(names) > 1:
            raise ValueError("Too many reference systems: %s", names)
        (name,) = names
        crs = CRS.from_cf(ds[name].attrs)
        reference_system = crs.to_json_dict()

    elif reference_system is False:
        reference_system = None

    return reference_system


def build_variables(ds):
    keys = set(ds.variables) - set(ds.dims)
    variables = {}
    for k, v in ds.variables.items():
        if k not in keys:
            continue
        if k in ds.coords:
            type_ = "auxiliary"
        else:
            type_ = "data"

        if v.chunks:
            chunks = v.data.chunksize
        else:
            chunks = None

        # print("v", v.attrs)
        description = v.attrs.get("description", None) or v.attrs.get("long_name", None)
        var = Variable(
            type=type_,
            description=description,
            dimensions=list(v.dims),
            unit=v.attrs.get("units", None),
            attrs=v.attrs,
            shape=v.shape,
            chunks=chunks,
        )
        variables[k] = var
    return variables


def build_datacube(
    ds,
    *,
    temporal_dimension=None,
    temporal_extent=None,
    temporal_values=False,
    temporal_step=None,
    x_dimension=None,
    x_extent=None,
    x_values=False,
    x_step=None,
    y_dimension=None,
    y_extent=None,
    y_values=False,
    y_step=None,
    reference_system=None,
    vertical_dimension=None,
    vertical_extent=None,
    vertical_values=None,
    vertical_step=None,
    **additional_dimensions,
):
    dimensions = {}

    if temporal_dimension is not None:
        dimensions[temporal_dimension] = build_temporal_dimension(
            ds, temporal_dimension, temporal_extent, temporal_values, temporal_step
        )

    if x_dimension:
        dimensions[x_dimension] = build_horizontal_dimension(
            ds,
            x_dimension,
            "x",
            x_extent,
            x_values,
            x_step,
            reference_system=reference_system,
        )
    if y_dimension:
        dimensions[y_dimension] = build_horizontal_dimension(
            ds,
            y_dimension,
            "y",
            y_extent,
            y_values,
            y_step,
            reference_system=reference_system,
        )

    if vertical_dimension:
        raise NotImplementedError
    #     dimensions[vertical_dimension] = build_vertical_dimension(
    #         ds,
    #         vertical_dimension,
    #         "z",
    #         vertical_extent,
    #         vertical_values,
    #         vertical_step,
    #         reference_system=reference_system,
    #     )
    if additional_dimensions:
        raise NotImplementedError

    variables = build_variables(ds)

    datacube = Datacube(**{"cube:dimensions": dimensions, "cube:variables": variables})
    result = json.loads(datacube.json(by_alias=True))
    return result


def xarray_to_stac(
    ds: xr.Dataset,
    template: Dict,
    *,
    temporal_dimension=None,
    temporal_extent=None,
    temporal_values=False,
    temporal_step=None,
    x_dimension=None,
    x_extent=None,
    x_values=False,
    x_step=None,
    y_dimension=None,
    y_extent=None,
    y_values=False,
    y_step=None,
    reference_system=None,
    vertical_dimension=None,
    vertical_extent=None,
    vertical_values=None,
    vertical_step=None,
    validate: bool = True,
    **additional_dimensions,
) -> pystac.Collection:
    """
    Construct a STAC Collection from an xarray Dataset.

    Parameters
    ----------
    template : dict
        A template to use for creating the pystac Collection / Item.
    temporal_dimension, x_dimension, y_dimension, vertical_dimension:
        The name of the (temporal, x, y, vertical) dimension
    temporal_extent, x_extent, y_extent:
        The lower and upper bounds of the (temporal, x, y vertical) dimension (inclusive).
    temporal_values, x_values, y_values, vertical_values:
        The actual values / coordinates of the (temporal, x, y, vertical) dimension. Keep in mind the impact on the size of the STAC collection.
        Should not be specified when `temporal_step` is specified. Prefer `temporal_step` when the temporal coordinates are regularly spaced.
    temporal_step, x_step, y_step, vertical_step:
        The difference between subsequent values in the (temporal, x, y vertical) dimension. Only specify when the values are regularly spaced.
    **additional_dimensions:
        A dictionary with keys ``extent``, ``values``, ``step``.
    """
    datacube = build_datacube(
        ds,
        temporal_dimension=temporal_dimension,
        temporal_extent=temporal_extent,
        temporal_values=temporal_values,
        temporal_step=temporal_step,
        x_dimension=x_dimension,
        x_extent=x_extent,
        x_values=x_values,
        x_step=x_step,
        y_dimension=y_dimension,
        y_extent=y_extent,
        y_values=y_values,
        y_step=y_step,
        reference_system=reference_system,
        vertical_dimension=vertical_dimension,
        vertical_extent=vertical_extent,
        vertical_values=vertical_values,
        vertical_step=vertical_step,
        **additional_dimensions,
    )

    # Fixup to ensure that epsg codes remain as digits, rather than strings.
    # Currently they're being cast to string by the _types stuff.
    # TODO(pystac): check if this is unnecessary
    for dimension in datacube["cube:dimensions"].values():
        ref = dimension.get("reference_system")
        if isinstance(ref, str) and ref.isdigit():
            dimension["reference_system"] = int(ref)

    is_item = template.get("type") == "Feature"
    result = copy.deepcopy(template)
    if is_item:
        result["properties"] = {**datacube, **template["properties"]}
    else:
        result = {**datacube, **template}

    extent = result.get("extent", {})
    extent.setdefault("spatial", {})
    extent.setdefault("temporal", {})

    if x_dimension and y_dimension and not extent.get("spatial"):
        ref = datacube["cube:dimensions"][x_dimension]["reference_system"]
        if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
            src_crs = CRS.from_epsg(ref)
        else:
            src_crs = CRS.from_json_dict(ref)
        left, right = datacube["cube:dimensions"][x_dimension]["extent"]
        bottom, top = datacube["cube:dimensions"][y_dimension]["extent"]
        bbox = build_bbox(left, bottom, right, top, src_crs)

        if is_item:
            result["bbox"] = bbox
        else:
            extent["spatial"] = {"bbox": [bbox]}

    if temporal_dimension and not extent.get("temporal"):
        start_datetime, end_datetime = (
            datacube["cube:dimensions"][temporal_dimension]["extent"][0],
            datacube["cube:dimensions"][temporal_dimension]["extent"][1],
        )
        if is_item:
            result["properties"]["start_datetime"] = start_datetime
            result["properties"]["end_datetime"] = end_datetime
        else:
            extent["temporal"]["interval"] = [[start_datetime, end_datetime]]

    if not is_item:
        result["extent"] = extent

    result.setdefault("stac_collections", [])
    # TODO: get from pystac
    result["stac_collections"].append(
        "https://stac-extensions.github.io/datacube/v1.0.0/schema.json"
    )

    if temporal_dimension:
        values = datacube["cube:dimensions"][temporal_dimension]["values"]
        if values is None:
            # For some reason, including None here causes validation to fail...
            # https://github.com/TomAugspurger/xstac/issues/9
            if is_item:
                del result["properties"]["cube:dimensions"][temporal_dimension][
                    "values"
                ]
            else:
                del result["cube:dimensions"][temporal_dimension]["values"]

    stac_obj = pystac.read_dict(result)

    if validate:
        if isinstance(stac_obj, pystac.Collection):
            stac_obj.normalize_hrefs("/")
        if is_item and stac_obj.get("geometry") is None:
            # https://github.com/sparkgeo/stac-validator/issues/176
            raise ValueError("Upstream bug validating when geometry is null.")
        else:
            stac_obj.validate()
    return stac_obj
