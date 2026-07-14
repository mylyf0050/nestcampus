from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nestcampus.db'
app.config['SECRET_KEY'] = 'nestcampus-dev-key'
db = SQLAlchemy(app)


class Hostel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    area = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    image = db.Column(db.String(120), nullable=False)
    amenities = db.Column(db.String(300), default="")
    rooms = db.relationship('Room', backref='hostel', lazy=True)


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
    student_name = db.Column(db.String(120), nullable=False)
    student_phone = db.Column(db.String(30), nullable=False)
    payment_method = db.Column(db.String(40), nullable=False)
    reference = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default="confirmed")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    room = db.relationship('Room')


def seed():
    if Hostel.query.first():
        return
    hostels = [
        dict(name="Nyame Bekyere Hostel", area="Legon, near Main Gate",
             description="A calm, secure hostel a 5-minute walk from Legon's Main Gate. Backup power, 24/7 water supply, and a shared study lounge on every floor.",
             lat=5.6516, lng=-0.1870, image="hostel1.svg",
             amenities="Wi-Fi,Backup power,24/7 water,Study lounge,Laundry"),
        dict(name="Adenta Scholars Lodge", area="Adenta, 10 mins from campus shuttle",
             description="Modern rooms with private bathrooms, popular with second and third-year students. Shuttle stop right outside the gate.",
             lat=5.7079, lng=-0.1653, image="hostel2.svg",
             amenities="Wi-Fi,Private bathroom,CCTV,Kitchen,Shuttle nearby"),
        dict(name="Haatso Heights", area="Haatso, near Ecomog Junction",
             description="Newly built hostel with a rooftop reading area and gated compound. Popular with final-year and graduate students.",
             lat=5.6710, lng=-0.2010, image="hostel3.svg",
             amenities="Wi-Fi,Gated compound,Rooftop lounge,Backup power,Gym"),
    ]
    for h in hostels:
        hostel = Hostel(**h)
        db.session.add(hostel)
        db.session.flush()
        db.session.add(Room(hostel_id=hostel.id, room_type="2 in a room", price_per_semester=1800, total_slots=12, booked_slots=7))
        db.session.add(Room(hostel_id=hostel.id, room_type="4 in a room", price_per_semester=1200, total_slots=20, booked_slots=14))
        db.session.add(Room(hostel_id=hostel.id, room_type="1 in a room (self-contained)", price_per_semester=3200, total_slots=6, booked_slots=2))
    db.session.commit()


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
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        if not name or not phone:
            flash("Please fill in your name and phone number.")
            return render_template('book.html', room=room)
        return redirect(url_for('payment', room_id=room.id, name=name, phone=phone))
    return render_template('book.html', room=room)


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
        booking = Booking(room_id=room.id, student_name=name, student_phone=phone,
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


@app.route('/admin')
def admin_dashboard():
    hostels = Hostel.query.all()
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    total_revenue = sum(b.room.price_per_semester for b in bookings)
    return render_template('admin.html', hostels=hostels, bookings=bookings, total_revenue=total_revenue)


with app.app_context():
    db.create_all()
    seed()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
