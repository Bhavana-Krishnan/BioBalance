from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    logs = db.relationship('DailyLog', backref='user', lazy=True)

class DailyLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20))
    mood = db.Column(db.String(20))
    meal = db.Column(db.String(100))
    gut_symptom = db.Column(db.String(50))
    sleep_hours = db.Column(db.Float)
    water_intake = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
