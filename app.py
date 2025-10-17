from models import User, DailyLog
from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pandas as pd
import plotly.express as px
import io
import base64
import os

BASE_DIR = os.getcwd()

app = Flask(__name__)
app.secret_key = "yoursecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + \
    os.path.join(BASE_DIR, 'moodgut.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


db = SQLAlchemy(app)

# User table


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f"<User {self.username}>"

# DailyLog table (for mood/gut entries)


class DailyLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20))
    mood = db.Column(db.String(20))
    meal = db.Column(db.String(100))
    gut_symptom = db.Column(db.String(50))
    sleep_hours = db.Column(db.Float)
    water_intake = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('logs', lazy=True))


# Import models
with app.app_context():
    db.create_all()

# -------- ROUTES --------


@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        if User.query.filter_by(username=username).first():
            flash("Username already exists!")
            return redirect(url_for('register'))
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        flash("Registration successful! Please log in.")
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials.")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/add', methods=['GET', 'POST'])
def add_entry():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        log = DailyLog(
            date=datetime.now().strftime("%Y-%m-%d"),
            mood=request.form['mood'],
            meal=request.form['meal'],
            gut_symptom=request.form['gut_symptom'],
            sleep_hours=float(request.form['sleep_hours']),
            water_intake=float(request.form['water_intake']),
            user_id=session['user_id']
        )
        db.session.add(log)
        db.session.commit()
        flash("Entry added successfully!")
        return redirect(url_for('dashboard'))
    return render_template('add_entry.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    logs = DailyLog.query.filter_by(user_id=session['user_id']).all()
    if not logs:
        return render_template('dashboard.html', charts=None, interpretation=None)

    # Convert entries to DataFrame
    df = pd.DataFrame([{
        'date': l.date,
        'mood': l.mood,
        'sleep_hours': l.sleep_hours,
        'water_intake': l.water_intake,
        'gut_symptom': l.gut_symptom,
        'meal': l.meal
    } for l in logs])

    # Map mood to numeric scores for quant analysis
    mood_map = {'Happy': 5, 'Calm': 4, 'Neutral': 3,
                'Sad': 2, 'Stressed': 1, 'Tired': 2}
    df['mood_score'] = df['mood'].map(mood_map)

    charts = []

    # 1️⃣ Mood Trend Over Time
    fig1 = px.line(df, x='date', y='mood_score', title="Mood Trend Over Time",
                   markers=True, line_shape="spline")
    charts.append(fig1.to_html(full_html=False))

    # 2️⃣ Sleep vs. Mood
    fig2 = px.scatter(df, x='sleep_hours', y='mood_score',
                      title="Sleep vs Mood",
                      trendline="ols",
                      color='gut_symptom')
    charts.append(fig2.to_html(full_html=False))

    # 3️⃣ Water Intake Trend
    fig3 = px.line(df, x='date', y='water_intake', title="Water Intake Over Time",
                   markers=True, line_shape="spline")
    charts.append(fig3.to_html(full_html=False))

    # 4️⃣ Gut Symptom Frequency
    gut_counts = df['gut_symptom'].value_counts().reset_index()
    gut_counts.columns = ['gut_symptom', 'count']
    fig4 = px.bar(gut_counts, x='gut_symptom', y='count',
                  title="Gut Symptom Frequency", text='count')
    charts.append(fig4.to_html(full_html=False))

    # 5️⃣ Mood vs. Gut Symptom
    avg_mood_by_gut = df.groupby('gut_symptom')[
        'mood_score'].mean().reset_index()
    fig5 = px.bar(avg_mood_by_gut, x='gut_symptom', y='mood_score',
                  title="Average Mood by Gut Symptom", text_auto=True)
    charts.append(fig5.to_html(full_html=False))

    # 🧩 Simple Interpretation
    avg_sleep = df['sleep_hours'].mean()
    avg_water = df['water_intake'].mean()
    common_gut = df['gut_symptom'].mode()[0]
    avg_mood = df['mood_score'].mean()

    interpretation = f"""
    Over your recent entries:
    - Your average sleep is **{avg_sleep:.1f} hours** and water intake is **{avg_water:.1f} L**.
    - The most frequent gut symptom is **{common_gut.lower()}**.
    - Your average mood score is **{avg_mood:.1f}/5**.

    """

    # Insight based on relationships
    if avg_sleep < 6:
        interpretation += "⛔ You might benefit from more sleep — your mood seems lower on shorter sleep days.\n"
    elif avg_sleep > 8:
        interpretation += "😴 You’re sleeping well; moods are likely more stable.\n"

    if avg_water < 1.5:
        interpretation += "💧 Try increasing water intake for better digestion and mood balance.\n"

    if common_gut.lower() in ['bloating', 'constipation']:
        interpretation += f"⚠️ Watch out for {common_gut.lower()} — it appears often; note any meal patterns causing it.\n"

    if avg_mood > 4:
        interpretation += "🌞 Great! Your moods are generally positive."
    elif avg_mood < 3:
        interpretation += "☁️ Your moods seem on the lower side — consider focusing on rest and gut comfort."

    return render_template('dashboard.html', charts=charts, interpretation=interpretation)


if __name__ == "__main__":
    app.run(debug=True)
