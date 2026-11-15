from __future__ import annotations
import argparse, csv, os, sqlite3, sys, time
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]

def gtfs_seconds(value: str | None):
    if not value:
        return None
    try:
        h, m, s = value.strip().split(':')
        return int(h) * 3600 + int(m) * 60 + int(float(s))
    except Exception:
        return None

def ensure_schema(con: sqlite3.Connection):
    con.executescript('''
    PRAGMA journal_mode=WAL;
    PRAGMA synchronous=NORMAL;
    PRAGMA temp_store=MEMORY;
    CREATE TABLE IF NOT EXISTS agencies(agency_id TEXT PRIMARY KEY, agency_name TEXT, agency_url TEXT, agency_timezone TEXT, agency_lang TEXT);
    CREATE TABLE IF NOT EXISTS service_calendar(service_id TEXT PRIMARY KEY, monday INTEGER,tuesday INTEGER,wednesday INTEGER,thursday INTEGER,friday INTEGER,saturday INTEGER,sunday INTEGER,start_date TEXT,end_date TEXT);
    CREATE TABLE IF NOT EXISTS feed_info(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS stops(
      stop_id TEXT PRIMARY KEY, stop_code TEXT, stop_name TEXT NOT NULL,
      stop_lat REAL, stop_lon REAL
    );
    CREATE TABLE IF NOT EXISTS routes(
      route_id TEXT PRIMARY KEY, agency_id TEXT, route_short_name TEXT,
      route_long_name TEXT, route_desc TEXT, route_type INTEGER
    );
    CREATE TABLE IF NOT EXISTS trips(
      trip_id TEXT PRIMARY KEY, route_id TEXT NOT NULL, service_id TEXT,
      trip_headsign TEXT, shape_id TEXT, direction_id TEXT
    );
    CREATE TABLE IF NOT EXISTS stop_times(
      trip_id TEXT NOT NULL, arrival_sec INTEGER, departure_sec INTEGER,
      stop_id TEXT NOT NULL, stop_sequence INTEGER NOT NULL,
      PRIMARY KEY(trip_id, stop_sequence)
    );
    CREATE TABLE IF NOT EXISTS shape_points(
      shape_id TEXT NOT NULL, point_sequence INTEGER NOT NULL,
      lat REAL NOT NULL, lon REAL NOT NULL, distance_m REAL,
      PRIMARY KEY(shape_id, point_sequence)
    );
    CREATE TABLE IF NOT EXISTS demand_route_hour(
      route_short_name TEXT NOT NULL, local_hour INTEGER NOT NULL,
      tickets INTEGER NOT NULL, passengers INTEGER NOT NULL,
      revenue REAL NOT NULL, ac_tickets INTEGER NOT NULL,
      PRIMARY KEY(route_short_name, local_hour)
    );
    CREATE TABLE IF NOT EXISTS demand_od(
      route_short_name TEXT NOT NULL, start_stop TEXT NOT NULL, end_stop TEXT NOT NULL,
      tickets INTEGER NOT NULL, passengers INTEGER NOT NULL, revenue REAL NOT NULL,
      PRIMARY KEY(route_short_name, start_stop, end_stop)
    );
    CREATE TABLE IF NOT EXISTS demand_stop(
      stop_name TEXT PRIMARY KEY, boardings INTEGER NOT NULL, alightings INTEGER NOT NULL,
      passengers_boarding INTEGER NOT NULL, passengers_alighting INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS demand_hour(
      local_hour INTEGER PRIMARY KEY, tickets INTEGER NOT NULL,
      passengers INTEGER NOT NULL, revenue REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    ''')

def read_csv_rows(path: Path):
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        yield from csv.DictReader(f)

def import_static(con, source: Path):
    specs = [
      ('stops.txt', 'INSERT OR REPLACE INTO stops VALUES(?,?,?,?,?)',
       lambda r: (r['stop_id'], r.get('stop_code') or None, r['stop_name'], float(r['stop_lat']), float(r['stop_lon']))),
      ('routes.txt', 'INSERT OR REPLACE INTO routes VALUES(?,?,?,?,?,?)',
       lambda r: (r['route_id'], r.get('agency_id') or None, r.get('route_short_name') or None, r.get('route_long_name') or None, r.get('route_desc') or None, int(r.get('route_type') or 3))),
      ('trips.txt', 'INSERT OR REPLACE INTO trips VALUES(?,?,?,?,?,?)',
       lambda r: (r['trip_id'], r['route_id'], r.get('service_id') or None, r.get('trip_headsign') or None, r.get('shape_id') or None, r.get('direction_id') or None)),
      ('stop_times.txt', 'INSERT OR REPLACE INTO stop_times VALUES(?,?,?,?,?)',
       lambda r: (r['trip_id'], gtfs_seconds(r.get('arrival_time')), gtfs_seconds(r.get('departure_time')), r['stop_id'], int(r['stop_sequence']))),
      ('shapes.txt', 'INSERT OR REPLACE INTO shape_points VALUES(?,?,?,?,?)',
       lambda r: (r['shape_id'], int(r['shape_pt_sequence']), float(r['shape_pt_lat']), float(r['shape_pt_lon']), float(r['shape_dist_traveled']) if r.get('shape_dist_traveled') else None)),
    ]
    for filename, sql, converter in specs:
        path = source / filename
        if not path.exists():
            raise FileNotFoundError(f'Missing {filename} in {source}')
        started = time.time(); batch = []; total = 0
        for row in read_csv_rows(path):
            try: batch.append(converter(row))
            except Exception as exc:
                print(f'Skipping invalid row in {filename}: {exc}', file=sys.stderr)
            if len(batch) >= 20000:
                con.executemany(sql, batch); total += len(batch); batch.clear()
        if batch:
            con.executemany(sql, batch); total += len(batch)
        con.commit()
        print(f'Imported {filename}: {total:,} rows in {time.time()-started:.1f}s')

