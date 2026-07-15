import os
import random
import string
import smtplib
import uuid
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# ---------- config (env-driven so nothing sensitive lives in code) ----------
db_url = os.environ.get('DATABASE_URL', 'sqlite:///nestcampus.db')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql+psycopg://', 1)
elif db_url.startswith('postgresql://'):
    db_url = db_url.replace('postgresql://', 'postgresql+psycopg://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'nestcampus-dev-key')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max upload

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'img', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

SUPERADMIN_EMAIL = os.environ.get('SUPERADMIN_EMAIL', 'admin@nestcampus.demo')
SUPERADMIN_PASSWORD = os.environ.get('SUPERADMIN_PASSWORD', 'changeme123')
ADMIN_NOTIFY_EMAIL = os.environ.get('ADMIN_NOTIFY_EMAIL', 'asamoahkingsley27@gmail.com')
MAIL_USERNAME = os.environ.get('MAIL_USERNAME')  # e.g. a Gmail address, only needed for real email sending
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')  # Gmail "app password", not the real password
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))

db = SQLAlchemy(app)

SEMESTER_DAYS = 130  # approx length of one semester, used to compute booking end dates


# ---------------- models ----------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # student / owner / superadmin
    is_verified = db.Column(db.Boolean, default=False)
    verification_code = db.Column(db.String(10), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    image = db.Column(db.String(160), nullable=False)
    amenities = db.Column(db.String(300), default="")
    status = db.Column(db.String(20), default="pending")  # pending / published
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    rooms = db.relationship('Room', backref='hostel', lazy=True, cascade="all, delete-orphan")
    owner = db.relationship('User')

    @property
    def avg_rating(self):
        reviews = Review.query.filter_by(hostel_id=self.id).all()
        if not reviews:
            return None
        return round(sum(r.rating for r in reviews) / len(reviews), 1)

    @property
    def review_count(self):
        return Review.query.filter_by(hostel_id=self.id).count()


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
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student_name = db.Column(db.String(120), nullable=False)
    student_phone = db.Column(db.String(30), nullable=False)
    semesters = db.Column(db.Integer, default=1)
    total_amount = db.Column(db.Integer, nullable=False)
    payment_method = db.Column(db.String(40), nullable=False)
    transaction_ref = db.Column(db.String(60), nullable=False)
    reference = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default="active")  # active / completed / cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)
    room = db.relationship('Room')
    student = db.relationship('User')


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), unique=True, nullable=False)
    hostel_id = db.Column(db.Integer, db.ForeignKey('hostel.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostel_id = db.Column(db.Integer, db.ForeignKey('hostel.id'), nullable=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(20), nullable=False)  # question / complaint / general
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default="open")  # open / resolved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    hostel = db.relationship('Hostel')
    from_user = db.relationship('User')


# ---------------- helpers ----------------

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file_storage):
    if not file_storage or file_storage.filename == '':
        return None
    if not allowed_file(file_storage.filename):
        return None
    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(UPLOAD_FOLDER, filename))
    return f"uploads/{filename}"


def generate_code():
    return ''.join(random.choices(string.digits, k=6))


def send_owner_verification_email(owner):
    """Best-effort email to the platform admin. Never blocks or crashes signup if it fails."""
    body = (
        f"A new hostel owner has signed up on NestCampus.\n\n"
        f"Name: {owner.name}\nEmail: {owner.email}\n"
        f"Verification code to give them once you've confirmed they're legitimate: {owner.verification_code}\n\n"
        f"You can also see this anytime in the Super Admin dashboard under Pending Owners."
    )
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        app.logger.info(f"[NestCampus] Email not configured. Owner signup pending: {owner.email} code={owner.verification_code}")
        return
    try:
        msg = MIMEText(body)
        msg['Subject'] = f"NestCampus: new owner signup - {owner.name}"
        msg['From'] = MAIL_USERNAME
        msg['To'] = ADMIN_NOTIFY_EMAIL
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:
            server.starttls()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.sendmail(MAIL_USERNAME, [ADMIN_NOTIFY_EMAIL], msg.as_string())
    except Exception as e:
        app.logger.warning(f"[NestCampus] Failed to send owner verification email: {e}")


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


def refresh_booking_statuses():
    """Auto-complete bookings whose semester period has ended."""
    now = datetime.utcnow()
    active = Booking.query.filter_by(status='active').filter(Booking.end_date <= now).all()
    for b in active:
        b.status = 'completed'
    if active:
        db.session.commit()


