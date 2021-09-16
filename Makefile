.PHONY: run-examples

run-examples:
	# terraclimate-collection
	xstac examples/terraclimate/terraclimate-template.json \
		zarr-https examples/terraclimate/terraclimate.json \
		--x-dimension=lon --y-dimension=lat --reference-system=4326
	# terraclimate-item
	xstac examples/terraclimate/item-template.json \
	    zarr-https examples/terraclimate/item.json \
	    --x-dimension=lon --y-dimension=lat --reference-system=4326
	# daymet
	cd examples/daymet && \
		python generate.py --region=all --frequency=all