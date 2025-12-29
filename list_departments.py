import sqlite3

# Connect to your database file
conn = sqlite3.connect("attendance.db")
cur = conn.cursor()

# Query distinct department names (trim removes spaces)
cur.execute("SELECT DISTINCT TRIM(department) FROM students ORDER BY department")
departments = [row[0] for row in cur.fetchall()]

print("Departments in the database:")
for dept in departments:
    print(f"'{dept}'")

conn.close()
