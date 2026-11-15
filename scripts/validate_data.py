import sqlite3
from pathlib import Path
DB=Path(__file__).resolve().parents[1]/'data'/'routepulse.sqlite'
con=sqlite3.connect(DB)
for table in ['stops','routes','trips','stop_times','shape_points','demand_route_hour','demand_od','demand_stop','demand_hour','interchange_stops']:
    try: print(f'{table:22} {con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]:>12,}')
    except sqlite3.Error as e: print(f'{table:22} ERROR {e}')
print('ticket transaction rows:',con.execute("SELECT value FROM metadata WHERE key='ticket_rows'").fetchone())
print('integrity:',con.execute('PRAGMA quick_check').fetchone()[0])
print('unmatched trip references:',con.execute('''SELECT COUNT(*) FROM stop_times s LEFT JOIN trips t ON t.trip_id=s.trip_id WHERE t.trip_id IS NULL''').fetchone()[0])
print('unmatched stop references:',con.execute('''SELECT COUNT(*) FROM stop_times s LEFT JOIN stops p ON p.stop_id=s.stop_id WHERE p.stop_id IS NULL''').fetchone()[0])
print('top demand hours:',con.execute('SELECT local_hour,tickets FROM demand_hour ORDER BY tickets DESC LIMIT 4').fetchall())
con.close()
