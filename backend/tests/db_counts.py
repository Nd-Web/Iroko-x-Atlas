import sqlite3, os
os.chdir(os.path.join(os.path.dirname(__file__), ".."))
conn = sqlite3.connect("atlas.db")
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
for (t,) in c.fetchall():
    n = c.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
    print(f"{t}: {n} rows")
conn.close()
