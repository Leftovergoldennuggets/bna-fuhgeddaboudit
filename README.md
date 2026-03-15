# Every Waymo Crash, Mapped

**Live site: [https://leftovergoldennuggets.github.io/bna-fuhgeddaboudit/](https://leftovergoldennuggets.github.io/bna-fuhgeddaboudit/)**

An evergreen data journalism website analyzing every publicly reported crash involving a Waymo autonomous vehicle in the United States. Built for Stanford COMM277T: Building News Apps.

## About

Self-driving cars are rapidly expanding across American cities. Every time a Waymo vehicle is involved in a crash, the company is required to report it to the National Highway Traffic Safety Administration. This project makes that federal data accessible — mapping every reported incident, analyzing the circumstances, and letting readers explore the data themselves.

The site merges two public data sources:
- **NHTSA Standing General Order reports** — federal crash reports filed by Waymo, including narratives, severity, and vehicle movements
- **Waymo Safety Impact Data Hub** — Waymo's curated dataset with crash type classifications and street-level addresses

All statistics are computed from data. The site updates automatically every quarter when new data is published.

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

## Tech Stack

- **Pipeline:** Python (pandas, requests, geopy)
- **Website:** HTML/CSS/JavaScript (no build step)
- **Maps:** Leaflet + MarkerCluster
- **Charts:** Chart.js
- **Hosting:** GitHub Pages
- **Auto-updates:** GitHub Actions (quarterly)

## License

MIT License — see [LICENSE](LICENSE) file.
