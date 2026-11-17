import os
import sqlite3
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("EMP_SECRET_KEY", "change-this-development-key")
DB = os.path.join(app.root_path, "emp.db")


# ---------- Database ----------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','examiner','student')),
        approved INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS exams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER NOT NULL,
        examiner_id INTEGER NOT NULL,
        slot_time TEXT NOT NULL,
        capacity INTEGER NOT NULL CHECK(capacity > 0),
        FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE,
        FOREIGN KEY(examiner_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'booked',
        UNIQUE(slot_id, student_id),
        FOREIGN KEY(slot_id) REFERENCES slots(id) ON DELETE CASCADE,
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER UNIQUE NOT NULL,
        marks REAL NOT NULL,
        feedback TEXT DEFAULT '',
        FOREIGN KEY(booking_id) REFERENCES bookings(id) ON DELETE CASCADE
    );
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS rubrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER NOT NULL,
        criterion TEXT NOT NULL,
        description TEXT,
        max_marks INTEGER NOT NULL,
        FOREIGN KEY (exam_id) REFERENCES exams(id)
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS system_settings (
        setting_name TEXT PRIMARY KEY,
        setting_value TEXT NOT NULL
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS examiner_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        examiner_id INTEGER NOT NULL,
        exam_id INTEGER NOT NULL,

        FOREIGN KEY (examiner_id) REFERENCES users(id),
        FOREIGN KEY (exam_id) REFERENCES exams(id),

        UNIQUE (examiner_id, exam_id)
    )
    """)
    # Default settings: both controls are open
    conn.execute("""
    INSERT OR IGNORE INTO system_settings
    (setting_name, setting_value)
    VALUES
    ('slot_creation_open', '1'),
    ('student_booking_open', '1')
    """)

    columns = [row[1] for row in conn.execute("PRAGMA table_info(users)")]

    if "active" not in columns:
        conn.execute("""
             ALTER TABLE users
             ADD COLUMN active INTEGER NOT NULL DEFAULT 1
        """)
    
    # Add examination date, time and booking window columns
    exam_columns = [
    row[1] for row in conn.execute("PRAGMA table_info(exams)")
    ]

    new_columns = {
    "exam_date": "TEXT",
    "exam_time": "TEXT",
    "booking_start": "TEXT",
    "booking_end": "TEXT"
    }
    for column, datatype in new_columns.items():
        exam_columns = [
        row[1] for row in conn.execute("PRAGMA table_info(exams)")
    ]
    if column not in exam_columns:
        conn.execute(
            f"ALTER TABLE exams ADD COLUMN {column} {datatype}"
        )

        
    admin_email = os.environ.get("EMP_ADMIN_EMAIL", "admin@emp.local")
    admin_password = os.environ.get("EMP_ADMIN_PASSWORD", "Admin@12345")
    existing = conn.execute("SELECT id FROM users WHERE email=?", (admin_email,)).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO users(name,email,password,role,approved) VALUES(?,?,?,?,1)",
            ("Administrator", admin_email, generate_password_hash(admin_password), "admin")
        )

    conn.commit()
    conn.close()
    

def setting_is_open(setting_name):
    setting = db().execute("""
        SELECT setting_value
        FROM system_settings
        WHERE setting_name = ?
    """, (setting_name,)).fetchone()
    return setting is not None and setting["setting_value"] == "1"    

#  Login and permissions 
def login_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("You are not allowed to open that page.")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator



@app.route("/")
def home():
    return redirect(url_for("dashboard") if session.get("user_id") else url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "student")
        if not name or not email or len(password) < 6 or role not in ("student", "examiner"):
            flash("Enter valid details. Password must be at least 6 characters.")
        else:
            try:
                db().execute(
                    "INSERT INTO users(name,email,password,role,approved) VALUES(?,?,?,?,?)",
                    (name, email, generate_password_hash(password), role, 1 if role == "student" else 0)
                )
                db().commit()
                flash("Registration successful. Examiner accounts need admin approval.")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That email is already registered.")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password"], password) and user["approved"]:
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
        flash("Login failed. Check your details or examiner approval status.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required()
def dashboard():
    role = session["role"]
    if role == "admin":
        pending = db().execute("SELECT id,name,email FROM users WHERE role='examiner' AND approved=0").fetchall()
        active_slots = db().execute("""SELECT COUNT(*) FROM slots""").fetchone()[0]
        courses = db().execute("SELECT * FROM courses ORDER BY code").fetchall()
        exams = db().execute("""SELECT exams.*, courses.code, courses.name AS course_name
                               FROM exams JOIN courses ON courses.id=exams.course_id
                               ORDER BY exams.id DESC""").fetchall()
        students = db().execute("SELECT COUNT(*) FROM users WHERE role='student'" ).fetchone()[0]
        examiners = db().execute("SELECT COUNT(*) FROM users WHERE role='examiner'").fetchone()[0]
        bookings = db().execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
        slot_creation_open = setting_is_open("slot_creation_open")
        student_booking_open = setting_is_open("student_booking_open")
        available_examiners = db().execute("""SELECT id, name, email
                                          FROM users
                                          WHERE role = 'examiner'
                                          AND approved = 1
                                          AND active = 1""").fetchall()
        assignments = db().execute("""SELECT examiner_assignments.id,
                                    users.name AS examiner_name,
                                    users.email,
                                    exams.title AS exam_title
                                    FROM examiner_assignments
                                    JOIN users
                                    ON examiner_assignments.examiner_id = users.id
                                    JOIN exams
                                    ON examiner_assignments.exam_id = exams.id
                                   ORDER BY examiner_assignments.id DESC
                                    """).fetchall()
        return render_template("admin.html", pending=pending, courses=courses, exams=exams, 
                               students=students, examiners=examiners, bookings=bookings, slot_creation_open=slot_creation_open,
    student_booking_open=student_booking_open,available_examiners=available_examiners,assignments=assignments,active_slots=active_slots)
    
    
    if role == "examiner":
        examiner_id = session["user_id"]
        # Get examinations assigned to this examiner
        exams = db().execute("""
            SELECT exams.id, exams.title, courses.code,
                   courses.name AS course_name
            FROM examiner_assignments
            JOIN exams
                ON exams.id = examiner_assignments.exam_id
            JOIN courses
                ON courses.id = exams.course_id
            WHERE examiner_assignments.examiner_id = ?
            ORDER BY exams.title
        """, (examiner_id,)).fetchall()
        # Total assigned examinations
        assigned_examinations = db().execute("""
    SELECT COUNT(*)
    FROM examiner_assignments
    WHERE examiner_id = ?
