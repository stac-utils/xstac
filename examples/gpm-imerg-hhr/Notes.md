As noted in https://github.com/TomAugspurger/xstac/issues/7 there is a conflict with STAC and non-standard calendars.

To alleviate this, `generate.py` requires
```
pip install git+https://github.com/aulemahal/xarray@calendar-utils
```
until `convert_calendar` is available in a core module.



