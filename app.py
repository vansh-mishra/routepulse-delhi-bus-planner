from __future__ import annotations
import os, sqlite3, time, math, gzip, shutil
from datetime import datetime, date
from zoneinfo import ZoneInfo
from functools import wraps
from pathlib import Path
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
DB_PATH = Path(os.getenv('ROUTEPULSE_DB', ROOT / 'data' / 'routepulse.sqlite'))
if not DB_PATH.is_absolute():
    DB_PATH = ROOT / DB_PATH
app = Flask(__name__)
_configured_secret = os.getenv('SECRET_KEY', '').strip()
# Use a random per-process fallback for local demonstrations instead of a predictable hard-coded secret.
# Set SECRET_KEY in .env and in the hosting provider for stable sessions across restarts.
app.secret_key = _configured_secret or os.urandom(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.getenv('SESSION_COOKIE_SECURE', '0').lower() in ('1', 'true', 'yes'),
)

LIVE_URL = os.getenv('TRANSPORT_STACK_FEED_URL', 'https://dts-backend.transportstack.in/api/dataset/otd/get-file?agency=delhi-buses&category=realtime_gtfs&filename=VehiclePositions.pb')
LIVE_KEY = os.getenv('TRANSPORT_STACK_API_KEY', '').strip()
_live_cache = {'at': 0.0, 'payload': None}


def db():
    if not DB_PATH.exists():
        compressed = Path(str(DB_PATH) + '.gz')
        if compressed.exists():
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            temp_path = Path(str(DB_PATH) + f'.{os.getpid()}.extracting')
            with gzip.open(compressed, 'rb') as source, temp_path.open('wb') as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            temp_path.replace(DB_PATH)
        else:
            raise RuntimeError(f'Database not found at {DB_PATH}. Keep data/routepulse.sqlite.gz in place or rebuild from source files.')
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    return con


def meta(con, key, default='0'):
    row = con.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
    return row['value'] if row else default


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            flash('Sign in to save and revisit your journeys.', 'info')
            return redirect(url_for('login', next=request.path))
        return fn(*args, **kwargs)
    return wrapper


def _clock(seconds):
    if seconds is None: return '—'
    seconds = int(seconds)
    day_offset, rem = divmod(seconds, 86400)
    hh, rem = divmod(rem, 3600); mm, _ = divmod(rem, 60)
    suffix = f' (+{day_offset} day)' if day_offset else ''
    return f'{hh%24:02d}:{mm:02d}{suffix}'


def _service_seconds(value):
    try:
        h, m = value.split(':')[:2]
        s = value.split(':')[2] if len(value.split(':')) > 2 else '0'
        return int(h)*3600 + int(m)*60 + int(float(s))
    except Exception:
        return 0


def _shape(con, shape_id, max_points=100):
    if not shape_id: return []
    rows = con.execute('SELECT lat,lon FROM shape_points WHERE shape_id=? ORDER BY point_sequence', (shape_id,)).fetchall()
    if len(rows) > max_points:
        step = max(1, math.ceil(len(rows) / max_points))
        rows = rows[::step]
        if rows[-1] != con.execute('SELECT lat,lon FROM shape_points WHERE shape_id=? ORDER BY point_sequence DESC LIMIT 1',(shape_id,)).fetchone():
            last = con.execute('SELECT lat,lon FROM shape_points WHERE shape_id=? ORDER BY point_sequence DESC LIMIT 1',(shape_id,)).fetchone()
            if last: rows.append(last)
    return [[round(float(r['lat']), 6), round(float(r['lon']), 6)] for r in rows]


def _route_demand(con, route_short_name, hour):
    if not route_short_name: return None
    row = con.execute('SELECT tickets,passengers,revenue,ac_tickets FROM demand_route_hour WHERE route_short_name=? AND local_hour=?', (route_short_name, hour)).fetchone()
    if not row: return None
    return {'tickets': int(row['tickets']), 'passengers': int(row['passengers']), 'revenue': round(float(row['revenue']), 2), 'ac_share': round((row['ac_tickets'] / row['tickets'] * 100) if row['tickets'] else 0, 1)}


