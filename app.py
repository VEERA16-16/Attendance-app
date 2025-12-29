import sqlite3
import csv
import os
import io
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.secret_key = "supersecretkey"

ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    conn = sqlite3.connect("attendance.db")
    conn.row_factory = sqlite3.Row
    return conn

def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def decorated_view(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                return "Unauthorized", 403
            return f(*args, **kwargs)
        return decorated_view
    return decorator

@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        conn.close()

        if user:
            verified = check_password_hash(user["password_hash"], password)
            if verified:
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["role"] = user["role"]
                session["department"] = user["department"]
                if user["role"] == "admin":
                    return redirect(url_for("admin"))
                else:
                    return redirect(url_for("dashboard"))
            else:
                flash("Invalid credentials!", "danger")
        else:
            flash("Invalid credentials!", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# Admin Dashboard - shows attendance records
@app.route("/admin")
@login_required(role="admin")
def admin():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, a.date, s.roll_no, s.name, s.year, s.department, a.status, a.reason
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        ORDER BY a.date DESC
    """)
    records = cur.fetchall()
    conn.close()
    return render_template("admin.html", records=records)

# Edit Attendance Route
@app.route("/edit_attendance/<int:record_id>", methods=["GET", "POST"])
@login_required(role="admin")
def edit_attendance(record_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, a.student_id, a.date, a.status, a.reason, s.name, s.department
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.id = ?
    """, (record_id,))
    rec = cur.fetchone()
    if not rec:
        flash("Attendance record not found.", "danger")
        return redirect(url_for("admin"))

    if request.method == "POST":
        status = request.form.get("status")
        reason = request.form.get("reason", "")
        cur.execute("""
            UPDATE attendance SET status = ?, reason = ? WHERE id = ?
        """, (status, reason, record_id))
        conn.commit()
        conn.close()
        flash("Attendance updated successfully!", "success")
        return redirect(url_for("admin"))

    conn.close()
    return render_template("edit_attendance.html", rec=rec)

# Delete Attendance Route
@app.route("/delete_attendance/<int:record_id>", methods=["POST"])
@login_required(role="admin")
def delete_attendance(record_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM attendance WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()
    flash("Attendance record deleted.", "success")
    return redirect(url_for("admin"))

# Department Dashboard for attendance marking
@app.route("/dashboard", methods=["GET", "POST"])
@login_required(role="department")
def dashboard():
    dept = session["department"]
    if request.method == "POST":
        date_selected = request.form.get("date")
    else:
        date_selected = request.args.get("date", date.today().isoformat())

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM students WHERE department = ?", (dept,))
    students = cur.fetchall()

    attendance_map = {}
    if students and date_selected:
        placeholders = ','.join('?' for _ in students)
        params = [date_selected] + [s['id'] for s in students]
        query = f"SELECT student_id, status, reason FROM attendance WHERE date = ? AND student_id IN ({placeholders})"
        cur.execute(query, params)
        for row in cur.fetchall():
            attendance_map[row['student_id']] = {'status': row['status'], 'reason': row['reason']}

    # Handle POST attendance update
    if request.method == "POST" and date_selected:
        for student in students:
            student_id = student['id']
            status = request.form.get(f'status_{student_id}')
            reason = request.form.get(f'reason_{student_id}', '')
            if status:
                try:
                    cur.execute("""
                        INSERT INTO attendance (student_id, date, status, reason)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(student_id, date) DO UPDATE SET
                        status=excluded.status,
                        reason=excluded.reason
                    """, (student_id, date_selected, status, reason))
                except sqlite3.IntegrityError:
                    flash(f"⚠️ Error updating attendance for student id {student_id}.", "danger")
        conn.commit()
        flash("Attendance updated successfully!", "success")
        attendance_map.clear()
        cur.execute(query, params)
        for row in cur.fetchall():
            attendance_map[row['student_id']] = {'status': row['status'], 'reason': row['reason']}

    conn.close()
    return render_template("attendance.html", students=students, dept=dept, date_selected=date_selected, attendance_map=attendance_map)

# Add Student Route
@app.route("/add_student", methods=["GET", "POST"])
@login_required(role="department")
def add_student():
    dept = session["department"]
    if request.method == "POST":
        roll_no = request.form["roll_no"]
        name = request.form["name"]
        year = request.form["year"]
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO students (roll_no, name, year, department) VALUES (?, ?, ?, ?)",
                (roll_no, name, year, dept)
            )
            conn.commit()
            flash("Student added successfully!", "success")
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            flash("Roll No already exists! Use a unique Roll No.", "danger")
        finally:
            conn.close()
    return render_template("add_student.html", dept=dept)

# Manage Students Route
@app.route("/manage_students")
@login_required(role="department")
def manage_students():
    dept = session["department"]
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM students WHERE department = ?", (dept,))
    students = cur.fetchall()
    conn.close()
    return render_template("manage_students.html", students=students)

# Attendance Report Page with detailed lists and counts
@app.route("/report_page", methods=["GET"])
@login_required(role="admin")
def report_page():
    selected_date = request.args.get("date", date.today().isoformat())
    selected_dept = request.args.get("department", None)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT department FROM students")
    all_departments = [row['department'] for row in cur.fetchall()]

    params = []
    dept_filter = ""
    if selected_dept and selected_dept != "":
        dept_filter = "AND s.department = ?"
        params.append(selected_dept)

    cur.execute(f"SELECT COUNT(*) FROM students s WHERE 1=1 {dept_filter}", params)
    total_students = cur.fetchone()[0]

    cur.execute(
        f"""SELECT COUNT(*) FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.date = ? AND a.status = 'P' {dept_filter}""",
        [selected_date] + params)
    total_present = cur.fetchone()[0]

    cur.execute(
        f"""SELECT COUNT(*) FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.date = ? AND a.status = 'A' {dept_filter}""",
        [selected_date] + params)
    total_absent = cur.fetchone()[0]

    if selected_dept and selected_dept != "":
        cur.execute("SELECT roll_no, name, year, department FROM students WHERE department = ?", (selected_dept,))
        all_students_list = cur.fetchall()
    else:
        cur.execute("SELECT roll_no, name, year, department FROM students")
        all_students_list = cur.fetchall()

    cur.execute(f"""
        SELECT s.roll_no, s.name, s.year, s.department
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.date = ? AND a.status = 'P' {dept_filter}
    """, [selected_date] + params)
    present_students_list = cur.fetchall()

    cur.execute(f"""
        SELECT s.roll_no, s.name, s.year, s.department, a.reason
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.date = ? AND a.status = 'A' {dept_filter}
    """, [selected_date] + params)
    absent_students_list = cur.fetchall()

    conn.close()

    return render_template(
        "report-page.html",
        total_students=total_students,
        total_present=total_present,
        total_absent=total_absent,
        selected_date=selected_date,
        selected_dept=selected_dept,
        all_departments=all_departments,
        all_students_list=all_students_list,
        present_students_list=present_students_list,
        absent_students_list=absent_students_list
    )

# Import Students Route - CSV upload
@app.route('/import_students', methods=['GET', 'POST'])
@login_required(role='admin')
def import_students():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not allowed_file(file.filename):
            flash("Please upload a valid CSV file.", "danger")
            return redirect(request.url)
        filename = secure_filename(file.filename)
        os.makedirs("uploads", exist_ok=True)
        filepath = os.path.join("uploads", filename)
        file.save(filepath)
        inserted = 0
        with open(filepath, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            conn = get_db()
            cur = conn.cursor()
            for row in reader:
                try:
                    cur.execute(
                        "INSERT INTO students (roll_no, name, year, department) VALUES (?, ?, ?, ?)",
                        (row['roll_no'], row['name'], row['year'], row['department'])
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    pass
            conn.commit()
            conn.close()
        flash(f"Successfully imported {inserted} students!", "success")
        return redirect(url_for('admin'))
    return render_template('import_students.html')

# Export Attendance CSV download
@app.route("/export_attendance_csv")
@login_required(role="admin")
def export_attendance_csv():
    selected_date = request.args.get("date", date.today().isoformat())
    selected_dept = request.args.get("department", None)
    status_filter = request.args.get("status", None)

    conn = get_db()
    cur = conn.cursor()

    params = [selected_date]
    dept_filter = ""
    if selected_dept and selected_dept != "":
        dept_filter = "AND s.department = ?"
        params.append(selected_dept)

    status_clause = ""
    if status_filter == 'present':
        status_clause = "AND a.status = 'P'"
    elif status_filter == 'absent':
        status_clause = "AND a.status = 'A'"

    query = f"""
        SELECT s.roll_no, s.name, s.year, s.department, a.status, a.reason, a.date
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.date = ? {dept_filter} {status_clause}
        ORDER BY s.department, s.name
    """
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Roll No', 'Name', 'Year', 'Department', 'Status', 'Reason', 'Date'])
    for row in rows:
        status = 'Present' if row['status'] == 'P' else 'Absent'
        writer.writerow([row['roll_no'], row['name'], row['year'], row['department'], status, row['reason'] or '', row['date']])
    output.seek(0)

    return Response(output, mimetype='text/csv',
                    headers={"Content-Disposition": f"attachment;filename=attendance_{selected_date}_{status_filter or 'all'}.csv"})

if __name__ == "__main__":
    from models import init_db
    init_db()
    app.run(debug=True)
