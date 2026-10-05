from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import Error
from datetime import datetime

from config import DB_CONFIG

app = Flask(__name__)
app.secret_key = "fitness-log-secret-key-change-me"


# -----------------------------
# Database helpers
# -----------------------------
def get_db():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        raise RuntimeError(f"MySQL connection error: {e}") from e


def init_database():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL UNIQUE,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS fitness_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            activity_name VARCHAR(100) NOT NULL,
            exercise_type VARCHAR(50) NOT NULL,
            duration_minutes INT NOT NULL,
            calories_burned DECIMAL(10,2) NOT NULL DEFAULT 0,
            log_date DATE NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )

    conn.commit()
    cursor.close()
    conn.close()


# -----------------------------
# Auth decorator
# -----------------------------
def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped


# -----------------------------
# Core routes
# -----------------------------
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not email or not password:
            flash("Please complete all fields.", "danger")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM users WHERE username = %s OR email = %s",
            (username, email),
        )
        existing = cursor.fetchone()

        if existing:
            flash("Username or email already exists.", "warning")
            cursor.close()
            conn.close()
            return render_template("register.html")

        password_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, password_hash),
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        login_value = request.form.get("login_value", "").strip()
        password = request.form.get("password", "")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, email, password_hash FROM users WHERE username = %s OR email = %s LIMIT 1",
            (login_value, login_value),
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user[3], password):
            session["user_id"] = user[0]
            session["username"] = user[1]
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username/email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(duration_minutes), 0), COALESCE(ROUND(AVG(calories_burned), 2), 0)
        FROM fitness_logs
        WHERE user_id = %s
        """,
        (user_id,),
    )
    total_logs, total_duration, avg_calories = cursor.fetchone()

    cursor.execute(
        """
        SELECT activity_name, exercise_type, duration_minutes, calories_burned, log_date
        FROM fitness_logs
        WHERE user_id = %s
        ORDER BY log_date DESC, created_at DESC
        LIMIT 5
        """,
        (user_id,),
    )
    recent_logs = cursor.fetchall()

    cursor.execute(
        """
        SELECT DATE(log_date) AS workout_day,
               SUM(duration_minutes) AS total_duration,
               SUM(calories_burned) AS total_calories
        FROM fitness_logs
        WHERE user_id = %s AND log_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        GROUP BY DATE(log_date)
        ORDER BY DATE(log_date) ASC
        """,
        (user_id,),
    )
    weekly_data = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "dashboard.html",
        total_logs=total_logs,
        total_duration=total_duration,
        avg_calories=avg_calories,
        recent_logs=recent_logs,
        weekly_data=weekly_data,
    )


@app.route("/logs")
@login_required
def logs():
    user_id = session["user_id"]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, activity_name, exercise_type, duration_minutes, calories_burned, log_date, notes
        FROM fitness_logs
        WHERE user_id = %s
        ORDER BY log_date DESC, created_at DESC
        """,
        (user_id,),
    )
    records = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("logs.html", records=records)


