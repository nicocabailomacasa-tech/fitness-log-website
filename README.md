# Fitness Log Website

A complete web application built with Python, Flask, and MySQL/XAMPP for tracking workouts, calories, daily activity, and fitness progress.

## Features
- User registration and login
- Exercise/activity records
- Workout duration tracking
- Calories burned tracking
- Daily fitness logs
- Progress overview
- Weekly and monthly reports
- Calories calculator

## Tech Stack
- Python
- Flask
- MySQL (XAMPP)
- HTML/CSS/Bootstrap

## Setup Instructions

### 1. Install XAMPP
- Download and install XAMPP.
- Start Apache and MySQL.

### 2. Create the database
Open phpMyAdmin or MySQL client and run:

```sql
CREATE DATABASE fitness_log_db;
```

Or import the provided `database.sql` file.

### 3. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 4. Install dependencies
```bash
pip install -r requirements.txt
```

### 5. Start the app
```bash
python app.py
```

Then open:

```text
http://localhost:5000
```

## Database Config
Update `config.py` if needed:

```python
DB_HOST = "localhost"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = ""
DB_NAME = "fitness_log_db"
```

## Project Structure
```text
fitness-log-website/
├── app.py
├── config.py
├── database.sql
├── requirements.txt
├── README.md
├── static/
│   └── style.css
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── add_log.html
│   ├── logs.html
│   ├── reports.html
│   └── calculator.html
└── venv/
```

## Notes
- The app uses session-based authentication.
- Default MySQL credentials in XAMPP are usually `root` with an empty password.
- If your local setup differs, update the credentials in `config.py`.