def import_auxiliary(con, source: Path):
    agency_path = source / 'agency.txt'
    if agency_path.exists():
        con.executemany('INSERT OR REPLACE INTO agencies VALUES(?,?,?,?,?)',
            [(r['agency_id'],r.get('agency_name'),r.get('agency_url'),r.get('agency_timezone'),r.get('agency_lang')) for r in read_csv_rows(agency_path)])
    calendar_path = source / 'calendar.txt'
    if calendar_path.exists():
        con.executemany('INSERT OR REPLACE INTO service_calendar VALUES(?,?,?,?,?,?,?,?,?,?)',
            [(r['service_id'],int(r['monday']),int(r['tuesday']),int(r['wednesday']),int(r['thursday']),int(r['friday']),int(r['saturday']),int(r['sunday']),r['start_date'],r['end_date']) for r in read_csv_rows(calendar_path)])
    feed_path = source / 'feed_info.txt'
    if feed_path.exists():
        for row in read_csv_rows(feed_path):
            for key,value in row.items(): con.execute('INSERT OR REPLACE INTO feed_info VALUES(?,?)',(key,value or ''))
    con.commit()


def add_indexes(con):
    con.executescript('''
      CREATE INDEX IF NOT EXISTS idx_stops_name ON stops(stop_name);
      CREATE INDEX IF NOT EXISTS idx_routes_short ON routes(route_short_name);
      CREATE INDEX IF NOT EXISTS idx_trips_route ON trips(route_id);
      CREATE INDEX IF NOT EXISTS idx_stop_times_stop_departure ON stop_times(stop_id, departure_sec);
      CREATE INDEX IF NOT EXISTS idx_demand_route_hour ON demand_route_hour(route_short_name, local_hour);
      CREATE INDEX IF NOT EXISTS idx_demand_od_route ON demand_od(route_short_name, tickets DESC);
    ''')
    # Stop interchange utility: count different routes that call at each stop.
    con.executescript('''
      DROP TABLE IF EXISTS interchange_stops;
      CREATE TABLE interchange_stops AS
      SELECT st.stop_id, COUNT(DISTINCT t.route_id) AS route_count
      FROM stop_times st JOIN trips t ON t.trip_id=st.trip_id
      GROUP BY st.stop_id HAVING COUNT(DISTINCT t.route_id) >= 2;
      CREATE INDEX idx_interchange_route_count ON interchange_stops(route_count DESC);
    ''')
    con.commit()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source', type=Path, default=ROOT/'data'/'source')
    ap.add_argument('--tickets', type=Path, default=None)
    ap.add_argument('--output', type=Path, default=ROOT/'data'/'routepulse.sqlite')
    args=ap.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.output.exists(): args.output.unlink()
    con=sqlite3.connect(args.output)
    try:
      ensure_schema(con)
      import_static(con,args.source)
      import_auxiliary(con,args.source)
      add_indexes(con)
      for key, query in [
        ('stops_count','SELECT COUNT(*) FROM stops'),('routes_count','SELECT COUNT(*) FROM routes'),
        ('trips_count','SELECT COUNT(*) FROM trips'),('stop_times_count','SELECT COUNT(*) FROM stop_times'),
        ('shape_points_count','SELECT COUNT(*) FROM shape_points'),
        ('ticket_route_count','SELECT COUNT(DISTINCT route_short_name) FROM demand_route_hour'),
      ]:
        val=str(con.execute(query).fetchone()[0]); con.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',(key,val))
      con.execute("INSERT OR REPLACE INTO metadata VALUES('built_at',?)",(datetime.now().isoformat(timespec='seconds'),))
      con.commit(); con.execute('ANALYZE'); con.commit(); con.execute('VACUUM')
      con.close()
      import subprocess
      ticket_path=args.tickets or (args.source/'October-Delhi.csv')
      if ticket_path.exists(): subprocess.run([sys.executable,str(ROOT/'scripts'/'import_ticket_demand.py'),'--csv',str(ticket_path),'--db',str(args.output)],check=True)
      print('DATABASE READY:',args.output, f'({args.output.stat().st_size/1024/1024:.1f} MB)')
      return
    finally: con.close()
if __name__=='__main__': main()
