"""
xstac
"""
import collections
import dateutil
from typing import Union

import cf_xarray  # noqa: F401
import pyproj  # noqa: F401
import xarray as xr
import numpy as np
import pystac
import pandas as pd
from pyproj import CRS, Transformer
from typing import Dict
from pystac.extensions.datacube import (
    TemporalDimension,
    HorizontalSpatialDimension,
    DatacubeExtension,
    Variable,
    VerticalSpatialDimension,
    DimensionType,
)

SCHEMA_URI = "https://stac-extensions.github.io/datacube/v2.0.0/schema.json"

CF_STANDARD_AXES = dict(temporal_dimension="T", x_dimension="X", y_dimension="Y")


def maybe_use_cf_standard_axis(kw, kw_name, ds):
    if kw is None:
        try:
            kw = ds.cf[CF_STANDARD_AXES[kw_name]].name
        except KeyError as e:
            raise KeyError(
                f"Kwarg `{kw_name}` is None and `{CF_STANDARD_AXES[kw_name]}` is not a key of "
                f"the dataset's `cf` namespace. Make `ds.cf['{CF_STANDARD_AXES[kw_name]}']` "
                "accessible via `cf_xarray`'s `guess_coord_axis` method or by manually editing the "
                "dataset's attributes according to http://cfconventions.org. Alternatively, pass "
                f"`{kw_name}` as a string cooresponding to the name of the dataset's {kw_name}."
                # "If the dataset does not have a {kw_name}, pass `{kw_name}=False`."
            ) from e
    return kw


def _bbox_to_geometry(bbox):
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [bbox[2], bbox[1]],
                [bbox[2], bbox[3]],
                [bbox[0], bbox[3]],
                [bbox[0], bbox[1]],
                [bbox[2], bbox[1]],
            ]
        ],
    }


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
    start = time.min(keepdims=True)
    end = time.max(keepdims=True)

    if time.dtype == "object":
        start = start.item().isoformat() + "Z"
        end = end.item().isoformat() + "Z"
        extent = [start, end]

    else:
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
        properties=dict(
            extent=extent,
            description=time.attrs.get("long_name"),
            values=values,
            step=step,
            type=DimensionType.TEMPORAL.value,
        )
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
        properties=dict(
            axis=axis,
            extent=extent,
            step=step,
            values=values,
            description=da.attrs.get("long_name"),
            reference_system=reference_system,
            type=DimensionType.SPATIAL.value,
        )
    )


def build_vertical_dimension(ds, name, axis, extent, values, step, reference_system):
    pass


def maybe_infer_reference_system(ds, reference_system) -> dict:
    """
    Infer a Coordinate Reference System from a Dataset

    Notes
    -----
    This gets a reference system from a dataset using the following heuristics (in order):

    * epsg from the coords
    * proj:epsg from the coords
    * crs from the attrs
    * variables with grid_mapping_name in their attrs.

    """
    if reference_system is None:
        if "epsg" in ds.coords:
            reference_system = pyproj.CRS.from_epsg(
                ds.coords["epsg"].item()
            ).to_json_dict()
        elif "proj:epsg" in ds.coords:
            reference_system = pyproj.CRS.from_epsg(
                ds.coords["proj:epsg"].item()
            ).to_json_dict()
        elif "crs" in ds.attrs:
            reference_system = pyproj.CRS.from_user_input(
                ds.attrs["crs"]
            ).to_json_dict()
        else:
            # try to infer it
            names = [
                k for k, v in ds.variables.items() if "grid_mapping_name" in v.attrs
            ]
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
            dict(
                type=type_,
                description=description,
                dimensions=list(v.dims),
                unit=v.attrs.get("units", None),
                attrs=v.attrs,
                shape=list(v.shape),
                chunks=chunks,
            )
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

    variables = build_variables(ds)
    return dimensions, variables


