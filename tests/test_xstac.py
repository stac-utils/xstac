from xstac import xarray_to_stac
from xstac._xstac import _bbox_to_geometry
import cf_xarray
import pytest
import pystac

import xstac


def test_xarray_to_stac(
    ds, collection_template, collection_expected_dims, collection_expected_vars
):
    result = xarray_to_stac(ds, template=collection_template)
    assert result.id == "id"
    assert isinstance(result, pystac.Collection)
    assert result.description == "description"
    assert result.license == "license"

    dimensions = result.extra_fields["cube:dimensions"]
    assert dimensions == collection_expected_dims
    assert result.extra_fields["cube:variables"] == collection_expected_vars


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