""", (session["user_id"],)).fetchone()[0]


        # Total slots created by examiner
        created_slots = db().execute("""
    SELECT COUNT(*)
    FROM slots
    WHERE examiner_id = ?
""", (session["user_id"],)).fetchone()[0]


        # Total students booked in examiner's slots
        students_booked = db().execute("""
    SELECT COUNT(*)
    FROM bookings
    JOIN slots ON slots.id = bookings.slot_id
    WHERE slots.examiner_id = ?
    AND bookings.status = 'booked'
""", (session["user_id"],)).fetchone()[0]


        # Total pending evaluations
        pending_evaluations = db().execute("""
    SELECT COUNT(*)
    FROM bookings
    JOIN slots ON slots.id = bookings.slot_id
    LEFT JOIN results ON results.booking_id = bookings.id
    WHERE slots.examiner_id = ?
    AND bookings.status = 'booked'
    AND results.booking_id IS NULL
    """, (session["user_id"],)).fetchone()[0]
        # Get slots created by this examiner
        slots = db().execute("""
            SELECT slots.*,
                    exams.title AS exam_title,
                    COUNT(CASE
                    WHEN bookings.status = 'booked'
                    THEN bookings.id
                    END) AS booked
                    FROM slots
                    JOIN exams
                    ON exams.id = slots.exam_id
                    LEFT JOIN bookings
                    ON bookings.slot_id = slots.id
                    WHERE slots.examiner_id = ?
                    GROUP BY slots.id
                    ORDER BY slots.slot_time
                    """, (examiner_id,)).fetchall()
        slot_creation_open = setting_is_open("slot_creation_open")
        return render_template(
            "examiner.html",
            slots=slots,
            exams=exams,
            slot_creation_open=slot_creation_open,
            assigned_examinations=assigned_examinations,
            created_slots=created_slots,
            students_booked=students_booked,
            pending_evaluations=pending_evaluations
        )

    # Check whether admin has enabled student booking
    booking_open = setting_is_open("student_booking_open")

    # Get future examination slots
    slots = db().execute("""
    SELECT
        slots.*,
        exams.title,
        exams.booking_start,
        exams.booking_end,
        courses.code,
        users.name AS examiner_name,

        (SELECT COUNT(*)
         FROM bookings
         WHERE bookings.slot_id = slots.id
         AND status = 'booked') AS booked

    FROM slots
    JOIN exams ON exams.id = slots.exam_id
    JOIN courses ON courses.id = exams.course_id
    JOIN users ON users.id = slots.examiner_id

    WHERE datetime(slots.slot_time) > datetime('now', 'localtime')

    ORDER BY slots.slot_time