def _leg_payload(con, row, board_stop_id, alight_stop_id, board_seq, alight_seq, hour):
    board = con.execute('SELECT stop_name,stop_lat,stop_lon FROM stops WHERE stop_id=?', (board_stop_id,)).fetchone()
    alight = con.execute('SELECT stop_name,stop_lat,stop_lon FROM stops WHERE stop_id=?', (alight_stop_id,)).fetchone()
    demand = _route_demand(con, row['route_short_name'], hour)
    return {
      'trip_id': row['trip_id'], 'route_id': row['route_id'],
      'route': row['route_short_name'] or row['route_long_name'] or row['route_id'],
      'route_name': row['route_desc'] or row['route_long_name'] or row['route_short_name'] or row['route_id'],
      'headsign': row['trip_headsign'] or '', 'shape_id': row['shape_id'],
      'from_stop_id': board_stop_id, 'from_stop': board['stop_name'] if board else str(board_stop_id),
      'to_stop_id': alight_stop_id, 'to_stop': alight['stop_name'] if alight else str(alight_stop_id),
      'from_lat': board['stop_lat'] if board else None, 'from_lon': board['stop_lon'] if board else None,
      'to_lat': alight['stop_lat'] if alight else None, 'to_lon': alight['stop_lon'] if alight else None,
      'departure_sec': int(row['departure_sec']), 'arrival_sec': int(row['arrival_sec']),
      'departure': _clock(row['departure_sec']), 'arrival': _clock(row['arrival_sec']),
      'ride_minutes': max(0, round((int(row['arrival_sec'])-int(row['departure_sec']))/60, 1)),
      'demand': demand, 'geometry': _shape(con, row['shape_id'])
    }


def _direct_query(con, board_id, destination_id, earliest_sec, limit=8, exclude_route=None):
    sql = '''SELECT d.trip_id,d.departure_sec,a.arrival_sec,d.stop_sequence AS board_seq,
                    a.stop_sequence AS alight_seq,t.route_id,t.shape_id,t.trip_headsign,
                    r.route_short_name,r.route_long_name,r.route_desc
             FROM stop_times d
             JOIN stop_times a ON a.trip_id=d.trip_id AND a.stop_id=? AND a.stop_sequence>d.stop_sequence
             JOIN trips t ON t.trip_id=d.trip_id
             JOIN routes r ON r.route_id=t.route_id
             WHERE d.stop_id=? AND d.departure_sec>=?'''
    params = [destination_id, board_id, earliest_sec]
    if exclude_route:
        sql += ' AND t.route_id<>?'; params.append(exclude_route)
    sql += ' ORDER BY d.departure_sec ASC,a.arrival_sec ASC LIMIT ?'; params.append(limit)
    return con.execute(sql, params).fetchall()


