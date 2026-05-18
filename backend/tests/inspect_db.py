"""Quick DB inspection script."""
import sqlite3, os
os.chdir(os.path.join(os.path.dirname(__file__), ".."))
conn = sqlite3.connect("atlas.db")
c = conn.cursor()

# List tables
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in c.fetchall()]
print(f"Tables ({len(tables)}): {tables}\n")

# Row counts
for t in tables:
    count = c.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
    print(f"  {t}: {count} rows")

# Sample data from key tables
for t in ["network_sites", "network_incidents", "vendor_contracts", "complaint_tickets", "network_kpis", "conversations", "messages", "agent_runs"]:
    if t in tables:
        rows = c.execute(f"SELECT * FROM [{t}] LIMIT 2").fetchall()
        cols = [desc[0] for desc in c.description]
        print(f"\n--- {t} (sample) ---")
        print(f"  Columns: {cols}")
        for r in rows:
            print(f"  {dict(zip(cols, r))}")

conn.close()
