from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import random

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nestcampus.db'
app.config['SECRET_KEY'] = 'nestcampus-dev-key'
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'student' or 'owner'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Hostel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    area = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    image = db.Column(db.String(120), nullable=False)
    amenities = db.Column(db.String(300), default="")
    rooms = db.relationship('Room', backref='hostel', lazy=True)
    owner = db.relationship('User')


class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostel_id = db.Column(db.Integer, db.ForeignKey('hostel.id'), nullable=False)
    room_type = db.Column(db.String(80), nullable=False)
    price_per_semester = db.Column(db.Integer, nullable=False)
    total_slots = db.Column(db.Integer, nullable=False)
    booked_slots = db.Column(db.Integer, default=0)

    @property
    def available(self):
        return self.total_slots - self.booked_slots


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    student_name = db.Column(db.String(120), nullable=False)
    student_phone = db.Column(db.String(30), nullable=False)
    payment_method = db.Column(db.String(40), nullable=False)
    reference = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default="confirmed")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    room = db.relationship('Room')


# ---------- auth helpers ----------

def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    return User.query.get(uid)


@app.context_processor
def inject_user():
    return dict(current_user=current_user())


def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Please log in to continue.")
                return redirect(url_for('login'))
            if role and user.role != role:
                flash("You don't have access to that page.")
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return wrapped
    return decorator


# ---------- seed ----------

def seed():
    if Hostel.query.first():
        return
    demo_owner = User(name="Demo Owner", email="owner@nestcampus.demo", role="owner")
    demo_owner.set_password("demo1234")
    db.session.add(demo_owner)
    db.session.flush()

    hostels = [
        dict(name="Supreme Hostel", area="Okponglo Street, Legon",
             description="Well-known hostel on Okponglo Street, a short walk from Legon campus. Popular pick for students wanting easy access to Main Gate and Okponglo transport hub.",
             lat=5.6497, lng=-0.1745, image="hostel1.svg",
             amenities="Wi-Fi,Backup power,24/7 water,Security"),
        dict(name="UPSA Hostel", area="East Legon, ~300m from UPSA",
             description="Large 8-storey hostel with elevators, purpose-built for UPSA students. Spacious rooms with shuttle service to campus.",
             lat=5.6550, lng=-0.1660, image="hostel2.svg",
             amenities="Wi-Fi,Generator,Elevators,Shuttle service,Security,Parking,TV room"),
        dict(name="Locus Hostel", area="Legon area (confirm exact location)",
             description="Details pending confirmation \u2014 update with the real address, description, and photos before pitching.",
             lat=5.6494, lng=-0.1832, image="hostel3.svg",
             amenities="Wi-Fi,Security"),
        dict(name="Philipo Hostel", area="Legon area (confirm exact location)",
             description="Details pending confirmation \u2014 update with the real address, description, and photos before pitching.",
             lat=5.6516, lng=-0.1870, image="hostel1.svg",
             amenities="Wi-Fi,Security"),
        dict(name="Legon Hostel", area="Legon (confirm exact location)",
             description="Details pending confirmation \u2014 update with the real address, description, and photos before pitching.",
             lat=5.6520, lng=-0.1900, image="hostel2.svg",
             amenities="Wi-Fi,Security"),
    ]
    for h in hostels:
        hostel = Hostel(owner_id=demo_owner.id, **h)
        db.session.add(hostel)
        db.session.flush()
        db.session.add(Room(hostel_id=hostel.id, room_type="2 in a room", price_per_semester=1800, total_slots=12, booked_slots=7))
        db.session.add(Room(hostel_id=hostel.id, room_type="4 in a room", price_per_semester=1200, total_slots=20, booked_slots=14))
        db.session.add(Room(hostel_id=hostel.id, room_type="1 in a room (self-contained)", price_per_semester=3200, total_slots=6, booked_slots=2))
    db.session.commit()


# ---------- public / student routes ----------

@app.route('/')
def index():
    hostels = Hostel.query.all()
    return render_template('index.html', hostels=hostels)


@app.route('/hostel/<int:hostel_id>')
def hostel_detail(hostel_id):
    hostel = Hostel.query.get_or_404(hostel_id)
    return render_template('hostel.html', hostel=hostel)


