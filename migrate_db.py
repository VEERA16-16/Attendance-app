import sqlite3
from werkzeug.security import generate_password_hash

# Connect to your existing database
conn = sqlite3.connect("attendance.db")
cur = conn.cursor()

print("🔄 Running migration...")

# 1. Ensure students table exists correctly
cur.execute("""
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll_no TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    year INTEGER NOT NULL,
    department TEXT NOT NULL
)
""")

# 2. Ensure attendance table exists with UNIQUE(student_id, date)
cur.execute("""
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT,
    UNIQUE(student_id, date),
    FOREIGN KEY(student_id) REFERENCES students(id)
)
""")

# 3. Ensure users table exists
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    department TEXT
)
""")

# 4. Insert default users (Admin + Departments)
default_users = [
    ("admin", "Admin@123", "admin", None),
    ("cse", "CSE@123", "department", "CSE"),
    ("ece", "ECE@123", "department", "ECE"),
    ("it", "IT@123", "department", "IT"),
    ("eee", "EEE@123", "department", "EEE"),
    ("mech", "MECH@123", "department", "MECH"),
    ("civil", "CIVIL@123", "department", "CIVIL"),
    ("aids", "AI&DS@123", "department", "AI&DS"),

]

for username, password, role, dept in default_users:
    password_hash = generate_password_hash(password)
    try:
        cur.execute(
            "INSERT INTO users (username, password_hash, role, department) VALUES (?, ?, ?, ?)",
            (username, password_hash, role, dept),
        )
        print(f"✅ User created: {username}")
    except sqlite3.IntegrityError:
        print(f"⚠️ User already exists: {username}")

# Commit and close
conn.commit()
conn.close()
print("🎉 Migration completed successfully.")
