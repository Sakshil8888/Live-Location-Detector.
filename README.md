# Live Location Detector

A beginner-friendly mini project demonstrating **consent-based live location sharing** using the browser's Geolocation API, plain JavaScript, and Django (without a database).

## What this project does

- A person (the **sharer**) opens the page, enters their own phone number, and clicks **Share My Location**. Their browser asks for GPS permission.
- Once allowed, their live coordinates are sent to the server every few seconds.
- The server gives the sharer a **6-digit share code**.
- Anyone who wants to view that location (the **viewer**) must enter **both** the phone number **and** the share code.
- The sharer can stop sharing at any time, which deletes their location from the server immediately.

## Why a phone number alone isn't enough

This project is deliberately **not** able to look up a person's location from just their phone number. That would mean secretly tracking someone, which this project avoids by design:

- A phone number only **labels** a session — it never identifies or locates a device by itself.
- A location only exists on the server if its owner actively started sharing from their own device.
- A viewer also needs the one-time 6-digit code, so knowing someone's number is not enough to see where they are.
- A wrong code doesn't say whether the number exists or not — it gives the same generic error either way, so numbers can't be fished for.

This mirrors how real sharing works (e.g. WhatsApp location sharing) — the device owner always has to take the action themselves.

## Features

- Live GPS tracking using `navigator.geolocation.watchPosition()`
- Interactive map (Leaflet + OpenStreetMap) with a live marker and accuracy radius
- Shows latitude, longitude, accuracy (in metres), and last update time
- One-click **Open in Google Maps** link
- Start/stop sharing at any time
- Basic abuse protection: wrong-code lockout after repeated failed attempts
- In-page alerts to the sharer when someone enters a wrong code, gets locked out, or successfully views their location

## Tech stack

- **Frontend:** HTML, CSS, JavaScript (no frameworks), Leaflet.js for the map
- **Backend:** Python, Django (views only — no models, no database)
- **Storage:** an in-memory Python dictionary (see limitations below)

## Project structure
```
live-location-detector/
├── index.html      # Full UI: HTML, CSS, and JavaScript
├── backend.py       # All location-sharing logic and API views
├── django_app.py    # Django setup, URL routing, and server entry point
├── .gitignore
└── README.md
```
Only three application files are used on purpose, to keep the project simple enough for a beginner to read end-to-end. Django's usual `manage.py`, `settings.py`, and `urls.py` are folded into `django_app.py` using `settings.configure()` and `ROOT_URLCONF`.

## Setup and installation
Requires Python 3.10+.
```bash
# clone the repo
git clone <your-repo-url>
cd live-location-detector

# create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # macOS/Linux

# install Django
pip install django
```

## Running the project
```bash
python django_app.py
```
Then open **http://127.0.0.1:8000/** in your browser. Do not open `index.html` directly — it must be served by Django for the API and CSRF protection to work.
## How to test it (two windows)
1. **Window A (sharer):** open the app, enter a phone number, click **Share My Location**, and allow GPS permission. Note the 6-digit code shown.
2. **Window B (viewer):** open the app in a second window, enter the same phone number and the code, then click **Find Shared Location**.
3. Window B should now show the live location, updating every few seconds.
4. Click **Stop Sharing** in Window A — Window B should show an error shortly after.

Both windows will show the same location, since they're on the same device. To see a *different* person's real location, they need to open the app on their own device and share from there (see note below on local-only networking).

## Limitations
- **In-memory storage:** all active sessions live in a Python dictionary and are lost whenever the Django server restarts. This is intentional for a learning project and is **not suitable for production use**.
- **Local use only:** the app runs on Django's development server (`runserver`) with `DEBUG=True`, which is meant for local testing only, not public deployment.
- **Single-device/local-network scope:** by default, only `127.0.0.1` can access the app. Testing with a second real device (e.g. a friend's phone) requires exposing the server over HTTPS (e.g. via a tunnel like Cloudflare Tunnel or ngrok), since browsers block GPS access on non-secure origins except `localhost`.
- **No accounts or history:** only the latest location point is stored; there's no login system and no location history, by design.

## Disclaimer
This is an educational demo built to understand the Geolocation API, Django request handling, and consent-based design — not a production tracking system. Location sharing only ever happens with the explicit, active participation of the device owner.