def xarray_to_stac(
    ds: xr.Dataset,
    template: Union[Dict, pystac.Item, pystac.Collection],
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
        The actual values / coordinates of the (temporal, x, y, vertical) dimension. Keep in mind the impact on
        the size of the STAC collection. Should not be specified when `temporal_step` is specified. Prefer
        `temporal_step` when the temporal coordinates are regularly spaced.
    temporal_step, x_step, y_step, vertical_step:
        The difference between subsequent values in the (temporal, x, y vertical) dimension. Only specify
        when the values are regularly spaced.
    **additional_dimensions:
        A dictionary with keys ``extent``, ``values``, ``step``.
    """
    temporal_dimension = maybe_use_cf_standard_axis(
        temporal_dimension, "temporal_dimension", ds
    )
    x_dimension = maybe_use_cf_standard_axis(x_dimension, "x_dimension", ds)
    y_dimension = maybe_use_cf_standard_axis(y_dimension, "y_dimension", ds)

    dimensions = {}

    if temporal_dimension is not False:
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

    # Fixup to ensure that epsg codes remain as digits, rather than strings.
    # Currently they're being cast to string by the _types stuff.
    # TODO(pystac): check if this is unnecessary
    for dimension in dimensions.values():
        if isinstance(
            dimension, (HorizontalSpatialDimension, VerticalSpatialDimension)
        ):
            ref = dimension.reference_system
            if isinstance(ref, str) and ref.isdigit():
                dimension.reference_system = int(ref)

    if isinstance(template, collections.abc.Mapping):
        template = pystac.read_dict(template)

    is_item = isinstance(template, pystac.Item)
    is_collection = not is_item

    result = template.clone()
    ext = DatacubeExtension.ext(result, add_if_missing=True)

    ext.dimensions = dimensions
    # doesn't have a setter: https://github.com/stac-utils/pystac/issues/681
    # ext.variables = variables
    ext.properties["cube:variables"] = {k: v.properties for k, v in variables.items()}

    if (
        is_collection
        and x_dimension
        and y_dimension
        and not any(x for x in result.extent.spatial.bboxes)
    ):
        ref = ext.dimensions[x_dimension]["reference_system"]
        if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
            src_crs = CRS.from_epsg(ref)
        else:
            src_crs = CRS.from_json_dict(ref)
        left, right = ext.dimensions[x_dimension]["extent"]
        bottom, top = ext.dimensions[y_dimension]["extent"]
        bbox = build_bbox(left, bottom, right, top, src_crs)

        if is_item:
            result["bbox"] = bbox
            # TODO: probably broken...
            result["geometry"] = _bbox_to_geometry(bbox)
        else:
            result.extent.spatial.bboxes[0] = bbox

    infer_temporal_extent = (
        temporal_dimension is not None
        and (is_collection and not any(x for x in result.extent.temporal.intervals[0]))
        or (
            is_item
            and not (
                result.properties.get("start_datetime")
                or result.properties.get("end_datetime")
            )
        )
    )

    if infer_temporal_extent:
        start_datetime, end_datetime = ext.dimensions[temporal_dimension].extent
        if is_item:
            result.properties["start_datetime"] = start_datetime
            result.properties["end_datetime"] = end_datetime
        else:
            start_datetime, end_datetime = (
                dateutil.parser.parse(start_datetime),
                dateutil.parser.parse(end_datetime),
            )
            result.extent.temporal.intervals[0] = [start_datetime, end_datetime]

    # remove unset values, otherwise we might hit bizare jsonschema issues
    # when validating
    for obj in ["cube:variables", "cube:dimensions"]:
        for var in ext.properties[obj]:
            for k, v in list(ext.properties[obj][var].items()):
                if v is None:
                    del ext.properties[obj][var][k]
    stac_obj = result

    if validate:
        if isinstance(stac_obj, pystac.Collection):
            stac_obj.normalize_hrefs("/")
        stac_obj.validate()
    return stac_obj
