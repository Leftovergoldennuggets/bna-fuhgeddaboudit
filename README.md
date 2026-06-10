# Every Waymo Crash, Mapped

**Live site: [https://leftovergoldennuggets.github.io/bna-fuhgeddaboudit/](https://leftovergoldennuggets.github.io/bna-fuhgeddaboudit/)**

An evergreen data journalism website analyzing every publicly reported crash
involving a driverless Waymo vehicle in the United States. Originally built
for Stanford COMM277T: Building News Apps; substantially overhauled in
June 2026.

## About

Self-driving cars are expanding rapidly across American cities — Waymo's
driverless service is open to the public in eleven metros as of mid-2026.
Every time a Waymo vehicle is involved in a crash, the company is required
to report it to the National Highway Traffic Safety Administration. This
project makes that federal data accessible: mapping every reported incident,
analyzing the circumstances, and letting readers explore the data themselves.

The site merges two public data sources:

- **NHTSA Standing General Order reports** — the legally required federal
  crash record, refreshed roughly monthly. **This is the base dataset**:
  every reported crash enters the site within a week of publication.
- **Waymo Safety Impact Data Hub** — Waymo's curated quarterly release,
  used to *enrich* matched crashes with exact dates, street-level
  addresses, and crash type classifications.

Headline statistics cover **driverless operation only** (no human behind
the wheel). Crashes from supervised testing with a safety driver are
tracked separately and visible in the Explore section.

All statistics are computed from data. The site updates automatically every
week via GitHub Actions.

## Team

- **Anders Eidesvik** — Data pipeline, analysis, reporting
- **Kate Li** — Website development, early analysis

## Data Sources

- [NHTSA Standing General Order Data](https://www.nhtsa.gov/automated-vehicles/automated-driving-systems)
- [Waymo Safety Impact Data Hub](https://waymo.com/safety/impact/)
- [Waymo mileage milestones](https://docs.google.com/spreadsheets/d/1eZdFOrOMO2li30MImf2zg8PTw4s3DbSz/edit?usp=sharing&ouid=110131066109816005681&rtpof=true&sd=true) (compiled by Anders Eidesvik)

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the full data pipeline
make data

# Start local server
make serve
# Visit http://localhost:8000/site/index.html
```

## Testing

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

The test suite covers the pipeline's core logic: metro mapping, operation
classification, date/time parsing, severity levels, and merge behavior.
Tests run in CI on every push and before every automated data update.

## Tech Stack

- **Pipeline:** Python (pandas, requests, geopy)
- **Website:** HTML/CSS/JavaScript (no build step)
- **Maps:** Leaflet + MarkerCluster
- **Charts:** Chart.js
- **Hosting:** GitHub Pages
- **Auto-updates:** GitHub Actions (weekly)

## License

MIT License — see [LICENSE](LICENSE) file.
