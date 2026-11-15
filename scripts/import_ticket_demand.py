from __future__ import annotations
import argparse, sqlite3, time
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--csv',type=Path,default=ROOT/'data'/'source'/'October-Delhi.csv'); ap.add_argument('--db',type=Path,default=ROOT/'data'/'routepulse.sqlite'); args=ap.parse_args()
 con=sqlite3.connect(args.db)
 con.execute('PRAGMA journal_mode=WAL'); con.execute('PRAGMA synchronous=NORMAL')
 con.executescript('''
 DROP TABLE IF EXISTS demand_route_hour; DROP TABLE IF EXISTS demand_od; DROP TABLE IF EXISTS demand_stop; DROP TABLE IF EXISTS demand_hour;
 CREATE TABLE demand_route_hour(route_short_name TEXT,local_hour INTEGER,tickets INTEGER,passengers INTEGER,revenue REAL,ac_tickets INTEGER,PRIMARY KEY(route_short_name,local_hour));
 CREATE TABLE demand_od(route_short_name TEXT,start_stop TEXT,end_stop TEXT,tickets INTEGER,passengers INTEGER,revenue REAL,PRIMARY KEY(route_short_name,start_stop,end_stop));
 CREATE TABLE demand_stop(stop_name TEXT PRIMARY KEY,boardings INTEGER,alightings INTEGER,passengers_boarding INTEGER,passengers_alighting INTEGER);
 CREATE TABLE demand_hour(local_hour INTEGER PRIMARY KEY,tickets INTEGER,passengers INTEGER,revenue REAL);
 CREATE TEMP TABLE s_rh(route TEXT,hour INTEGER,tickets INTEGER,pax INTEGER,revenue REAL,ac INTEGER);
 CREATE TEMP TABLE s_od(route TEXT,start TEXT,end TEXT,tickets INTEGER,pax INTEGER,revenue REAL);
 CREATE TEMP TABLE s_stop(name TEXT,board INTEGER,alight INTEGER,board_pax INTEGER,alight_pax INTEGER);
 CREATE TEMP TABLE s_hour(hour INTEGER,tickets INTEGER,pax INTEGER,revenue REAL);
 ''')
 total=0; start=time.time(); min_date=None; max_date=None; missing_vehicle=0; vehicle_ids=set(); route_names=set(); start_names=set(); end_names=set(); use=['passenger_count','amount','end_stop_name','route','start_stop_name','created_at','is_ac','vehicle_number']
 for chunk in pd.read_csv(args.csv,usecols=use,chunksize=220000,low_memory=False):
  created=chunk['created_at'].astype(str); hour=pd.to_numeric(created.str.slice(11,13),errors='coerce').fillna(0).astype('int16')
  dates=created.str.slice(0,10); chunk_min=dates.min(); chunk_max=dates.max(); min_date=chunk_min if min_date is None else min(min_date,chunk_min); max_date=chunk_max if max_date is None else max(max_date,chunk_max)
  missing_vehicle += int(chunk['vehicle_number'].isna().sum()); vehicle_ids.update(chunk['vehicle_number'].dropna().astype(str).unique())
  route_names.update(chunk['route'].dropna().astype(str).str.strip().unique()); start_names.update(chunk['start_stop_name'].dropna().astype(str).str.strip().unique()); end_names.update(chunk['end_stop_name'].dropna().astype(str).str.strip().unique())
  d=pd.DataFrame({'route':chunk['route'].fillna('').astype(str).str.strip(),'start':chunk['start_stop_name'].fillna('').astype(str).str.strip(),'end':chunk['end_stop_name'].fillna('').astype(str).str.strip(),'hour':hour,'pax':pd.to_numeric(chunk.passenger_count,errors='coerce').fillna(0).astype('int32'),'revenue':pd.to_numeric(chunk.amount,errors='coerce').fillna(0.0).astype('float32'),'ac':chunk.is_ac.astype(str).str.lower().isin(['true','1','yes']).astype('int8')})
  # Compact, grouped rows are much faster to store than all raw ticket records.
  rh=d.groupby(['route','hour'],as_index=False).agg(tickets=('route','size'),pax=('pax','sum'),revenue=('revenue','sum'),ac=('ac','sum'))
  od=d.groupby(['route','start','end'],as_index=False).agg(tickets=('route','size'),pax=('pax','sum'),revenue=('revenue','sum'))
  st1=d[d.start!=''].groupby('start',as_index=False).agg(board=('route','size'),board_pax=('pax','sum')); st1['alight']=0; st1['alight_pax']=0; st1=st1[['start','board','alight','board_pax','alight_pax']].rename(columns={'start':'name'})
  st2=d[d.end!=''].groupby('end',as_index=False).agg(alight=('route','size'),alight_pax=('pax','sum')); st2['board']=0; st2['board_pax']=0; st2=st2[['end','board','alight','board_pax','alight_pax']].rename(columns={'end':'name'})
  hh=d.groupby('hour',as_index=False).agg(tickets=('route','size'),pax=('pax','sum'),revenue=('revenue','sum'))
  con.executemany('INSERT INTO s_rh VALUES(?,?,?,?,?,?)',rh.itertuples(index=False,name=None))
  con.executemany('INSERT INTO s_od VALUES(?,?,?,?,?,?)',od.itertuples(index=False,name=None))
  con.executemany('INSERT INTO s_stop VALUES(?,?,?,?,?)',st1.itertuples(index=False,name=None)); con.executemany('INSERT INTO s_stop VALUES(?,?,?,?,?)',st2.itertuples(index=False,name=None))
  con.executemany('INSERT INTO s_hour VALUES(?,?,?,?)',hh.itertuples(index=False,name=None))
  total+=len(d); con.commit(); print(f'Aggregated {total:,} ticket records',flush=True)
 con.executescript('''
 INSERT INTO demand_route_hour SELECT route,hour,SUM(tickets),SUM(pax),SUM(revenue),SUM(ac) FROM s_rh GROUP BY route,hour;
 INSERT INTO demand_od SELECT route,start,end,SUM(tickets),SUM(pax),SUM(revenue) FROM s_od GROUP BY route,start,end ORDER BY SUM(tickets) DESC LIMIT 30000;
 INSERT INTO demand_stop SELECT name,SUM(board),SUM(alight),SUM(board_pax),SUM(alight_pax) FROM s_stop GROUP BY name;
 INSERT INTO demand_hour SELECT hour,SUM(tickets),SUM(pax),SUM(revenue) FROM s_hour GROUP BY hour;
 DROP TABLE s_rh; DROP TABLE s_od; DROP TABLE s_stop; DROP TABLE s_hour;
 ''')
 con.execute("INSERT OR REPLACE INTO metadata VALUES('ticket_rows',?)",(str(total),))
 con.execute("INSERT OR REPLACE INTO metadata VALUES('ticket_csv_name',?)",(args.csv.name,))
 for key,value in [('ticket_date_start',min_date or ''),('ticket_date_end',max_date or ''),('ticket_vehicle_missing',str(missing_vehicle)),('ticket_unique_vehicles',str(len(vehicle_ids))),('ticket_unique_routes',str(len(route_names))),('ticket_unique_board_stops',str(len(start_names))),('ticket_unique_alight_stops',str(len(end_names)))]:
  con.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',(key,value))
 con.executescript('CREATE INDEX IF NOT EXISTS idx_demand_route_hour ON demand_route_hour(route_short_name,local_hour); CREATE INDEX IF NOT EXISTS idx_demand_od_route ON demand_od(route_short_name,tickets DESC);')
 con.commit(); con.execute('ANALYZE'); con.commit(); con.execute('VACUUM')
 print('Demand import done in',round(time.time()-start,1),'seconds; db size',round(args.db.stat().st_size/1024/1024,1),'MB')
 con.close()
if __name__=='__main__': main()