# ---------------- seed ----------------

def seed():
    if not User.query.filter_by(role='superadmin').first():
        superadmin = User(name="NestCampus Admin", email=SUPERADMIN_EMAIL, role="superadmin", is_verified=True)
        superadmin.set_password(SUPERADMIN_PASSWORD)
        db.session.add(superadmin)
        db.session.commit()

    if Hostel.query.first():
        return

    demo_owner = User(name="Demo Owner", email="owner@nestcampus.demo", role="owner", is_verified=True)
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
        hostel = Hostel(owner_id=demo_owner.id, status='published', **h)
        db.session.add(hostel)
        db.session.flush()
        db.session.add(Room(hostel_id=hostel.id, room_type="2 in a room", price_per_semester=1800, total_slots=12, booked_slots=7))
        db.session.add(Room(hostel_id=hostel.id, room_type="4 in a room", price_per_semester=1200, total_slots=20, booked_slots=14))
        db.session.add(Room(hostel_id=hostel.id, room_type="1 in a room (self-contained)", price_per_semester=3200, total_slots=6, booked_slots=2))
    db.session.commit()


# ---------------- public / student routes ----------------

@app.route('/')
def index():
    refresh_booking_statuses()
    q = request.args.get('q', '').strip()
    query = Hostel.query.filter_by(status='published')
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Hostel.name.ilike(like), Hostel.area.ilike(like)))
    hostels = query.all()
    return render_template('index.html', hostels=hostels, q=q)


@app.route('/hostel/<int:hostel_id>')
def hostel_detail(hostel_id):
    hostel = Hostel.query.get_or_404(hostel_id)
    if hostel.status != 'published':
        flash("This hostel isn't published yet.")
        return redirect(url_for('index'))
    questions = Feedback.query.filter_by(hostel_id=hostel.id, category='question').order_by(Feedback.created_at.desc()).all()
    reviews = Review.query.filter_by(hostel_id=hostel.id).order_by(Review.created_at.desc()).all()
    return render_template('hostel.html', hostel=hostel, questions=questions, reviews=reviews)


@app.route('/hostel/<int:hostel_id>/ask', methods=['POST'])
@login_required(role='student')
def ask_question(hostel_id):
    hostel = Hostel.query.get_or_404(hostel_id)
    message = request.form.get('message', '').strip()
    if message:
        fb = Feedback(hostel_id=hostel.id, from_user_id=current_user().id, category='question', message=message)
        db.session.add(fb)
        db.session.commit()
        flash("Your question has been sent to the hostel owner.")
    return redirect(url_for('hostel_detail', hostel_id=hostel.id))


