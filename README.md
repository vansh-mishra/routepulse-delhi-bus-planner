# RoutePulse — Delhi Bus Journey Planner

**Transport Stack Hackathon 2026 · Problem 1: Real-time bus traffic model and journey planner**

RoutePulse is a focused Delhi bus journey-planning prototype built from the GTFS files and October 2026 ticket transactions supplied with this project. It provides stop search, direct and one-transfer timetable journey options, shape-based route maps, ticket-demand insights, user accounts for saved journeys, a persistent light/dark theme toggle, and an optional GTFS-Realtime vehicle-position connector.

## Important data interpretation

This project uses the supplied data as follows:

- **Static GTFS** (`stops`, `routes`, `trips`, `stop_times`, `shapes`, `calendar`, `agency`, `feed_info`) powers the stop network, route graph, scheduled trip search and map geometry.
- **October-Delhi.csv** contains ticket transactions: passenger count, fare amount, vehicle number (missing in some records), route, start stop, end stop, timestamp and AC flag. It is used for boarding/demand and fare insights. **It is not a GPS history file and cannot be used to calculate road speeds or observed bus travel durations.**
- **GTFS-Realtime** is optional. Configure the Transport Stack API key in `.env` to retrieve the current vehicle-position feed.
- **Map rendering** uses Leaflet with the standard OpenStreetMap raster tile service. It requires no map API key. Keep the visible attribution and follow the [OpenStreetMap tile usage policy](https://operations.osmfoundation.org/policies/tiles/); do not bulk-download or prefetch tiles. The app requests only the tiles needed for the user-visible map viewport.
- The hackathon's separate October historical GPS SQLite archive is not included in the uploaded files used to create this database. Until it is connected, journey durations are explicitly labelled **GTFS timetable estimates**, not GPS-trained traffic predictions.

## Included data build

`data/routepulse.sqlite.gz` is the prebuilt database generated from the uploaded GTFS text files and `October-Delhi.csv`. The app automatically extracts it to `data/routepulse.sqlite` the first time a page or API endpoint is opened. It contains:

- 6,862 stops
- 2,574 routes
- 80,357 trips
- 2,737,136 stop-time rows
- 965,607 shape points
- 2,559,899 October ticket transactions aggregated into route-hour, OD-pair, stop-demand and hour-demand tables

The uploaded GTFS data is internally consistent: every trip referenced in `stop_times` has a matching trip record, and every referenced stop has a stop record.

## Run on Windows (VS Code)

1. Extract the project ZIP.
2. Open the extracted `routepulse-delhi` folder in VS Code.
3. Open PowerShell in that folder.
4. Create and activate a virtual environment:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

5. Install dependencies:

```powershell
python -m pip install --index-url https://pypi.org/simple -r requirements.txt
```

6. Create local configuration:

```powershell
Copy-Item .env.example .env
notepad .env
```

Set a private `SECRET_KEY`. To activate GTFS-Realtime, add the **rotated** Transport Stack key to `TRANSPORT_STACK_API_KEY`. Do not paste API keys into source code or commit `.env`.

7. Start the app:

```powershell
python app.py
```

8. Open `http://127.0.0.1:5000/`.

## Product pages

- `/` — concise product overview
- `/demo` — public journey planner; no account required
- `/signup` and `/login` — account creation and sign-in
- `/account` — saved journeys
- `/insights` — ticket-demand analytics from October CSV
- `/api/docs` — compact developer API reference

The theme toggle in the top navigation switches between light and dark modes and remembers the preference in the browser.

## Main API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Data and integration status |
| GET | `/api/stops?q=Kashmere` | GTFS stop search |
| GET | `/api/plan?origin_id=...&destination_id=...&departure=08:30` | Up to three scheduled journey options |
| GET | `/api/demand?hour=8` | Ticket-demand ranking by route/hour |
| GET | `/api/vehicles` | Optional GTFS-Realtime vehicle positions |
| POST | `/api/save-journey` | Save a journey for a signed-in user |

## Rebuild the database from original source files

The downloadable ZIP includes the compressed prebuilt database so the app starts without re-importing the large CSV. The prebuilt database is intentionally ignored by ordinary Git pushes because of its size; distribute it separately or rebuild it from source files for a public repository. The extracted `.sqlite` file is ignored by Git; the compressed `.sqlite.gz` file is included in the repository bundle. To rebuild it from original files, create `data/source/` and place these files there:

`agency.txt`, `calendar.txt`, `feed_info.txt`, `routes.txt`, `shapes.txt`, `stop_times.txt`, `stops.txt`, `trips.txt`, `October-Delhi.csv`.

Then run:

```powershell
python scripts/build_database.py --source data/source --output data/routepulse.sqlite
```

The builder streams the ticket CSV in chunks and stores aggregate demand rather than retaining all raw ticket rows in the operational database.

## Notes and limitations

1. Current journey options use the official GTFS schedule. They are not observed-traffic predictions.
2. Walking time is a user-editable planning buffer; it is not derived from pedestrian routing.
3. Transfer search currently supports one bus-to-bus interchange at a shared GTFS stop.
4. Live vehicle markers require a valid API key and installed GTFS-Realtime bindings. The live feed may omit optional speed or route fields.
5. The ticket CSV has some missing `vehicle_number` values; the dashboard describes transaction demand, not actual on-board occupancy.
6. Before the hackathon submission, connect the separate historical GPS SQLite archive and calculate segment/time-of-day speed profiles. Then validate against observed journeys and Google Maps for matched date/time pairs.

## Deployment

A `render.yaml`, `Procfile` and `requirements-prod.txt` are included for a simple Render/Gunicorn deployment. On Windows, install only `requirements.txt`; on Render, the deployment file installs `requirements-prod.txt`. Set a strong `SECRET_KEY` and a rotated `TRANSPORT_STACK_API_KEY` in the hosting dashboard; never add them to Git.

## Demo video

Follow `docs/demo_video_guide.md` to record a 2–3 minute OBS walkthrough. The guide includes a suggested demo sequence, recording configuration and accuracy/security reminders.

## Submission readiness

See `docs/submission_readiness.md` for the audit. Current routing is GTFS timetable-based; the separate historical GPS SQLite archive and empirical traffic-model validation still need to be completed before claiming a fully validated real-time traffic prediction solution.

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Project structure

```text
routepulse-delhi/
├── app.py
├── data/routepulse.sqlite
├── scripts/
│   ├── build_database.py
│   └── import_ticket_demand.py
├── templates/
├── static/
├── tests/
├── docs/
├── requirements.txt
└── .env.example
```

## Security

- Never commit `.env`, credentials or API keys.
- Passwords are stored as Werkzeug password hashes, not plaintext.
- Use HTTPS and a production secret key when deploying publicly.
- The included account system is a hackathon prototype, not a production identity service.
