import sqlite3

def init_db():
    conn = sqlite3.connect("attendance.db")
    cur = conn.cursor()

    # ----------------- USERS TABLE -----------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        department TEXT
    )
    """)

    # ----------------- STUDENTS TABLE -----------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roll_no TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        year INTEGER NOT NULL,
        department TEXT NOT NULL
    )
    """)

    # ----------------- ATTENDANCE TABLE -----------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        status TEXT NOT NULL,
        reason TEXT,
        FOREIGN KEY(student_id) REFERENCES students(id),
        UNIQUE(student_id, date)  -- ✅ ensures one record per student per date
    )
    """)

    conn.commit()
    conn.close()