def plan_journeys(origin_id, destination_id, departure_sec, walk_in=5, walk_out=5):
    con = db()
    try:
        origin = con.execute('SELECT * FROM stops WHERE stop_id=?',(str(origin_id),)).fetchone()
        destination = con.execute('SELECT * FROM stops WHERE stop_id=?',(str(destination_id),)).fetchone()
        if not origin or not destination: return {'error':'Choose valid origin and destination stops from the suggestions.'}, 400
        if str(origin_id) == str(destination_id): return {'error':'Origin and destination must be different.'}, 400
        hour = (departure_sec // 3600) % 24
        options=[]
        # Direct services: one option per scheduled trip.
        direct = _direct_query(con, str(origin_id), str(destination_id), departure_sec, limit=12)
        for row in direct:
            leg = _leg_payload(con,row,str(origin_id),str(destination_id),row['board_seq'],row['alight_seq'],hour)
            arr = int(row['arrival_sec'])
            wait = max(0, int(row['departure_sec']) - departure_sec)
            total = wait + leg['ride_minutes']*60 + (walk_in+walk_out)*60
            options.append({'kind':'direct','legs':[leg],'transfer_count':0,'transfer_stop':None,
                'wait_minutes':round(wait/60,1),'walk_in_minutes':walk_in,'walk_out_minutes':walk_out,
                'total_minutes':round(total/60,1),'arrival_sec':arr+walk_out*60,
                'departure_sec':departure_sec,'source':'GTFS scheduled service','is_schedule_based':True})
        # One-transfer journeys via stops served by at least two routes.
        firsts = con.execute('''SELECT s.trip_id,s.departure_sec,s.stop_sequence,t.route_id
            FROM stop_times s JOIN trips t ON t.trip_id=s.trip_id
            WHERE s.stop_id=? AND s.departure_sec>=? ORDER BY s.departure_sec LIMIT 14''',(str(origin_id),departure_sec)).fetchall()
        seen=set()
        for first in firsts:
            transfer_stops = con.execute('''SELECT s.stop_id,s.arrival_sec,s.stop_sequence,st.stop_name
                FROM stop_times s JOIN stops st ON st.stop_id=s.stop_id
                JOIN interchange_stops h ON h.stop_id=s.stop_id
                WHERE s.trip_id=? AND s.stop_sequence>? AND s.stop_id<>?
                ORDER BY s.stop_sequence LIMIT 40''',(first['trip_id'],first['stop_sequence'],str(origin_id))).fetchall()
            for hub in transfer_stops:
                second_rows = _direct_query(con,hub['stop_id'],str(destination_id),int(hub['arrival_sec'])+300,limit=1,exclude_route=first['route_id'])
                if not second_rows: continue
                first_row = con.execute('''SELECT s.trip_id,s.departure_sec,e.arrival_sec AS arrival_sec,s.stop_sequence AS board_seq,
                    e.stop_sequence AS alight_seq,t.route_id,t.shape_id,t.trip_headsign,r.route_short_name,r.route_long_name,r.route_desc
                    FROM stop_times s JOIN stop_times e ON e.trip_id=s.trip_id AND e.stop_id=? AND e.stop_sequence>s.stop_sequence
                    JOIN trips t ON t.trip_id=s.trip_id JOIN routes r ON r.route_id=t.route_id
                    WHERE s.trip_id=? AND s.stop_id=? AND s.stop_sequence=? LIMIT 1''',
                    (hub['stop_id'],first['trip_id'],str(origin_id),first['stop_sequence'])).fetchone()
                if not first_row: continue
                second=second_rows[0]
                key=(first['trip_id'],second['trip_id'],hub['stop_id'])
                if key in seen: continue
                seen.add(key)
                leg1=_leg_payload(con,first_row,str(origin_id),hub['stop_id'],first_row['board_seq'],first_row['alight_seq'],hour)
                leg2=_leg_payload(con,second,hub['stop_id'],str(destination_id),second['board_seq'],second['alight_seq'],(int(second['departure_sec'])//3600)%24)
                initial_wait=max(0,int(first_row['departure_sec'])-departure_sec)
                transfer_wait=max(0,int(second['departure_sec'])-int(first_row['arrival_sec']))
                total=initial_wait+int(first_row['arrival_sec'])-int(first_row['departure_sec'])+transfer_wait+int(second['arrival_sec'])-int(second['departure_sec'])+(walk_in+walk_out)*60
                options.append({'kind':'transfer','legs':[leg1,leg2],'transfer_count':1,'transfer_stop':hub['stop_name'],
                    'wait_minutes':round(initial_wait/60,1),'transfer_wait_minutes':round(transfer_wait/60,1),
                    'walk_in_minutes':walk_in,'walk_out_minutes':walk_out,'total_minutes':round(total/60,1),
                    'arrival_sec':int(second['arrival_sec'])+walk_out*60,'departure_sec':departure_sec,
                    'source':'GTFS scheduled service','is_schedule_based':True})
        # Keep materially different trip alternatives and sort by total elapsed time.
        options.sort(key=lambda x:(x['total_minutes'],x['arrival_sec'],x['transfer_count']))
        unique=[]; signatures=set()
        for option in options:
            sig=tuple((leg['route'],leg['departure_sec'],leg['to_stop_id']) for leg in option['legs'])
            if sig in signatures: continue
            signatures.add(sig); unique.append(option)
            if len(unique)>=3: break
        for i,opt in enumerate(unique,1):
            opt['id']=i; opt['arrival']=_clock(opt['arrival_sec'])
            for leg in opt['legs']: leg.pop('geometry',None)
        # Include route geometry only for chosen options in a dedicated lightweight map payload.
        map_legs=[]
        for opt in unique:
            for leg in opt['legs']:
                if leg['shape_id']:
                    map_legs.append({'route':leg['route'],'geometry':_shape(con,leg['shape_id']),'from_stop':leg['from_stop'],'to_stop':leg['to_stop']})
        return {'origin':dict(origin),'destination':dict(destination),'departure':_clock(departure_sec),
                'options':unique,'map_legs':map_legs,'model_note':'Journey times are timetable-based. Ticketing records inform demand insights, not road-speed prediction.'},200
    finally:
        con.close()


def live_vehicle_data(force=False):
    now=time.time()
    if not force and _live_cache['payload'] is not None and now-_live_cache['at']<20:
        return _live_cache['payload']
    if not LIVE_KEY:
        payload={'status':'not_configured','message':'Add your rotated Transport Stack key to .env to enable live vehicle positions.','vehicles':[],'count':0}
    else:
        try:
            import requests
            from google.transit import gtfs_realtime_pb2
            response=requests.get(LIVE_URL,headers={'x-api-key':LIVE_KEY},timeout=15)
            response.raise_for_status()
            feed=gtfs_realtime_pb2.FeedMessage(); feed.ParseFromString(response.content)
            vehicles=[]
            for entity in feed.entity:
                if not entity.HasField('vehicle'): continue
                v=entity.vehicle
                if not v.HasField('position'): continue
                vehicles.append({'vehicle_id':v.vehicle.id if v.HasField('vehicle') else entity.id,
                    'route_id':v.trip.route_id if v.HasField('trip') else None,
                    'lat':v.position.latitude,'lon':v.position.longitude,
                    'speed_kmh':round(v.position.speed*3.6,1) if v.position.HasField('speed') else None,
                    'bearing':v.position.bearing if v.position.HasField('bearing') else None,
                    'timestamp':int(v.timestamp) if v.HasField('timestamp') else None})
            payload={'status':'connected','message':'Live vehicle positions received from Transport Stack.','vehicles':vehicles,'count':len(vehicles)}
        except Exception as exc:
            payload={'status':'error','message':f'Live feed could not be read: {type(exc).__name__}. Check the endpoint, key and network.','vehicles':[],'count':0}
    _live_cache.update(at=now,payload=payload)
    return payload


@app.get('/')
def home():
    con=db()
    try:
        stats={'stops':int(meta(con,'stops_count')),'routes':int(meta(con,'routes_count')),'trips':int(meta(con,'trips_count')),'ticket_rows':int(meta(con,'ticket_rows'))}
        return render_template('index.html',stats=stats,user=session.get('user_name'))
    finally: con.close()

@app.get('/demo')
def demo():
    local_now=datetime.now(ZoneInfo('Asia/Kolkata'))
    return render_template('demo.html',user=session.get('user_name'),today=local_now.date().isoformat(),now=local_now.strftime('%H:%M'))

@app.get('/insights')
def insights():
    con=db()
    try:
        summary={'ticket_records':int(meta(con,'ticket_rows')),'stops':int(meta(con,'stops_count')),'routes':int(meta(con,'routes_count')),'trips':int(meta(con,'trips_count'))}
        hourly=[dict(r) for r in con.execute('SELECT local_hour AS hour,tickets,passengers,revenue FROM demand_hour ORDER BY local_hour')]
        routes=[dict(r) for r in con.execute('''SELECT d.route_short_name AS route,SUM(d.tickets) tickets,SUM(d.passengers) passengers,SUM(d.revenue) revenue
            FROM demand_route_hour d GROUP BY d.route_short_name ORDER BY tickets DESC LIMIT 10''')]
        ods=[dict(r) for r in con.execute('SELECT route_short_name AS route,start_stop,end_stop,tickets,passengers FROM demand_od ORDER BY tickets DESC LIMIT 10')]
        top_stops=[dict(r) for r in con.execute('SELECT stop_name,boardings,alightings FROM demand_stop ORDER BY boardings DESC LIMIT 10')]
        total_rev=con.execute('SELECT SUM(revenue) FROM demand_hour').fetchone()[0] or 0
        total_pax=con.execute('SELECT SUM(passengers) FROM demand_hour').fetchone()[0] or 0
        summary['revenue']=round(float(total_rev),2); summary['passengers']=int(total_pax)
        peak=max(hourly,key=lambda x:x['tickets']) if hourly else {'hour':0,'tickets':0}
        summary['peak_hour']=peak['hour']
        return render_template('insights.html',summary=summary,hourly=hourly,routes=routes,ods=ods,top_stops=top_stops,user=session.get('user_name'))
    finally: con.close()

@app.get('/api/health')
def api_health():
    con=db()
    try:
        return jsonify({'status':'ok','database':'loaded','gtfs':{
          'stops':int(meta(con,'stops_count')),'routes':int(meta(con,'routes_count')),'trips':int(meta(con,'trips_count')),
          'stop_times':int(meta(con,'stop_times_count')),'shape_points':int(meta(con,'shape_points_count'))},
          'ticketing':{'records':int(meta(con,'ticket_rows')),'role':'ridership demand analytics, not GPS traffic history'},
          'live_feed':'configured' if LIVE_KEY else 'not_configured'})
    finally: con.close()

@app.get('/api/stops')
def api_stops():
    q=request.args.get('q','').strip()
    if len(q)<2: return jsonify({'results':[]})
    con=db()
    try:
        rows=con.execute('''SELECT stop_id,stop_name,stop_lat,stop_lon FROM stops
            WHERE stop_name LIKE ? COLLATE NOCASE ORDER BY stop_name LIMIT 15''',(f'%{q}%',)).fetchall()
        return jsonify({'results':[dict(r) for r in rows]})
    finally: con.close()

@app.get('/api/plan')
@app.get('/api/journeys')
def api_plan():
    try:
        origin=request.args.get('origin_id','').strip(); dest=request.args.get('destination_id','').strip()
        departure_raw=request.args.get('departure','08:30').strip()
        selected_date=date.today()
        if 'T' in departure_raw:
            date_part, departure=departure_raw.split('T',1)
            selected_date=date.fromisoformat(date_part)
        else:
            departure=departure_raw
        h,m=map(int,departure.split(':')[:2]); departure_sec=h*3600+m*60
        # Validate that at least one GTFS service is active on the requested local date.
        con=db()
        try:
            weekday_col=['monday','tuesday','wednesday','thursday','friday','saturday','sunday'][selected_date.weekday()]
            yyyymmdd=selected_date.strftime('%Y%m%d')
            active=con.execute(f"SELECT COUNT(*) FROM service_calendar WHERE start_date<=? AND end_date>=? AND {weekday_col}=1",(yyyymmdd,yyyymmdd)).fetchone()[0]
        finally:
            con.close()
        if not active:
            return jsonify({'error':'No scheduled GTFS service is listed for this date. Choose a date within the published service calendar.'}),400
        walk_in=max(0,min(30,int(request.args.get('walk_in',5))))
        walk_out=max(0,min(30,int(request.args.get('walk_out',5))))
        data,status=plan_journeys(origin,dest,departure_sec,walk_in,walk_out)
        return jsonify(data),status
    except Exception as exc:
        app.logger.exception('Journey planning failed')
        return jsonify({'error':f'Journey planning failed: {type(exc).__name__}'}),500

@app.get('/api/demand')
def api_demand():
    hour=max(0,min(23,int(request.args.get('hour',8))))
    con=db()
    try:
        rows=con.execute('''SELECT route_short_name AS route,tickets,passengers,revenue
          FROM demand_route_hour WHERE local_hour=? ORDER BY tickets DESC LIMIT 12''',(hour,)).fetchall()
        return jsonify({'hour':hour,'source':'October 2026 ticket transactions','interpretation':'Demand proxy; not traffic speed or vehicle occupancy.','routes':[dict(r) for r in rows]})
    finally: con.close()

@app.get('/api/vehicles')
def api_vehicles(): return jsonify(live_vehicle_data())

@app.get('/api/docs')
def api_docs(): return render_template('api_docs.html',user=session.get('user_name'))

@app.route('/signup',methods=['GET','POST'])
def signup():
    if request.method=='POST':
        name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        if len(name)<2 or '@' not in email or len(password)<8:
            flash('Enter your name, a valid email and a password of at least 8 characters.','error')
        else:
            con=db()
            try:
                con.execute('CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,created_at TEXT NOT NULL)')
                con.execute('CREATE TABLE IF NOT EXISTS saved_journeys(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,origin_id TEXT NOT NULL,destination_id TEXT NOT NULL,origin_name TEXT NOT NULL,destination_name TEXT NOT NULL,departure TEXT NOT NULL,created_at TEXT NOT NULL)')
                con.execute('INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)',(name,email,generate_password_hash(password),datetime.now().isoformat(timespec='seconds'))); con.commit()
                user=con.execute('SELECT user_id,name FROM users WHERE email=?',(email,)).fetchone()
                session['user_id']=user['user_id']; session['user_name']=user['name']; flash('Your RoutePulse account is ready.','success')
                return redirect(url_for('demo'))
            except sqlite3.IntegrityError: flash('An account with that email already exists. Sign in instead.','error')
            finally: con.close()
    return render_template('auth.html',mode='signup',user=session.get('user_name'))

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        con=db()
        try:
            con.execute('CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,created_at TEXT NOT NULL)')
            user=con.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
            if user and check_password_hash(user['password_hash'],password):
                session['user_id']=user['user_id']; session['user_name']=user['name']; flash('Welcome back.','success')
                return redirect(request.args.get('next') or url_for('demo'))
            flash('Email or password is incorrect.','error')
        finally: con.close()
    return render_template('auth.html',mode='login',user=session.get('user_name'))

@app.get('/logout')
def logout(): session.clear(); flash('You have been signed out.','info'); return redirect(url_for('home'))

@app.post('/api/save-journey')
@login_required
def save_journey():
    data=request.get_json(silent=True) or {}
    con=db()
    try:
        con.execute('''CREATE TABLE IF NOT EXISTS saved_journeys(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,origin_id TEXT NOT NULL,destination_id TEXT NOT NULL,origin_name TEXT NOT NULL,destination_name TEXT NOT NULL,departure TEXT NOT NULL,created_at TEXT NOT NULL)''')
        con.execute('''INSERT INTO saved_journeys(user_id,origin_id,destination_id,origin_name,destination_name,departure,created_at)
          VALUES(?,?,?,?,?,?,?)''',(session['user_id'],str(data.get('origin_id','')),str(data.get('destination_id','')),str(data.get('origin_name','')),str(data.get('destination_name','')),str(data.get('departure','')),datetime.now().isoformat(timespec='seconds')))
        con.commit(); return jsonify({'saved':True})
    finally: con.close()

@app.get('/account')
@login_required
def account():
    con=db()
    try:
        con.execute('''CREATE TABLE IF NOT EXISTS saved_journeys(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,origin_id TEXT NOT NULL,destination_id TEXT NOT NULL,origin_name TEXT NOT NULL,destination_name TEXT NOT NULL,departure TEXT NOT NULL,created_at TEXT NOT NULL)''')
        rows=con.execute('SELECT * FROM saved_journeys WHERE user_id=? ORDER BY id DESC LIMIT 50',(session['user_id'],)).fetchall()
        return render_template('account.html',journeys=[dict(x) for x in rows],user=session.get('user_name'))
    finally: con.close()

if __name__=='__main__':
    print(f'RoutePulse database: {DB_PATH}')
    print(f'Live feed: {"configured" if LIVE_KEY else "not configured (add key to .env)"}')
    app.run(host=os.getenv('HOST','0.0.0.0'),port=int(os.getenv('PORT',5000)),debug=os.getenv('FLASK_DEBUG','0')=='1')
