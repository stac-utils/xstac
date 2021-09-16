.PHONY: run-examples

run-examples:
	# terraclimate
	xstac examples/terraclimate/terraclimate-template.json \
		zarr-https examples/terraclimate/terraclimate.json \
		--x-dimension=lon --y-dimension=lat --reference-system=4326
	# daymet
	cd examples/daymet && \
		python generate.py --region hi --frequency daily && \
		python generate.py --region hi --frequency monthly && \
		python generate.py --region hi --frequency annual && \
		python generate.py --region na --frequency daily && \
		python generate.py --region na --frequency monthly && \
		python generate.py --region na --frequency annual && \
		python generate.py --region pr --frequency daily && \
		python generate.py --region pr --frequency monthly && \
		python generate.py --region pr --frequency annual
