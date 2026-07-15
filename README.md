# NestCampus

Student hostel booking platform for Greater Accra — student/owner/admin accounts, owner verification, listing approval, semester-based bookings, simulated payments, reviews, and feedback.

## ⚠️ Critical: set up a persistent database before your next demo

**This is almost certainly why your owner login broke and accounts disappeared.** Render's free tier wipes the local disk on every redeploy — including the SQLite database. Every account, hostel, and booking gets deleted each time you push new code.

Fix (10 minutes, free, no card required):

1. Create a free Postgres database at **https://neon.tech** (sign up, create a project, copy the connection string — it looks like `postgresql://user:pass@host/dbname`)
2. On Render, go to your service → **Environment** → **Add Environment Variable**:
   - Key: `DATABASE_URL`
   - Value: the connection string from Neon
3. **Manual Deploy → Deploy latest commit**

Once this is set, your data survives redeploys, sleep/wake cycles, and restarts. Do this before showing the app to your client — right now every code push is erasing all your test data.

## Roles

- **Student** — browses, books, pays, reviews, asks questions, files complaints
- **Owner** — submits hostels for review (name, area, description, amenities, photo, *suggested* price/rooms), sees their own bookings and revenue, responds to questions/complaints, marks stays as checked-out
- **Super admin (you)** — reviews and edits every pending hostel (including final price/room counts/photo) before publishing, verifies new owners, resolves platform-wide feedback

## Owner verification flow

1. Owner signs up → account created but unverified, a 6-digit code is generated
2. An email attempt is sent to your admin address with the code (see Email setup below — if not configured, the code is simply visible in your Super Admin panel, which works fine on its own)
3. You confirm the person is legitimate, then give them the code (phone call, WhatsApp, in person — however you choose)
4. Owner enters the code at `/verify-owner` → verified
5. Owner submits a hostel → it's `pending`, invisible to students
6. You review it at `/superadmin`, edit anything (including price/rooms/photo), click **Save & publish**

## Login

Set up your own super admin credentials via environment variables (defaults are insecure placeholders):
- `SUPERADMIN_EMAIL` — defaults to `admin@nestcampus.demo`
- `SUPERADMIN_PASSWORD` — defaults to `changeme123`

**Set both of these as real values in Render's Environment tab before your demo** — the defaults are visible in this public GitHub repo, so anyone could log in as admin otherwise.

Demo owner account (seeded automatically, owns the 5 sample hostels): `owner@nestcampus.demo` / `demo1234` — also worth changing or removing before a real client demo.

## Email setup (optional)

Without this, owner-signup codes just show up in your Super Admin panel — fully functional, no email needed. If you want an actual email notification too:

- `MAIL_USERNAME` — a Gmail address
- `MAIL_PASSWORD` — a Gmail **app password** (not your real password — generate one at myaccount.google.com/apppasswords, requires 2-factor auth enabled)
- `ADMIN_NOTIFY_EMAIL` — already defaults to asamoahkingsley27@gmail.com, override if needed

## Run locally

```bash
pip install -r requirements.txt
python3 app.py
```
Open http://localhost:5000. Without `DATABASE_URL` set, it uses local SQLite automatically.

## Important things to know before a live demo

- **Payment is simulated.** A transaction reference of 6+ digits is treated as valid; anything else (letters, too short) shows a "Transaction failed" popup. This is intentional so you can demo both outcomes — use `123456` for success, `abc` for failure.
- **A semester is approximated as 130 days** for computing when a booking auto-completes. You can also manually mark any booking "checked-out" from the owner dashboard at any time — useful for demoing the review flow without waiting months.
- **A student can only have one active booking at a time** (any hostel) — this is enforced server-side.
- **Photos uploaded via the app are also NOT persistent** on Render's free tier disk — same root cause as the database. Once you've set up `DATABASE_URL` above, ask me about persistent file storage too (S3-compatible storage like Cloudflare R2 has a generous free tier) if photo uploads matter for your demo.
- **No payment commission is taken anywhere in the code** — matches what you asked for.

## What's simulated vs. real

| Feature | Status |
|---|---|
| Accounts, roles, sessions | Real |
| Hostel approval workflow | Real |
| Booking, semester pricing | Real |
| Payment | Simulated (no real money moves) |
| Owner verification code | Real (email delivery optional) |
| Reviews, Q&A, complaints | Real |
| Database persistence | **Needs your action — see top of this file** |
