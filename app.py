from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from zoneinfo import ZoneInfo
from threading import Lock

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///reminders.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ---- Model ----
class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    dosage = db.Column(db.String(120), nullable=False)
    time = db.Column(db.String(5), nullable=False)  # "HH:MM"
    days = db.Column(db.String(50), nullable=False)  # "MON,TUE"
    notes = db.Column(db.Text)

with app.app_context():
    db.create_all()

# ---- Notification queue (simple in‑memory) ----
_notifications = []
_lock = Lock()

def push_notification(rem):
    with _lock:
        _notifications.append({
            "id": rem.id,
            "name": rem.name,
            "dosage": rem.dosage,
            "notes": rem.notes or ""
        })

def pop_notifications():
    with _lock:
        data = list(_notifications)
        _notifications.clear()
        return data

# ---- Scheduler ----
def check_due():
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    day = now.strftime("%a").upper()  # MON, TUE, ...
    hhmm = now.strftime("%H:%M")
    with app.app_context():
        for r in Reminder.query.all():
            if r.time == hhmm and day in r.days.split(","):
                push_notification(r)

scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
scheduler.add_job(check_due, "interval", seconds=30)
scheduler.start()

# ---- Routes ----
@app.route("/", methods=["GET"])
def index():
    reminders = Reminder.query.all()
    return render_template("index.html", reminders=reminders)

@app.route("/add", methods=["POST"])
def add():
    name = request.form["name"]
    dosage = request.form["dosage"]
    time_ = request.form["time"]  # "HH:MM"
    days = request.form.getlist("days")
    notes = request.form.get("notes", "")
    r = Reminder(name=name, dosage=dosage, time=time_, days=",".join(days), notes=notes)
    db.session.add(r)
    db.session.commit()
    return redirect(url_for("index"))

@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    Reminder.query.filter_by(id=id).delete()
    db.session.commit()
    return redirect(url_for("index"))

@app.route("/api/notifications", methods=["GET"])
def notifications():
    return jsonify(pop_notifications())

if __name__ == "__main__":
    # avoid double scheduler when reloader is on
    app.run(debug=True, use_reloader=False)
