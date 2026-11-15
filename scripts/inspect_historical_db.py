"""Inspect, but do not alter, a downloaded daily historical GPS SQLite database."""
import argparse, sqlite3
from pathlib import Path


def inspect(path: Path):
    uri = f'file:{path.resolve().as_posix()}?mode=ro'
    con = sqlite3.connect(uri, uri=True)
    try:
        print(f'\nDATABASE: {path.name}')
        tables = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        if not tables:
            print('No user tables found.'); return
        for (table,) in tables:
            cols = con.execute(f'PRAGMA table_info("{table.replace(chr(34), chr(34)*2)}")').fetchall()
            count = con.execute(f'SELECT COUNT(*) FROM "{table.replace(chr(34), chr(34)*2)}"').fetchone()[0]
            print(f'\nTable: {table} | rows: {count:,}')
            print('Columns: ' + ', '.join(f'{c[1]} ({c[2] or "unspecified"})' for c in cols))
            print('Sample:')
            for row in con.execute(f'SELECT * FROM "{table.replace(chr(34), chr(34)*2)}" LIMIT 2'):
                # Show only the first two records for schema diagnosis; do not export the table.
                print('  ' + repr(row)[:500])
    finally:
        con.close()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source',type=Path,help='SQLite .db file or directory containing daily .db files')
    ap.add_argument('--files',type=int,default=3,help='Maximum number of daily files to inspect (default: 3)')
    a=ap.parse_args()
    files=sorted(a.source.glob('*.db')) if a.source.is_dir() else [a.source]
    if not files:
        raise SystemExit(f'No .db files found at {a.source}')
    for path in files[:max(1,a.files)]: inspect(path)

if __name__=='__main__': main()
