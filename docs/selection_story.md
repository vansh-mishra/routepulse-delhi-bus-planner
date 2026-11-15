# RoutePulse — problem/solution story for the hackathon

## Problem
Bus travel time in Delhi varies with time and operating conditions. A timetable is useful for discovering services but does not by itself describe actual road movement.

## Prototype delivered
- Searchable stop-to-stop journey planner using the supplied GTFS network.
- Direct and one-transfer options based on scheduled trips and stop sequences.
- GTFS shape geometry shown on a map.
- October 2026 ticket-demand analytics by route, hour, OD pair and stop.
- Optional live GTFS-Realtime vehicle-position connector.
- Public demo, account creation and saved journey flow.

## Evidence from supplied files
- 6,862 stops, 2,574 routes, 80,357 trips, 2,737,136 stop-time rows and 965,607 shape points.
- 2,559,899 ticket transactions in October-Delhi.csv.
- All stop-time trip references match trips.txt; all stop IDs match stops.txt.

## Honest technical boundary
The uploaded October CSV is a ticketing dataset. It records passenger_count, amount, vehicle_number, ticket_type_id, end_stop_name, route, start_stop_name, created_at and is_ac. It has no latitude, longitude, speed or observed arrival time, so it cannot train a road-speed model. The current ETA baseline therefore uses scheduled GTFS travel times. Live GTFS-RT can be activated with a new API key. To satisfy the traffic-model part fully, the separate historical GPS SQLite archive must be loaded, map-matched to the GTFS network, profiled by time-of-day/day-of-week and evaluated against observed trips and Google Maps.

## Recommended next technical milestone
Add the historical GPS SQLite archive to the data pipeline. For each bus, order GPS observations by timestamp, remove impossible jumps, map-match points to route/road segments, calculate observed segment speeds and build robust median speed profiles per segment/time bucket. Use those profiles to adjust GTFS segment times. Report MAE, RMSE, median absolute error and the percentage of predictions within 5/10 minutes on held-out trips.
