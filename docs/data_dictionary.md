# Data dictionary used by RoutePulse

## Static GTFS

- `stops.txt`: stop identifier, code, display name, latitude, longitude.
- `routes.txt`: agency, route identifier, short/long names, route description and route type.
- `trips.txt`: trip identifier, route/service identifiers, headsign and shape identifier.
- `stop_times.txt`: trip, arrival/departure time, stop identifier and stop sequence.
- `shapes.txt`: shape identifier, ordered latitude/longitude points and shape distance.
- `agency.txt`, `calendar.txt`, `feed_info.txt`: agency, service calendar and feed metadata.

## October-Delhi.csv

Supplied columns: `passenger_count`, `amount`, `vehicle_number`, `ticket_type_id`, `end_stop_name`, `route`, `start_stop_name`, `created_at`, `is_ac`.

Interpretation: ticket transaction events. RoutePulse aggregates ticket counts, passenger counts and fare by route/hour; origin-destination pair counts; and boarding/alighting stop counts. Timestamps are stored with the `+05:30` offset and are grouped by their local clock hour.

`vehicle_number` is missing in a portion of records. The file does not contain latitude, longitude, bus speed or an observed trip-duration field.

## Separate historical GPS archive needed

The hackathon brief describes daily SQLite files named `bus_movements_YYYY_MM_DD.db`. That archive is not one of the source files included in this project build. It is required for genuine historical travel-time estimation.
