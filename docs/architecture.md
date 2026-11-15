# RoutePulse architecture

## Product flow

1. Visitor lands on the overview page.
2. Visitor opens the public demo and searches for origin and destination stops from the GTFS stop list.
3. Planner finds direct services and up to one bus transfer using trip stop sequences and departure/arrival times.
4. Route shapes are displayed on the map.
5. Journey options state clearly that durations are schedule-based.
6. Signed-in users can save journeys and revisit them.
7. Data insights explain route/time demand from ticket transactions.

## Data flow

```text
Static GTFS text files ──> database builder ──> SQLite
  stops / routes / trips / stop_times / shapes
                                      │
                                      ├──> Stop search
                                      ├──> Scheduled direct/transfer search
                                      └──> Shape geometry on map

October-Delhi.csv ──> chunked aggregation ──> SQLite demand tables
  route / start / end / passenger_count / amount / created_at / is_ac
                                      │
                                      └──> Demand analytics only

GTFS-Realtime API ──> x-api-key header ──> protobuf decoder ──> vehicle positions
```

## Journey-time logic

- Departure time is mapped to seconds after local midnight.
- Direct candidates join a boarding stop and a later alighting stop on the same trip.
- Transfer candidates use stops served by multiple routes and search a connecting trip departing at least five minutes after the first bus arrives.
- Total elapsed time includes initial scheduled wait, scheduled onboard time, transfer wait and user-specified walk-in/walk-out buffers.
- Route geometry is loaded using `shape_id` and ordered shape points.

## Data science boundary

The October ticket file is ticketing demand, not historical vehicle telemetry. It supports temporal/route demand views but not road speed estimation. A true travel-time model needs the separate historical GPS SQLite archive, map matching, timestamp ordering per vehicle, outlier handling, route/segment assignment, time-of-day/day-of-week profiles, and validation against observed trip durations.
