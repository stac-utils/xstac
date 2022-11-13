# Daymet Collection

This directory contains an example nested collection for Daymet.

The top-level [Catalog](catalog.json) holds 9 nested collections, one for each region - frequency pair.

## Usage

```
python generate.py --region hi --frequency annual --storage-options="{\"account_name\": \"daymeteuwest\", \"credential\": \"$SAS_TOKEN\"}" --asset-href="az://test-update/fix/ann-hi.zarr"
python generate.py --region hi --frequency monthly --storage-options="{\"account_name\": \"daymeteuwest\", \"credential\": \"$SAS_TOKEN\"}" --asset-href="az://test-update/fix/mon-hi.zarr"
python generate.py --region hi --frequency daily --storage-options="{\"account_name\": \"daymeteuwest\", \"credential\": \"$SAS_TOKEN\"}" --asset-href="az://test-update/fix/daily-hi.zarr"

python generate.py --region pr --frequency annual --storage-options="{\"account_name\": \"daymeteuwest\", \"credential\": \"$SAS_TOKEN\"}" --asset-href="az://test-update/fix/ann-pr.zarr"
python generate.py --region pr --frequency monthly --storage-options="{\"account_name\": \"daymeteuwest\", \"credential\": \"$SAS_TOKEN\"}" --asset-href="az://test-update/fix/mon-pr.zarr"
python generate.py --region pr --frequency daily --storage-options="{\"account_name\": \"daymeteuwest\", \"credential\": \"$SAS_TOKEN\"}" --asset-href="az://test-update/fix/daily-pr.zarr"



```