@app.route("/logs/new", methods=["GET", "POST"])
@login_required
def add_log():
    if request.method == "POST":
        activity_name = request.form.get("activity_name", "").strip()
        exercise_type = request.form.get("exercise_type", "").strip()
        duration_minutes = request.form.get("duration_minutes", "0").strip()
        calories_burned = request.form.get("calories_burned", "0").strip()
        log_date = request.form.get("log_date") or datetime.today().strftime("%Y-%m-%d")
        notes = request.form.get("notes", "").strip()

        if not activity_name or not exercise_type:
            flash("Activity name and exercise type are required.", "danger")
            return render_template("add_log.html")

        try:
            duration_minutes = int(duration_minutes)
            calories_burned = float(calories_burned)
        except ValueError:
            flash("Duration and calories must be valid numbers.", "danger")
            return render_template("add_log.html")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO fitness_logs (user_id, activity_name, exercise_type, duration_minutes, calories_burned, log_date, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (session["user_id"], activity_name, exercise_type, duration_minutes, calories_burned, log_date, notes),
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash("Fitness log added successfully.", "success")
        return redirect(url_for("logs"))

    return render_template("add_log.html")


@app.route("/logs/<int:log_id>/edit", methods=["GET", "POST"])
@login_required
def edit_log(log_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, activity_name, exercise_type, duration_minutes, calories_burned, log_date, notes FROM fitness_logs WHERE id = %s AND user_id = %s",
        (log_id, session["user_id"]),
    )
    log = cursor.fetchone()

    if not log:
        flash("Log not found.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for("logs"))

    if request.method == "POST":
        activity_name = request.form.get("activity_name", "").strip()
        exercise_type = request.form.get("exercise_type", "").strip()
        duration_minutes = request.form.get("duration_minutes", "0").strip()
        calories_burned = request.form.get("calories_burned", "0").strip()
        log_date = request.form.get("log_date") or str(log[5])
        notes = request.form.get("notes", "").strip()

        if not activity_name or not exercise_type:
            flash("Activity name and exercise type are required.", "danger")
            return render_template("add_log.html", log=log)

        try:
            duration_minutes = int(duration_minutes)
            calories_burned = float(calories_burned)
        except ValueError:
            flash("Duration and calories must be valid numbers.", "danger")
            return render_template("add_log.html", log=log)

        cursor.execute(
            """
            UPDATE fitness_logs
            SET activity_name = %s,
                exercise_type = %s,
                duration_minutes = %s,
                calories_burned = %s,
                log_date = %s,
                notes = %s
            WHERE id = %s AND user_id = %s
            """,
            (activity_name, exercise_type, duration_minutes, calories_burned, log_date, notes, log_id, session["user_id"]),
        )
        conn.commit()
        flash("Log updated successfully.", "success")
        cursor.close()
        conn.close()
        return redirect(url_for("logs"))

    cursor.close()
    conn.close()
    return render_template("add_log.html", log=log, edit_mode=True)


@app.route("/logs/<int:log_id>/delete", methods=["POST"])
@login_required
def delete_log(log_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM fitness_logs WHERE id = %s AND user_id = %s",
        (log_id, session["user_id"]),
    )
    conn.commit()
    cursor.close()
    conn.close()
    flash("Log deleted successfully.", "success")
    return redirect(url_for("logs"))


@app.route("/reports")
@login_required
def reports():
    user_id = session["user_id"]
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT DATE(log_date) AS workout_day,
               SUM(duration_minutes) AS total_duration,
               SUM(calories_burned) AS total_calories
        FROM fitness_logs
        WHERE user_id = %s AND log_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        GROUP BY DATE(log_date)
        ORDER BY DATE(log_date) ASC
        """,
        (user_id,),
    )
    daily_summary = cursor.fetchall()

    cursor.execute(
        """
        SELECT DATE_FORMAT(log_date, '%Y-%m') AS month_label,
               SUM(duration_minutes) AS total_duration,
               COUNT(*) AS sessions,
               SUM(calories_burned) AS total_calories
        FROM fitness_logs
        WHERE user_id = %s
        GROUP BY DATE_FORMAT(log_date, '%Y-%m')
        ORDER BY log_date DESC
        LIMIT 6
        """,
        (user_id,),
    )
    monthly_summary = cursor.fetchall()

    cursor.execute(
        """
        SELECT exercise_type,
               COUNT(*) AS workouts,
               SUM(duration_minutes) AS total_duration,
               SUM(calories_burned) AS total_calories
        FROM fitness_logs
        WHERE user_id = %s
        GROUP BY exercise_type
        ORDER BY total_duration DESC
        """,
        (user_id,),
    )
    activity_breakdown = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "reports.html",
        daily_summary=daily_summary,
        monthly_summary=monthly_summary,
        activity_breakdown=activity_breakdown,
    )


@app.route("/calculator", methods=["GET", "POST"])
def calculator():
    result = None

    if request.method == "POST":
        gender = request.form.get("gender")
        age = float(request.form.get("age", 0) or 0)
        height_cm = float(request.form.get("height_cm", 0) or 0)
        weight_kg = float(request.form.get("weight_kg", 0) or 0)
        activity_level = request.form.get("activity_level")
        workout_minutes = float(request.form.get("workout_minutes", 0) or 0)

        if not all([gender, age, height_cm, weight_kg, activity_level]):
            flash("Please fill in all fields for the calorie calculator.", "danger")
            return render_template("calculator.html")

        activity_multiplier = {
            "sedentary": 1.2,
            "light": 1.375,
            "moderate": 1.55,
            "active": 1.725,
            "very_active": 1.9,
        }.get(activity_level, 1.2)

        if gender == "male":
            bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
        else:
            bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

        maintenance_calories = bmr * activity_multiplier
        exercise_calories = (workout_minutes * 7.0 * weight_kg) / 60

        result = {
            "bmr": round(bmr, 2),
            "maintenance_calories": round(maintenance_calories, 2),
            "exercise_calories": round(exercise_calories, 2),
            "daily_goal": round(maintenance_calories + exercise_calories, 2),
        }

    return render_template("calculator.html", result=result)


# -----------------------------
# Run app
# -----------------------------
if __name__ == "__main__":
    init_database()
    app.run(debug=True, host="0.0.0.0", port=5000)
