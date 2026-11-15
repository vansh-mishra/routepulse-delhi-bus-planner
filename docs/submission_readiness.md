# RoutePulse submission-readiness audit

Audit baseline: current project bundle and uploaded data artifacts inspected on 15 November 2026.

## Verified in this workspace

- [x] Static GTFS tables are present in the generated SQLite database.
- [x] GTFS counts match the uploaded files: 6,862 stops; 2,574 routes; 80,357 trips; 2,737,136 stop-time rows; 965,607 shape points.
- [x] Referential integrity checks passed: every stop-time trip and stop reference resolves.
- [x] October ticket transaction aggregation reconciles to 2,559,899 input rows.
- [x] Direct sample journey exists for Kashmere Gate City Bus Terminal to Nehru Place Terminal.
- [x] Light/dark theme toggle persists the choice in browser local storage.
- [x] Map configuration uses Leaflet + `https://tile.openstreetmap.org/{z}/{x}/{y}.png`; no map API key is required. Visible OpenStreetMap attribution is enabled.
- [x] No API credentials are bundled in `.env.example`; `.env` is ignored by Git.
- [x] Project includes a video recording guide.

## Not yet verified / still required for the full Problem 1 claim

- [ ] Historical DTC GPS SQLite archive imported and inspected. It was not among the files supplied for this build.
- [ ] Segment-level historical running-speed model trained from actual GPS observations.
- [ ] Travel-time estimates validated on held-out observed trips with MAE/RMSE and error distribution.
- [ ] Prediction comparisons against Google Maps for matched journeys, dates and departure times.
- [ ] GTFS-Realtime endpoint tested with a rotated, valid API key; no key is included in this repository.
- [ ] End-to-end browser test on the user's Windows machine and deployed HTTPS URL.
- [ ] Public repository and demo video uploaded to the hackathon submission portal.

## Submission verdict

**Ready as a data-backed GTFS timetable journey-planning and ticket-demand prototype; not yet complete as a validated real-time traffic-prediction solution.** The hackathon Problem 1 brief asks for historical/live bus traffic modelling and empirical travel-time validation. Do not claim those capabilities until the GPS archive, live feed and evaluation steps above are completed.

## GitHub size note

The downloadable project ZIP includes `data/routepulse.sqlite.gz` so the local demo can start without re-importing the source CSV. This large generated database artifact is ignored by `.gitignore` to avoid pushing a large binary through ordinary Git. Keep the ZIP for local demo use; for a public repository, publish the database separately as a release asset or provide reproducible source-data import instructions.
