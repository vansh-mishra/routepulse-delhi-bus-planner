# Dataset manifest — RoutePulse build

This manifest describes the uploaded input data used to build `routepulse.sqlite.gz`.

## Static GTFS inputs

| File | Rows | Used for |
|---|---:|---|
| `stops.txt` | 6,862 | Bus stop names and coordinates |
| `routes.txt` | 2,574 | Route identifiers and names |
| `trips.txt` | 80,357 | Scheduled trips, route links, headsigns and shapes |
| `stop_times.txt` | 2,737,136 | Scheduled arrival/departure times and stop order |
| `shapes.txt` | 965,607 | Ordered route geometry points |
| `agency.txt` | 2 | Agency metadata: DTC and DIMTS |
| `calendar.txt` | 1 | Service calendar; service 1 runs daily for the listed date range |
| `feed_info.txt` | 2 publisher rows | Feed metadata, version `v32` |

Referential checks performed: 80,357 distinct `trip_id` values in `trips.txt` match those in `stop_times.txt`; all stop IDs in `stop_times.txt` exist in `stops.txt`.

## Ticketing input: `October-Delhi.csv`

Supplied columns:

`passenger_count`, `amount`, `vehicle_number`, `ticket_type_id`, `end_stop_name`, `route`, `start_stop_name`, `created_at`, `is_ac`.

Processed totals:

- 2,559,899 ticket transactions.
- Local timestamp range: 1–31 October 2026 (Asia/Kolkata).
- 2,753,606 passengers when summing `passenger_count`.
- 34,176,078 total `amount` units; the file itself does not declare a currency/unit in its header, so the interface labels it as dataset fare amount.
- 2,259 distinct route strings.
- 6,809 distinct non-empty vehicle numbers; `vehicle_number` is missing in 1,242,167 rows.
- Highest ticket transaction count falls at 09:00 local time (351,443 records), followed by 08:00 (316,049), 18:00 (235,349) and 19:00 (222,243).

This is a ticketing/boarding dataset, not a GPS trace dataset. It contains no position coordinates, speed or observed trip-duration field. RoutePulse therefore uses it for demand and fare summaries only.

## GTFS-Realtime

The optional VehiclePositions feed is accessed from the Transport Stack API using an `x-api-key` header. The API key is not included in this project. Add a newly rotated key to `.env` locally or to the hosting provider's secret manager.

## Separate historical GPS database

The hackathon brief also describes daily SQLite GPS movement files. Those files were not among the uploaded source files used to create this build. Their absence is why the current ETA estimate is explicitly schedule-based. Add the actual historical GPS archive after validating its schema; do not use `October-Delhi.csv` as a speed dataset.