@app.route('/book/<int:room_id>', methods=['GET', 'POST'])
@login_required(role='student')
def book(room_id):
    room = Room.query.get_or_404(room_id)
    user = current_user()

    existing = Booking.query.filter_by(student_id=user.id, status='active').first()
    if existing:
        flash(f"You already have an active booking at {existing.room.hostel.name}. You can't book another room until that stay ends.")
        return redirect(url_for('my_bookings'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        try:
            semesters = max(1, min(4, int(request.form.get('semesters', 1))))
        except ValueError:
            semesters = 1
        if not name or not phone:
            flash("Please fill in your name and phone number.")
            return render_template('book.html', room=room, prefill_name=user.name)
        return redirect(url_for('payment', room_id=room.id, name=name, phone=phone, semesters=semesters))
    return render_template('book.html', room=room, prefill_name=user.name)


@app.route('/payment/<int:room_id>', methods=['GET', 'POST'])
@login_required(role='student')
def payment(room_id):
    room = Room.query.get_or_404(room_id)
    user = current_user()
    name = request.values.get('name', '')
    phone = request.values.get('phone', '')
    try:
        semesters = max(1, min(4, int(request.values.get('semesters', 1))))
    except ValueError:
        semesters = 1
    total_amount = room.price_per_semester * semesters

    if request.method == 'POST':
        existing = Booking.query.filter_by(student_id=user.id, status='active').first()
        if existing:
            flash("You already have an active booking. You can't book another room right now.")
            return redirect(url_for('my_bookings'))

        if room.available <= 0:
            flash("Sorry, this room just filled up.")
            return redirect(url_for('hostel_detail', hostel_id=room.hostel_id))

        method = request.form.get('method')
        transaction_ref = request.form.get('transaction_ref', '').strip()

        # Simulated payment validation: a reference of at least 6 digits is treated as valid.
        # This mirrors a real MoMo/transaction reference check until a live payment API is connected.
        is_valid = transaction_ref.replace(' ', '').isdigit() and len(transaction_ref.replace(' ', '')) >= 6

        if not is_valid:
            return render_template('payment.html', room=room, name=name, phone=phone,
                                    semesters=semesters, total_amount=total_amount, payment_failed=True)

        reference = "NC" + str(random.randint(100000, 999999))
        end_date = datetime.utcnow() + timedelta(days=SEMESTER_DAYS * semesters)
        booking = Booking(room_id=room.id, student_id=user.id, student_name=name, student_phone=phone,
                           semesters=semesters, total_amount=total_amount, payment_method=method,
                           transaction_ref=transaction_ref, reference=reference, end_date=end_date)
        room.booked_slots += 1
        db.session.add(booking)
        db.session.commit()
        return redirect(url_for('confirmation', booking_id=booking.id))

    return render_template('payment.html', room=room, name=name, phone=phone,
                            semesters=semesters, total_amount=total_amount)


@app.route('/confirmation/<int:booking_id>')
@login_required(role='student')
def confirmation(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.student_id != current_user().id:
        flash("You don't have access to that booking.")
        return redirect(url_for('index'))
    return render_template('confirmation.html', booking=booking)


@app.route('/my-bookings')
@login_required(role='student')
def my_bookings():
    refresh_booking_statuses()
    user = current_user()
    bookings = Booking.query.filter_by(student_id=user.id).order_by(Booking.created_at.desc()).all()
    reviewed_ids = {r.booking_id for r in Review.query.filter_by(student_id=user.id).all()}
    return render_template('my_bookings.html', bookings=bookings, reviewed_ids=reviewed_ids)


@app.route('/booking/<int:booking_id>/review', methods=['POST'])
@login_required(role='student')
def leave_review(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    user = current_user()
    if booking.student_id != user.id:
        flash("You don't have access to that booking.")
        return redirect(url_for('my_bookings'))
    if booking.status != 'completed':
        flash("You can only review a stay after it's completed.")
        return redirect(url_for('my_bookings'))
    if Review.query.filter_by(booking_id=booking.id).first():
        flash("You've already reviewed this stay.")
        return redirect(url_for('my_bookings'))
    try:
        rating = max(1, min(5, int(request.form.get('rating', 5))))
    except ValueError:
        rating = 5
    comment = request.form.get('comment', '').strip()
    review = Review(booking_id=booking.id, hostel_id=booking.room.hostel_id, student_id=user.id,
                     rating=rating, comment=comment)
    db.session.add(review)
    db.session.commit()
    flash("Thanks for the review!")
    return redirect(url_for('my_bookings'))


@app.route('/hostel/<int:hostel_id>/complain', methods=['POST'])
@login_required(role='student')
def complain(hostel_id):
    hostel = Hostel.query.get_or_404(hostel_id)
    message = request.form.get('message', '').strip()
    if message:
        fb = Feedback(hostel_id=hostel.id, from_user_id=current_user().id, category='complaint', message=message)
        db.session.add(fb)
        db.session.commit()
        flash("Your complaint has been sent to the hostel owner.")
    return redirect(url_for('my_bookings'))


@app.route('/feedback', methods=['GET', 'POST'])
@login_required()
def general_feedback():
    if request.method == 'POST':
        message = request.form.get('message', '').strip()
        if message:
            fb = Feedback(from_user_id=current_user().id, category='general', message=message)
            db.session.add(fb)
            db.session.commit()
            flash("Thanks — your feedback has been sent to the NestCampus team.")
            return redirect(url_for('index'))
    return render_template('feedback.html')


# ---------------- owner routes ----------------

@app.route('/admin')
@login_required(role='owner')
def admin_dashboard():
    refresh_booking_statuses()
    user = current_user()
    hostels = Hostel.query.filter_by(owner_id=user.id).all()
    hostel_ids = [h.id for h in hostels]
    bookings = Booking.query.join(Room).filter(Room.hostel_id.in_(hostel_ids)).order_by(Booking.created_at.desc()).all() if hostel_ids else []
    total_revenue = sum(b.total_amount for b in bookings)
    feedback_items = Feedback.query.filter(Feedback.hostel_id.in_(hostel_ids)).order_by(Feedback.created_at.desc()).all() if hostel_ids else []
    return render_template('admin.html', hostels=hostels, bookings=bookings,
                            total_revenue=total_revenue, feedback_items=feedback_items)


@app.route('/admin/add-hostel', methods=['GET', 'POST'])
@login_required(role='owner')
def add_hostel():
    user = current_user()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        area = request.form.get('area', '').strip()
        description = request.form.get('description', '').strip()
        amenities = request.form.get('amenities', '').strip()
        try:
            lat = float(request.form.get('lat', '5.6500'))
            lng = float(request.form.get('lng', '-0.1800'))
        except ValueError:
            lat, lng = 5.6500, -0.1800
        try:
            suggested_price = max(0, int(request.form.get('suggested_price', 0)))
        except ValueError:
            suggested_price = 0
        try:
            suggested_slots = max(1, int(request.form.get('suggested_slots', 10)))
        except ValueError:
            suggested_slots = 10

        if not name or not area or not description:
            flash("Please fill in the hostel name, area, and description.")
            return render_template('add_hostel.html')

        uploaded_image = save_upload(request.files.get('photo'))
        image = uploaded_image or 'hostel1.svg'

        hostel = Hostel(owner_id=user.id, name=name, area=area, description=description,
                         lat=lat, lng=lng, image=image, amenities=amenities, status='pending')
        db.session.add(hostel)
        db.session.flush()
        db.session.add(Room(hostel_id=hostel.id, room_type="Suggested room",
                             price_per_semester=suggested_price or 1500, total_slots=suggested_slots, booked_slots=0))
        db.session.commit()
        flash(f"{name} submitted for review. It won't be visible to students until NestCampus approves and publishes it.")
        return redirect(url_for('admin_dashboard'))
    return render_template('add_hostel.html')


@app.route('/admin/hostel/<int:hostel_id>/photo', methods=['GET', 'POST'])
@login_required(role='owner')
def update_hostel_photo(hostel_id):
    user = current_user()
    hostel = Hostel.query.get_or_404(hostel_id)
    if hostel.owner_id != user.id:
        flash("You don't have access to that hostel.")
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        uploaded_image = save_upload(request.files.get('photo'))
        if not uploaded_image:
            flash("Please choose a JPG, PNG, or WEBP photo (max 5MB).")
            return render_template('update_photo.html', hostel=hostel)
        hostel.image = uploaded_image
        was_published = hostel.status == 'published'
        hostel.status = 'pending'
        db.session.commit()
        if was_published:
            flash(f"Photo updated for {hostel.name}. It's back in review and will be temporarily unlisted until NestCampus re-approves it.")
        else:
            flash(f"Photo updated for {hostel.name}. A NestCampus admin will review it before it goes live.")
        return redirect(url_for('admin_dashboard'))
    return render_template('update_photo.html', hostel=hostel)


@app.route('/admin/booking/<int:booking_id>/checkout', methods=['POST'])
@login_required(role='owner')
def checkout_booking(booking_id):
    user = current_user()
    booking = Booking.query.get_or_404(booking_id)
    if booking.room.hostel.owner_id != user.id:
        flash("You don't have access to that booking.")
        return redirect(url_for('admin_dashboard'))
    booking.status = 'completed'
    db.session.commit()
    flash(f"{booking.student_name}'s stay marked as completed.")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/feedback/<int:feedback_id>/respond', methods=['POST'])
@login_required(role='owner')
def respond_feedback(feedback_id):
    user = current_user()
    fb = Feedback.query.get_or_404(feedback_id)
    if not fb.hostel or fb.hostel.owner_id != user.id:
        flash("You don't have access to that item.")
        return redirect(url_for('admin_dashboard'))
    response = request.form.get('response', '').strip()
    if response:
        fb.response = response
        fb.status = 'resolved'
        db.session.commit()
        flash("Response sent.")
    return redirect(url_for('admin_dashboard'))


@app.route('/verify-owner', methods=['GET', 'POST'])
@login_required(role='owner')
def verify_owner():
    user = current_user()
    if user.is_verified:
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        if code and code == user.verification_code:
            user.is_verified = True
            db.session.commit()
            flash("You're verified! You can now submit hostels for review.")
            return redirect(url_for('admin_dashboard'))
        flash("That code doesn't match. Double check with NestCampus and try again.")
    return render_template('verify_owner.html')


# ---------------- superadmin routes ----------------

@app.route('/superadmin')
@login_required(role='superadmin')
def superadmin_dashboard():
    pending_owners = User.query.filter_by(role='owner', is_verified=False).all()
    pending_hostels = Hostel.query.filter_by(status='pending').all()
    published_hostels = Hostel.query.filter_by(status='published').all()
    open_feedback = Feedback.query.filter_by(status='open').order_by(Feedback.created_at.desc()).all()
    return render_template('superadmin.html', pending_owners=pending_owners, pending_hostels=pending_hostels,
                            published_hostels=published_hostels, open_feedback=open_feedback)


@app.route('/superadmin/owner/<int:user_id>/verify', methods=['POST'])
@login_required(role='superadmin')
def superadmin_verify_owner(user_id):
    owner = User.query.get_or_404(user_id)
    owner.is_verified = True
    db.session.commit()
    flash(f"{owner.name} marked as verified.")
    return redirect(url_for('superadmin_dashboard'))


@app.route('/superadmin/hostel/<int:hostel_id>/edit', methods=['GET', 'POST'])
@login_required(role='superadmin')
def superadmin_edit_hostel(hostel_id):
    hostel = Hostel.query.get_or_404(hostel_id)
    if request.method == 'POST':
        hostel.name = request.form.get('name', hostel.name).strip()
        hostel.area = request.form.get('area', hostel.area).strip()
        hostel.description = request.form.get('description', hostel.description).strip()
        hostel.amenities = request.form.get('amenities', hostel.amenities).strip()
        try:
            hostel.lat = float(request.form.get('lat', hostel.lat))
            hostel.lng = float(request.form.get('lng', hostel.lng))
        except ValueError:
            pass
        uploaded_image = save_upload(request.files.get('photo'))
        if uploaded_image:
            hostel.image = uploaded_image

        # update room prices / slots
        for room in hostel.rooms:
            price_key = f"price_{room.id}"
            slots_key = f"slots_{room.id}"
            if price_key in request.form:
                try:
                    room.price_per_semester = max(0, int(request.form.get(price_key)))
                except ValueError:
                    pass
            if slots_key in request.form:
                try:
                    room.total_slots = max(room.booked_slots, int(request.form.get(slots_key)))
                except ValueError:
                    pass

        # optional: add a brand new room type
        new_type = request.form.get('new_room_type', '').strip()
        if new_type:
            try:
                new_price = max(0, int(request.form.get('new_room_price', 0)))
                new_slots = max(1, int(request.form.get('new_room_slots', 1)))
            except ValueError:
                new_price, new_slots = 1500, 10
            db.session.add(Room(hostel_id=hostel.id, room_type=new_type,
                                 price_per_semester=new_price, total_slots=new_slots, booked_slots=0))

        if request.form.get('publish') == '1':
            hostel.status = 'published'
            flash(f"{hostel.name} is now published and visible to students.")
        else:
            db.session.commit()
            flash(f"{hostel.name} updated.")
            return redirect(url_for('superadmin_edit_hostel', hostel_id=hostel.id))

        db.session.commit()
        return redirect(url_for('superadmin_dashboard'))
    return render_template('superadmin_edit_hostel.html', hostel=hostel)


@app.route('/superadmin/feedback/<int:feedback_id>/resolve', methods=['POST'])
@login_required(role='superadmin')
def superadmin_resolve_feedback(feedback_id):
    fb = Feedback.query.get_or_404(feedback_id)
    fb.status = 'resolved'
    db.session.commit()
    return redirect(url_for('superadmin_dashboard'))


# ---------------- auth routes ----------------

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
            flash("An account with that email already exists. Log in instead, or use a different email.")
            return render_template('signup.html')

        user = User(name=name, email=email, role=role)
        user.set_password(password)
        if role == 'owner':
            user.is_verified = False
            user.verification_code = generate_code()
        else:
            user.is_verified = True
        db.session.add(user)
        db.session.commit()

        if role == 'owner':
            send_owner_verification_email(user)

        session['user_id'] = user.id
        flash(f"Welcome, {name}!")
        if role == 'owner':
            return redirect(url_for('verify_owner'))
        return redirect(url_for('index'))
    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', '')
        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash("Incorrect email or password.")
            return render_template('login.html')

        if role and user.role != role:
            role_label = {'student': 'a student', 'owner': 'an owner', 'superadmin': 'an admin'}.get(user.role, user.role)
            flash(f"This email is registered as {role_label} account. Please log in with the correct account type.")
            return render_template('login.html')

        session['user_id'] = user.id
        if user.role == 'owner':
            return redirect(url_for('admin_dashboard') if user.is_verified else url_for('verify_owner'))
        if user.role == 'superadmin':
            return redirect(url_for('superadmin_dashboard'))
        return redirect(url_for('index'))
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
