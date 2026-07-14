# NestCampus — MVP Demo

A working booking + payment flow for student hostels in Greater Accra, built to demo to hostel owners before you pitch them.

## What's in this MVP
- Hostel listings with photos, amenities, and semester pricing
- Hostel detail page with a live interactive map (OpenStreetMap/Leaflet — no API key needed)
- Room selection with real-time availability
- Booking form → payment method selection (MTN MoMo, Vodafone Cash, AirtelTigo Money, Card, Bank Transfer) → confirmation with a reference number
- Owner dashboard showing bookings, revenue, and room availability

Payment is **simulated** for the pilot demo — no money actually moves. Once you have a hostel owner committed, the next step is registering for a Mobile Money merchant API (MTN MoMo API, Paystack, or Hubtel are common choices in Ghana) to make it real.

## Run it locally
```bash
cd nestcampus
pip install flask flask_sqlalchemy
python3 app.py
```
Then open http://localhost:5000

The database (SQLite) is created automatically on first run with 3 sample hostels near Legon so you have something to demo immediately. Delete `instance/nestcampus.db` any time to reset the seed data.

## Swap in real hostels
Edit the `seed()` function in `app.py` — replace the sample hostels with real ones (name, area, description, lat/lng coordinates, amenities) and drop real photos into `static/img/` once you have them from a hostel owner.

## Next steps to make this pitch-ready
1. Replace placeholder SVG images with real hostel photos once an owner agrees to a pilot
2. Get accurate lat/lng for each hostel (right-click the location in Google Maps → copy coordinates)
3. Deploy somewhere reachable (Render, PythonAnywhere, Railway all have free tiers) so you can send owners a live link instead of a local demo
4. Once a pilot is committed, look into MTN MoMo API / Paystack / Hubtel for real payment processing