@app.route('/book/<int:room_id>', methods=['GET', 'POST'])
def book(room_id):
    room = Room.query.get_or_404(room_id)
    user = current_user()
    prefill_name = user.name if user and user.role == 'student' else ''
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        if not name or not phone:
            flash("Please fill in your name and phone number.")
            return render_template('book.html', room=room, prefill_name=prefill_name)
        return redirect(url_for('payment', room_id=room.id, name=name, phone=phone))
    return render_template('book.html', room=room, prefill_name=prefill_name)


@app.route('/payment/<int:room_id>', methods=['GET', 'POST'])
def payment(room_id):
    room = Room.query.get_or_404(room_id)
    name = request.args.get('name', '')
    phone = request.args.get('phone', '')
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        method = request.form.get('method')
        reference = "NC" + str(random.randint(100000, 999999))
        user = current_user()
        booking = Booking(room_id=room.id, student_id=user.id if user and user.role == 'student' else None,
                           student_name=name, student_phone=phone,
                           payment_method=method, reference=reference)
        room.booked_slots += 1
        db.session.add(booking)
        db.session.commit()
        return redirect(url_for('confirmation', booking_id=booking.id))
    return render_template('payment.html', room=room, name=name, phone=phone)


@app.route('/confirmation/<int:booking_id>')
def confirmation(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    return render_template('confirmation.html', booking=booking)


@app.route('/my-bookings')
@login_required(role='student')
def my_bookings():
    user = current_user()
    bookings = Booking.query.filter_by(student_id=user.id).order_by(Booking.created_at.desc()).all()
    return render_template('my_bookings.html', bookings=bookings)


# ---------- owner routes ----------

@app.route('/admin')
@login_required(role='owner')
def admin_dashboard():
    user = current_user()
    hostels = Hostel.query.filter_by(owner_id=user.id).all()
    hostel_ids = [h.id for h in hostels]
    bookings = Booking.query.join(Room).filter(Room.hostel_id.in_(hostel_ids)).order_by(Booking.created_at.desc()).all() if hostel_ids else []
    total_revenue = sum(b.room.price_per_semester for b in bookings)
    return render_template('admin.html', hostels=hostels, bookings=bookings, total_revenue=total_revenue)


@app.route('/admin/add-hostel', methods=['GET', 'POST'])
@login_required(role='owner')
def add_hostel():
    user = current_user()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        area = request.form.get('area', '').strip()
        description = request.form.get('description', '').strip()
        amenities = request.form.get('amenities', '').strip()
        image = request.form.get('image', 'hostel1.svg')
        try:
            lat = float(request.form.get('lat', '5.6500'))
            lng = float(request.form.get('lng', '-0.1800'))
        except ValueError:
            lat, lng = 5.6500, -0.1800

        if not name or not area or not description:
            flash("Please fill in the hostel name, area, and description.")
            return render_template('add_hostel.html')

        hostel = Hostel(owner_id=user.id, name=name, area=area, description=description,
                         lat=lat, lng=lng, image=image, amenities=amenities)
        db.session.add(hostel)
        db.session.flush()
        db.session.add(Room(hostel_id=hostel.id, room_type="2 in a room", price_per_semester=1800, total_slots=10, booked_slots=0))
        db.session.add(Room(hostel_id=hostel.id, room_type="4 in a room", price_per_semester=1200, total_slots=16, booked_slots=0))
        db.session.commit()
        flash(f"{name} added to your listings.")
        return redirect(url_for('admin_dashboard'))
    return render_template('add_hostel.html')


# ---------- auth routes ----------

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', '')

        if not name or not email or not password or role not in ('student', 'owner'):
            flash("Please fill in all fields and pick an account type.")
            return render_template('signup.html')

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.")
            return render_template('signup.html')

        user = User(name=name, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        flash(f"Welcome, {name}!")
        return redirect(url_for('admin_dashboard') if role == 'owner' else url_for('index'))
    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Incorrect email or password.")
            return render_template('login.html')
        session['user_id'] = user.id
        return redirect(url_for('admin_dashboard') if user.role == 'owner' else url_for('index'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))


with app.app_context():
    db.create_all()
    seed()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