""").fetchall()

    # 1. Available examination slots
    available_slots = db().execute("""
    SELECT COUNT(*)
    FROM slots

    WHERE datetime(slots.slot_time) > datetime('now', 'localtime')

    AND (
        SELECT COUNT(*)
        FROM bookings
        WHERE bookings.slot_id = slots.id
        AND bookings.status = 'booked'
    ) < slots.capacity

""").fetchone()[0]


    # 2. Available examinations
    available_examinations = db().execute("""
    SELECT COUNT(DISTINCT exams.id)
    FROM exams

    JOIN slots ON slots.exam_id = exams.id

    WHERE exams.exam_date IS NOT NULL
    AND exams.exam_time IS NOT NULL

    AND datetime(exams.exam_date || ' ' || exams.exam_time)
        > datetime('now', 'localtime')

    AND datetime(slots.slot_time)
        > datetime('now', 'localtime')

    AND (
        SELECT COUNT(*)
        FROM bookings
        WHERE bookings.slot_id = slots.id
        AND bookings.status = 'booked'
    ) < slots.capacity
""").fetchone()[0]


    # If admin has closed booking, no slots/examinations are currently bookable
    if not booking_open:
       available_slots = 0
       available_examinations = 0


    # 3. Upcoming examinations booked by this student
    upcoming_examinations = db().execute("""
    SELECT COUNT(DISTINCT exams.id)

    FROM bookings

    JOIN slots ON slots.id = bookings.slot_id
    JOIN exams ON exams.id = slots.exam_id

    WHERE bookings.student_id = ?
    AND bookings.status = 'booked'
    AND datetime(slots.slot_time) > datetime('now', 'localtime')
    """, (session["user_id"],)).fetchone()[0]


    # 4. Total active bookings of this student
    booked_slots = db().execute("""
    SELECT COUNT(*)
    FROM bookings

    WHERE student_id = ?
    AND status = 'booked'
    """, (session["user_id"],)).fetchone()[0]


    # 5. Published results
    published_results = db().execute("""
    SELECT COUNT(*)

    FROM results

    JOIN bookings ON bookings.id = results.booking_id

    WHERE bookings.student_id = ?
    """, (session["user_id"],)).fetchone()[0]


# Get this student's booking history and results
    bookings = db().execute("""
    SELECT
        bookings.id,
        bookings.status,
        exams.title,
        slots.slot_time,
        results.marks,
        results.feedback

    FROM bookings

    JOIN slots ON slots.id = bookings.slot_id
    JOIN exams ON exams.id = slots.exam_id

    LEFT JOIN results ON results.booking_id = bookings.id

    WHERE bookings.student_id = ?

    ORDER BY bookings.id DESC
    """, (session["user_id"],)).fetchall()


    return render_template("student.html",slots=slots,bookings=bookings,now=datetime.now(),
                           available_examinations=available_examinations,
                            available_slots=available_slots,
                           upcoming_examinations=upcoming_examinations,
                          booked_slots=booked_slots,
                          published_results=published_results,
                          booking_open=booking_open
                          )


# ---------- Admin ----------
@app.route("/course", methods=["GET","POST"])
@login_required("admin")
def add_course():
    code, name = request.form.get("code", "").strip().upper(), request.form.get("name", "").strip()
    if code and name:
        try:
            db().execute("INSERT INTO courses(code,name) VALUES(?,?)", (code, name))
            db().commit()
            flash("Course added.")
        except sqlite3.IntegrityError:
            flash("Course code already exists.")
    else:
        flash("Enter both course code and name.")
    return redirect(url_for("dashboard"))

@app.route("/admin/slots")
@login_required("admin")
def slots():

    slots = db().execute("""
        SELECT
            slots.id,
            slots.slot_time,
            slots.capacity,
            exams.title,
            courses.code,
            users.name AS examiner_name,
            (
                SELECT COUNT(*)
                FROM bookings
                WHERE bookings.slot_id = slots.id
                AND bookings.status = 'booked'
            ) AS booked
        FROM slots
        JOIN exams ON exams.id = slots.exam_id
        JOIN courses ON courses.id = exams.course_id
        JOIN users ON users.id = slots.examiner_id
        ORDER BY slots.slot_time
    """).fetchall()
    return render_template("slots_page.html", slots=slots)

@app.route("/admin/courses")
@login_required("admin")
def courses_page():
    conn = db()

    courses = conn.execute(
        "SELECT * FROM courses"
    ).fetchall()
    return render_template("courses.html", courses=courses)

@app.route("/admin/examinations")
@login_required("admin")
def examinations_page():
    conn = db()
    exams = conn.execute("""
        SELECT exams.*, courses.code, courses.name AS course_name
        FROM exams
        JOIN courses ON exams.course_id = courses.id
    """).fetchall()
    return render_template("examinations.html", exams=exams)

@app.route("/activate/<int:user_id>", methods=["POST"])
@login_required("admin")
def activate_examiner(user_id):
    db().execute("""
        UPDATE users
        SET active = 1
        WHERE id = ? AND role = 'examiner' AND approved = 1
    """, (user_id,))
    db().commit()
    flash("Examiner activated successfully.")
    return redirect(url_for("examiners_page"))

@app.route("/deactivate/<int:user_id>", methods=["POST"])
@login_required("admin")
def deactivate_examiner(user_id):
    db().execute("""
        UPDATE users
        SET active = 0
        WHERE id = ? AND role = 'examiner'
    """, (user_id,))
    db().commit()
    flash("Examiner deactivated successfully.")
    return redirect(url_for("examiners_page"))
    
@app.route("/admin/students")
@login_required("admin")
def students_page():
    conn = db()
    students = conn.execute("""
        SELECT * FROM users
        WHERE role = 'student'
    """).fetchall()
    return render_template("students.html", students=students)


@app.route("/admin/exam/<int:exam_id>/booking-window", methods=["POST"])
@login_required("admin")
def set_booking_window(exam_id):

    booking_start = request.form.get("booking_start", "").strip()
    booking_end = request.form.get("booking_end", "").strip()

    try:
        start = datetime.strptime(
            booking_start, "%Y-%m-%dT%H:%M"
        )
        end = datetime.strptime(
            booking_end, "%Y-%m-%dT%H:%M"
        )

        if end <= start:
            flash("Booking closing time must be after opening time.")
            return redirect(url_for("dashboard"))

        exam = db().execute(
            "SELECT id FROM exams WHERE id=?",
            (exam_id,)
        ).fetchone()

        if not exam:
            flash("Examination not found.")
            return redirect(url_for("dashboard"))

        db().execute("""
            UPDATE exams
            SET booking_start=?, booking_end=?
            WHERE id=?
        """, (booking_start, booking_end, exam_id))

        db().commit()
        flash("Booking timeline updated successfully.")

    except ValueError:
        flash("Please enter valid booking start and closing dates.")

    return redirect(url_for("dashboard"))

@app.route("/admin/bookings")
@login_required("admin")
def bookings_page():
    conn = db()

    bookings = conn.execute("""
        SELECT
            bookings.id,
            bookings.status,
            users.name AS student_name,
            users.email AS student_email,
            exams.title AS exam_title,
            slots.slot_time
        FROM bookings
        JOIN users ON bookings.student_id = users.id
        JOIN slots ON bookings.slot_id = slots.id
        JOIN exams ON slots.exam_id = exams.id
        ORDER BY bookings.id DESC
    """).fetchall()

    return render_template("bookings.html", bookings=bookings)

@app.route("/admin/toggle-slot-creation", methods=["POST"])
@login_required("admin")
def toggle_slot_creation():

    enabled = request.form.get("enabled")

    if enabled not in ("0", "1"):
        flash("Invalid slot creation setting.")
        return redirect(url_for("dashboard"))

    db().execute("""
        UPDATE system_settings
        SET setting_value = ?
        WHERE setting_name = 'slot_creation_open'
    """, (enabled,))

    db().commit()

    flash("Slot creation setting updated successfully.")

    return redirect(url_for("dashboard"))

@app.route("/admin/toggle-student-booking", methods=["POST"])
@login_required("admin")
def toggle_student_booking():

    enabled = request.form.get("enabled")

    if enabled not in ("0", "1"):
        flash("Invalid student booking setting.")
        return redirect(url_for("dashboard"))

    db().execute("""
        UPDATE system_settings
        SET setting_value = ?
        WHERE setting_name = 'student_booking_open'
    """, (enabled,))

    db().commit()

    flash("Student booking setting updated successfully.")

    return redirect(url_for("dashboard"))


@app.route("/admin/assign-examiner", methods=["POST"])
@login_required("admin")
def assign_examiner():

    examiner_id = request.form.get("examiner_id")
    exam_id = request.form.get("exam_id")

    examiner = db().execute("""
        SELECT id FROM users
        WHERE id = ?
        AND role = 'examiner'
        AND approved = 1
        AND active = 1
    """, (examiner_id,)).fetchone()

    exam = db().execute("""
        SELECT id FROM exams WHERE id = ?
    """, (exam_id,)).fetchone()

    if not examiner or not exam:
        flash("Invalid examiner or examination.")
        return redirect(url_for("dashboard"))

    try:
        db().execute("""
            INSERT INTO examiner_assignments
            (examiner_id, exam_id)
            VALUES (?, ?)
        """, (examiner_id, exam_id))

        db().commit()
        flash("Examination assigned successfully.")

    except sqlite3.IntegrityError:
        flash("This examination is already assigned to this examiner.")

    return redirect(url_for("dashboard"))

@app.route("/admin/remove-assignment/<int:assignment_id>", methods=["POST"])
@login_required("admin")
def remove_assignment(assignment_id):

    db().execute("""
        DELETE FROM examiner_assignments
        WHERE id = ?
    """, (assignment_id,))

    db().commit()

    flash("Examiner assignment removed successfully.")

    return redirect(url_for("dashboard"))

@app.route("/admin/pending-approvals")
@login_required("admin")
def pending_approvals_page():
    conn = db()

    pending = conn.execute("""
        SELECT id, name, email
        FROM users
        WHERE role = 'examiner' AND approved = 0
        ORDER BY id DESC
    """).fetchall()

    return render_template("pending_approvals.html", pending=pending)

@app.route("/admin/examiners")
@login_required("admin")
def examiners_page():
    conn = db()

    examiners = conn.execute("""
        SELECT id, name, email, approved, active
        FROM users
        WHERE role = 'examiner'
    """).fetchall()

    return render_template("examiners.html", examiners=examiners)

@app.route("/exam", methods=["POST"])
@login_required("admin")
def add_exam():
    try:
        db().execute("INSERT INTO exams(course_id,title,description) VALUES(?,?,?)",
                     (int(request.form["course_id"]), request.form["title"].strip(),
                      request.form.get("description", "").strip()))
        db().commit()
        flash("Examination added.")
    except (ValueError, KeyError, sqlite3.IntegrityError):
        flash("Could not add examination. Check the course and details.")
    return redirect(url_for("dashboard"))


@app.route("/approve/<int:user_id>", methods=["POST"])
@login_required("admin")
def approve_examiner(user_id):
    db().execute("UPDATE users SET approved=1 WHERE id=? AND role='examiner'", (user_id,))
    db().commit()
    flash("Examiner approved if the account exists.")
    return redirect(url_for("dashboard"))

# Edit Examination
@app.route("/exam/<int:exam_id>/edit", methods=["GET", "POST"])
@login_required("admin")
def edit_exam(exam_id):

    conn = db()

    exam = conn.execute(
        "SELECT * FROM exams WHERE id=?", (exam_id,)
    ).fetchone()

    if not exam:
        flash("Examination not found.")
        return redirect(url_for("dashboard"))

    courses = conn.execute(
        "SELECT * FROM courses ORDER BY code"
    ).fetchall()

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()

        exam_date = request.form.get("exam_date", "").strip()
        exam_time = request.form.get("exam_time", "").strip()

        booking_start = request.form.get("booking_start", "").strip()
        booking_end = request.form.get("booking_end", "").strip()

        try:
            course_id = int(request.form["course_id"])

            if not title or not conn.execute(
                "SELECT id FROM courses WHERE id=?", (course_id,)
            ).fetchone():
                raise ValueError

            # Validate booking dates
            start = datetime.strptime(booking_start, "%Y-%m-%dT%H:%M")
            end = datetime.strptime(booking_end, "%Y-%m-%dT%H:%M")

            if end <= start:
                raise ValueError

            # Get rubric values from HTML
            criteria = request.form.getlist("rubric_criteria[]")
            descriptions = request.form.getlist("rubric_descriptions[]")
            marks = request.form.getlist("rubric_marks[]")

            if not (len(criteria) == len(descriptions) == len(marks)):
                raise ValueError

            rubric_data = []

            for criterion, desc, mark in zip(criteria, descriptions, marks):

                criterion = criterion.strip()
                desc = desc.strip()
                mark = mark.strip()

                # Ignore completely empty rubric rows
                if not criterion and not desc and not mark:
                    continue

                if not criterion or not mark:
                    raise ValueError

                mark = int(mark)

                if mark <= 0:
                    raise ValueError

                rubric_data.append((criterion, desc, mark))

            # Update examination details
            conn.execute("""
                UPDATE exams
                SET course_id=?, title=?, description=?,
                    exam_date=?, exam_time=?,
                    booking_start=?, booking_end=?
                WHERE id=?
            """, (
                course_id, title, description,
                exam_date, exam_time,
                booking_start, booking_end,
                exam_id
            ))

            # Replace old rubrics with updated rubrics
            conn.execute(
                "DELETE FROM rubrics WHERE exam_id=?",
                (exam_id,)
            )

            for criterion, desc, mark in rubric_data:
                conn.execute("""
                    INSERT INTO rubrics
                    (exam_id, criterion, description, max_marks)
                    VALUES (?, ?, ?, ?)
                """, (exam_id, criterion, desc, mark))

            conn.commit()

            flash("Examination and rubrics updated successfully.")
            return redirect(url_for("dashboard"))

        except (ValueError, KeyError):
            conn.rollback()
            flash("Please enter valid examination and rubric details.")

    # Load existing rubrics
    rubrics = conn.execute("""
        SELECT * FROM rubrics
        WHERE exam_id=?
        ORDER BY id
    """, (exam_id,)).fetchall()

    return render_template(
        "edit_exam.html",
        exam=exam,
        courses=courses,
        rubrics=rubrics
    )

# Delete Examination
@app.route("/exam/<int:exam_id>/delete", methods=["POST"])
@login_required("admin")
def delete_exam(exam_id):
    conn = db()

    conn.execute("DELETE FROM exams WHERE id=?", (exam_id,))
    conn.commit()

    flash("Examination deleted successfully.")
    return redirect(url_for("dashboard"))

# Edit Course
@app.route("/course/<int:course_id>/edit", methods=["GET", "POST"])
@login_required("admin")
def edit_course(course_id):
    conn = db()

    course = conn.execute(
        "SELECT * FROM courses WHERE id=?", (course_id,)
    ).fetchone()

    if not course:
        flash("Course not found.")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        name = request.form.get("name", "").strip()

        if not code or not name:
            flash("Please enter both course code and name.")
        else:
            try:
                conn.execute(
                    "UPDATE courses SET code=?, name=? WHERE id=?",
                    (code, name, course_id)
                )
                conn.commit()
                flash("Course updated successfully.")
                return redirect(url_for("dashboard"))

            except sqlite3.IntegrityError:
                flash("This course code may already exist.")

    return render_template("edit_course.html", course=course)


# Delete Course
@app.route("/course/<int:course_id>/delete", methods=["POST"])
@login_required("admin")
def delete_course(course_id):
    conn = db()

    course = conn.execute(
        "SELECT * FROM courses WHERE id=?", (course_id,)
    ).fetchone()

    if not course:
        flash("Course not found.")
        return redirect(url_for("dashboard"))

    # Prevent deletion if examinations are linked to this course
    exams = conn.execute(
        "SELECT id FROM exams WHERE course_id=?", (course_id,)
    ).fetchone()

    if exams:
        flash("Cannot delete this course. Delete its examinations first.")
        return redirect(url_for("dashboard"))

    conn.execute("DELETE FROM courses WHERE id=?", (course_id,))
    conn.commit()

    flash("Course deleted successfully.")
    return redirect(url_for("dashboard"))

# ---------- Examiner ----------




@app.route("/slot/<int:exam_id>", methods=["GET", "POST"])
@login_required("examiner")
def add_slot(exam_id):

    # Check whether this examiner is assigned to this exam
    assignment = db().execute("""
        SELECT exams.id, exams.title
        FROM examiner_assignments
        JOIN exams ON exams.id = examiner_assignments.exam_id
        WHERE examiner_assignments.examiner_id = ?
        AND exams.id = ?
    """, (session["user_id"], exam_id)).fetchone()

    if not assignment:
        flash("You are not assigned to this examination.")
        return redirect(url_for("dashboard"))

    if not setting_is_open("slot_creation_open"):
        flash("Slot creation is currently closed by admin.")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        try:
            capacity = int(request.form["capacity"])
            slot_time = request.form["slot_time"].strip()

            if capacity < 1:
                raise ValueError

            datetime.strptime(slot_time, "%Y-%m-%dT%H:%M")

            db().execute("""
                INSERT INTO slots
                (exam_id, examiner_id, slot_time, capacity)
                VALUES (?, ?, ?, ?)
            """, (exam_id, session["user_id"], slot_time, capacity))

            db().commit()
            flash("Slot created successfully!")
            return redirect(url_for("dashboard"))

        except (ValueError, KeyError, sqlite3.IntegrityError):
            db().rollback()
            flash("Please enter a valid date, time and capacity.")

    return render_template(
        "create_slot.html",
        exam=assignment
    )




@app.route("/slot/<int:slot_id>/students")
@login_required("examiner")
def slot_students(slot_id):
    slot = db().execute("SELECT * FROM slots WHERE id=? AND examiner_id=?",
                        (slot_id, session["user_id"])).fetchone()
    if not slot:
        flash("Slot not found or not assigned to you.")
        return redirect(url_for("dashboard"))
    students = db().execute("""SELECT bookings.id AS booking_id, users.name, users.email,
                              bookings.status, results.marks, results.feedback
                              FROM bookings JOIN users ON users.id=bookings.student_id
                              LEFT JOIN results ON results.booking_id=bookings.id
                              WHERE bookings.slot_id=? ORDER BY users.name""", (slot_id,)).fetchall()
    return render_template("slot_students.html", slot=slot, students=students)


@app.route("/evaluate/<int:booking_id>", methods=["POST"])
@login_required("examiner")
def evaluate(booking_id):
    booking = db().execute("""SELECT bookings.id FROM bookings
                            JOIN slots ON slots.id=bookings.slot_id
                            WHERE bookings.id=? AND slots.examiner_id=? AND bookings.status='booked'""",
                           (booking_id, session["user_id"])).fetchone()
    try:
        marks = float(request.form["marks"])
        feedback = request.form.get("feedback", "").strip()
        if not booking or marks < 0 or marks > 100:
            raise ValueError
        db().execute("""INSERT INTO results(booking_id,marks,feedback) VALUES(?,?,?)
                       ON CONFLICT(booking_id) DO UPDATE SET marks=excluded.marks, feedback=excluded.feedback""",
                     (booking_id, marks, feedback))
        db().commit()
        flash("Result saved.")
    except (ValueError, KeyError):
        flash("Evaluation failed. Marks must be between 0 and 100.")
    return redirect(url_for("slot_students", slot_id=db().execute(
        "SELECT slot_id FROM bookings WHERE id=?", (booking_id,)).fetchone()["slot_id"]))


# ---------- Student ----------


@app.route("/book/<int:slot_id>", methods=["POST"])
@login_required("student")
def book_slot(slot_id):

    conn = db()

    # Check whether admin has enabled student booking
    if not setting_is_open("student_booking_open"):
        flash("Student booking is currently closed by admin.")
        return redirect(url_for("dashboard"))

    # Get slot and its examination booking dates
    slot = conn.execute("""
        SELECT
            slots.*,
            exams.booking_start,
            exams.booking_end
        FROM slots
        JOIN exams ON exams.id = slots.exam_id
        WHERE slots.id = ?
    """, (slot_id,)).fetchone()

    if not slot:
        flash("Slot not found.")
        return redirect(url_for("dashboard"))

    now = datetime.now()

    # Check whether booking dates are configured
    if not slot["booking_start"] or not slot["booking_end"]:
        flash("Booking dates have not been configured for this examination.")
        return redirect(url_for("dashboard"))

    # Check booking period
    try:
        booking_start = datetime.strptime(
            slot["booking_start"], "%Y-%m-%dT%H:%M"
        )

        booking_end = datetime.strptime(
            slot["booking_end"], "%Y-%m-%dT%H:%M"
        )

        slot_time = datetime.strptime(
            slot["slot_time"], "%Y-%m-%dT%H:%M"
        )

    except ValueError:
        flash("Invalid examination booking dates.")
        return redirect(url_for("dashboard"))

    if now < booking_start:
        flash("Booking has not started yet.")

    elif now > booking_end:
        flash("The booking deadline has passed.")

    elif slot_time <= now:
        flash("This examination slot has already passed.")

    else:

        # Check whether this student already has a booking
        existing = conn.execute("""
            SELECT id, status
            FROM bookings
            WHERE slot_id = ?
            AND student_id = ?
        """, (slot_id, session["user_id"])).fetchone()

        # Do not allow duplicate active bookings
        if existing and existing["status"] == "booked":
            flash("You have already booked this slot.")

        else:

            # Count currently booked students
            count = conn.execute("""
                SELECT COUNT(*)
                FROM bookings
                WHERE slot_id = ?
                AND status = 'booked'
            """, (slot_id,)).fetchone()[0]

            if count >= slot["capacity"]:
                flash("This slot is full.")

            else:
                try:

                    if existing:
                        # Reuse the cancelled booking record
                        conn.execute("""
                            UPDATE bookings
                            SET status = 'booked'
                            WHERE id = ?
                        """, (existing["id"],))

                    else:
                        # Create a new booking
                        conn.execute("""
                            INSERT INTO bookings
                            (slot_id, student_id, status)
                            VALUES (?, ?, 'booked')
                        """, (slot_id, session["user_id"]))

                    conn.commit()
                    flash("Slot booked successfully!")

                except sqlite3.IntegrityError:
                    conn.rollback()
                    flash("Booking could not be completed.")

    return redirect(url_for("dashboard"))




@app.route("/cancel/<int:booking_id>", methods=["POST"])
@login_required("student")
def cancel_booking(booking_id):
    cur = db().execute("""UPDATE bookings SET status='cancelled'
                         WHERE id=? AND student_id=? AND status='booked'""",
                       (booking_id, session["user_id"]))
    db().commit()
    flash("Booking cancelled." if cur.rowcount else "Active booking not found.")
    return redirect(url_for("dashboard"))


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
