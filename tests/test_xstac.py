import json
import pyproj
import pytest
import pystac
import numpy as np
import xarray as xr

from xstac import xarray_to_stac, fix_attrs
from xstac._xstac import (
    _bbox_to_geometry,
    maybe_infer_reference_system,
    maybe_use_cf_standard_axis,
)


# def test_no_time_dimension(ds, collection_template):
#    _ = xarray_to_stac(ds, template=collection_template, temporal_dimension=False)


def test_fix_attrs():
    attrs = {"array": np.array([0, 1]), "scalar": np.int8(12)}
    fixed_attrs = {"array": [0, 1], "scalar": 12}

    ds = xr.Dataset({"a": ((), 0, attrs)}, coords={"x": ((), 0, attrs)}, attrs=attrs)
    actual = fix_attrs(ds)

    expected = xr.Dataset(
        {"a": ((), 0, fixed_attrs)},
        coords={"x": ((), 0, fixed_attrs)},
        attrs=fixed_attrs,
    )
    xr.testing.assert_identical(actual, expected)


@pytest.mark.parametrize("explicit_dims", [False, True])
def test_xarray_to_stac(
    ds,
    collection_template,
    collection_expected_dims,
    collection_expected_vars,
    explicit_dims,
):
    kw = (
        dict()
        if not explicit_dims
        else dict(temporal_dimension="time", x_dimension="x", y_dimension="y")
    )
    result = xarray_to_stac(ds, template=collection_template, **kw)
    assert result.id == "id"
    assert isinstance(result, pystac.Collection)
    assert result.description == "description"
    assert result.license == "license"

    dimensions = result.extra_fields["cube:dimensions"]
    assert dimensions == collection_expected_dims
    assert result.extra_fields["cube:variables"] == collection_expected_vars


@pytest.mark.parametrize(
    ("dimension_key", "expected_value"),
    [
        ("x_dimension", "x"),
        ("y_dimension", "y"),
        ("temporal_dimension", "time"),
        ("longitude", "lon"),
        ("latitude", "lat"),
    ],
)
def test_maybe_use_cf_standard_axis(ds, dimension_key, expected_value):
    assert maybe_use_cf_standard_axis(None, dimension_key, ds) == expected_value


def test_validation_with_none(ds_without_spatial_dims):
    # https://github.com/TomAugspurger/xstac/issues/9
    template = {
        "type": "Collection",
        "id": "cesm2-lens",
        "stac_version": "1.0.0",
        "description": "desc",
        "stac_extensions": [
            "https://stac-extensions.github.io/datacube/v2.0.0/schema.json"
        ],
        "extent": {
            "spatial": {"bbox": [[-180, -90, 180, 90]]},
            "temporal": {
                "interval": [["1851-01-01T00:00:00Z", "1851-01-01T00:00:00Z"]]
            },
        },
        "providers": [],
        "license": "CC0-1.0",
        "links": [],
    }
    c = xarray_to_stac(
        ds_without_spatial_dims, template, x_dimension=False, y_dimension=False
    )
    c.normalize_hrefs("/")
    c.validate()


def test_xarray_to_stac_item(ds, item_template, item_expected_dims, item_expected_vars):

    result = xarray_to_stac(ds, template=item_template)
    assert result.id == "id"
    assert isinstance(result, pystac.Item)

    dimensions = result.properties["cube:dimensions"]
    assert dimensions == item_expected_dims
    assert result.properties["cube:variables"] == item_expected_vars

    if ds.coords["time"].dtype == "object":
        assert result.properties["start_datetime"] == "2100-01-01T00:00:00Z"
        assert result.properties["end_datetime"] == "2100-02-10T00:00:00Z"
    else:
        assert result.properties["start_datetime"] == "1980-07-31T00:00:00Z"
        assert result.properties["end_datetime"] == "2019-07-31T00:00:00Z"


def test_bbox_to_geometry():
    import shapely.geometry

    bbox = [
        -160.2988400944475,
        17.960033949329812,
        -154.7780670634169,
        23.51232608231902,
    ]
    result = shapely.geometry.mapping(shapely.geometry.shape(_bbox_to_geometry(bbox)))
    expected = shapely.geometry.mapping(shapely.geometry.box(*bbox))
    assert result == expected


def test_missing_dims_error(ds_without_spatial_dims, collection_template):
    with pytest.raises(KeyError):
        _ = xarray_to_stac(ds_without_spatial_dims, collection_template)


def test_from_pystac_object(ds_without_spatial_dims):
    # https://github.com/TomAugspurger/xstac/issues/9
    template = {
        "type": "Collection",
        "id": "cesm2-lens",
        "stac_version": "1.0.0",
        "description": "desc",
        "stac_extensions": [
            "https://stac-extensions.github.io/datacube/v2.0.0/schema.json"
        ],
        "extent": {
            "spatial": {"bbox": [[-180, -90, 180, 90]]},
            "temporal": {
                "interval": [["1851-01-01T00:00:00Z", "1851-01-01T00:00:00Z"]]
            },
        },
        "providers": [],
        "license": "CC0-1.0",
        "links": [],
    }
    c = xarray_to_stac(
        ds_without_spatial_dims,
        pystac.read_dict(template),
        x_dimension=False,
        y_dimension=False,
    )
    c.normalize_hrefs("/")
    c.validate()


@pytest.mark.parametrize(
    ("ds", "expected"),
    [
        (xr.Dataset(coords={"epsg": xr.DataArray(32633, name="epsg")}), 32633),
        (
            xr.Dataset(coords={"proj:epsg": xr.DataArray(32633, name="proj:epsg")}),
            32633,
        ),
        (xr.Dataset(attrs={"crs": "epsg:32633"}), 32633),
        (
            xr.Dataset(
                coords={
                    "latitude": xr.DataArray(100, name="latitude"),
                    "longitude": xr.DataArray(100, name="longitude"),
                }
            ),
            4326,
        ),
    ],
)
def test_maybe_infer_reference_system(ds, expected):
    result = maybe_infer_reference_system(ds, reference_system=None)
    expected = pyproj.crs.CRS.from_epsg(expected).to_json_dict()
    assert result == expected


def test_maybe_infer_reference_system_from_cf_coordinates(ds):
    result = maybe_infer_reference_system(ds, reference_system=None)
    expected = pyproj.crs.CRS.from_epsg(4326).to_json_dict()
    assert result == expected


def test_disable_infer_temporal_extent(ds, item_template):
    # item_template = copy.deepcopy(item_template)
    # del item_template["properties"]["datetime"]
    result = xarray_to_stac(ds, item_template, temporal_dimension=False)
    assert "start_datetime" not in result.properties


def test_fixup_numpy_attrs_by_default(ds, item_template):
    ds.prcp.attrs["values"] = np.zeros(2)
    result = xarray_to_stac(ds, item_template, temporal_dimension=False)
    assert result.properties["cube:variables"]["prcp"]["attrs"]["values"] == [0.0, 0.0]
    json.dumps(result.to_dict())
