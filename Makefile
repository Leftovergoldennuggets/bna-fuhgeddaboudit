# Common tasks. See README.md and MAINTENANCE.md.
PYTHON ?= python3

.PHONY: data data-offline serve test

data:            ## Download everything and rebuild all site data
	$(PYTHON) pipeline/run_pipeline.py

data-offline:    ## Rebuild from the raw files already in data/raw/
	$(PYTHON) pipeline/run_pipeline.py --skip-download

serve:           ## Serve the site at http://localhost:8000/site/index.html
	$(PYTHON) -m http.server 8000

test:
	$(PYTHON) -m pytest tests/ -q
