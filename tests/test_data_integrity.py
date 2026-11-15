import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data' / 'routepulse.sqlite'

class DatasetIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(DB)

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def test_core_gtfs_counts(self):
        expected = {'stops': 6862, 'routes': 2574, 'trips': 80357,
                    'stop_times': 2737136, 'shape_points': 965607}
        for table, count in expected.items():
            with self.subTest(table=table):
                self.assertEqual(self.con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0], count)

    def test_all_stop_time_trips_exist(self):
        missing = self.con.execute('''SELECT COUNT(*) FROM stop_times s
            LEFT JOIN trips t ON t.trip_id=s.trip_id WHERE t.trip_id IS NULL''').fetchone()[0]
        self.assertEqual(missing, 0)

    def test_all_stop_time_stops_exist(self):
        missing = self.con.execute('''SELECT COUNT(*) FROM stop_times s
            LEFT JOIN stops p ON p.stop_id=s.stop_id WHERE p.stop_id IS NULL''').fetchone()[0]
        self.assertEqual(missing, 0)


    def test_calendar_and_agencies_loaded(self):
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM agencies').fetchone()[0], 2)
        calendar = self.con.execute("SELECT monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date FROM service_calendar WHERE service_id='1'").fetchone()
        self.assertIsNotNone(calendar)
        self.assertEqual(tuple(calendar[:7]), (1,1,1,1,1,1,1))

    def test_ticket_records_are_aggregated(self):
        expected = int(self.con.execute("SELECT value FROM metadata WHERE key='ticket_rows'").fetchone()[0])
        actual = self.con.execute('SELECT SUM(tickets) FROM demand_hour').fetchone()[0]
        self.assertEqual(actual, expected)
        self.assertGreater(self.con.execute('SELECT COUNT(*) FROM demand_route_hour').fetchone()[0], 0)
        self.assertGreater(self.con.execute('SELECT COUNT(*) FROM demand_od').fetchone()[0], 0)

    def test_sample_direct_journey_exists(self):
        rows = self.con.execute('''SELECT d.trip_id FROM stop_times d
            JOIN stop_times a ON a.trip_id=d.trip_id AND a.stop_id='2560' AND a.stop_sequence>d.stop_sequence
            WHERE d.stop_id='1025' AND d.departure_sec>=8*3600 LIMIT 1''').fetchall()
        self.assertTrue(rows)

if __name__ == '__main__':
    unittest.main()
