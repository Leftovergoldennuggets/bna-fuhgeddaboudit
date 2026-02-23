# =============================================================================
# Makefile — Quick commands for the Waymo crash data project
# =============================================================================
#
# Usage:
#   make data          Run the full pipeline (download, merge, compute, generate)
#   make data-local    Run pipeline WITHOUT downloading (use existing raw data)
#   make serve         Start a local web server to view the site
#   make clean         Delete raw and processed data (keeps web JSON files)
#   make clean-all     Delete ALL generated files including web JSON
#

# Run the full data pipeline (download + process + generate)
data:
	python pipeline/run_pipeline.py

# Run pipeline using existing raw data (skip download step)
data-local:
	python pipeline/run_pipeline.py --skip-download

# Start a local web server to preview the website
# Serves from the project root so site/ can access ../data/web/ JSON files
serve:
	@echo "Starting server at http://localhost:8000/site/"
	@echo "Press Ctrl+C to stop"
	python -m http.server 8000

# Delete raw and processed data (can be regenerated)
clean:
	rm -rf data/raw/*.csv data/processed/*.csv

# Delete ALL generated files
clean-all: clean
	rm -rf data/web/*.json site/assets/images/*.png

.PHONY: data data-local serve clean clean-all
