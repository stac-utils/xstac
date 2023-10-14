"""
xstac
"""
from ._xstac import xarray_to_stac, fix_attrs
from . import _kerchunk as kerchunk

__version__ = "1.2.0"

__all__ = ["xarray_to_stac", "fix_attrs", "kerchunk"]
