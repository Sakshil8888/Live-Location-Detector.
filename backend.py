"""
backend.py - all location-sharing logic (validation, storage, API views).

Active sessions live in a plain Python dictionary (ACTIVE_SHARES).
No database, no models, no migrations.
"""
import json
import math
import re
import secrets
import threading
import time

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

# ---------------- Settings ----------------
STALE_AFTER_SECONDS = 90    # no update for this long -> session is treated as ended
MAX_FAILED_ATTEMPTS = 5     # wrong code guesses allowed per number...
LOCKOUT_SECONDS = 60        # ...within this many seconds

# ---------------- In-memory storage ----------------
# Only the LATEST point is stored (no history). Lost when the server restarts.
ACTIVE_SHARES = {}
FAILED_LOOKUPS = {}          # {"phone": {"count": int, "since": float}}
LOCK = threading.Lock()      # the dev server handles requests in threads

PHONE_PATTERN = re.compile(r"[+]?[0-9]{10,15}")
CODE_PATTERN = re.compile(r"[0-9]{6}")


# ---------------- Helper functions ----------------
def error_response(message, status=400):
    return JsonResponse({"ok": False, "error": message}, status=status)


def clean_phone(raw):
    """Remove spaces, dashes and brackets, then check the number. Returns None if invalid."""
    if not isinstance(raw, str):
        return None
    phone = re.sub(r"[\s\-()]", "", raw)
    return phone if PHONE_PATTERN.fullmatch(phone) else None


def read_json_body(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except ValueError:  # also covers bad UTF-8 and bad JSON
        raise ValueError("Request body must be valid JSON.")
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object.")
    return data


def to_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number.")
    return number


def validate_coordinates(data):
    latitude = to_number(data.get("latitude"), "Latitude")
    longitude = to_number(data.get("longitude"), "Longitude")
    accuracy = to_number(data.get("accuracy", 0), "Accuracy")
    if not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90.")
    if not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180.")
    if accuracy < 0:
        raise ValueError("Accuracy cannot be negative.")
    return latitude, longitude, accuracy


def same_secret(supplied, expected):
    """Constant-time comparison so secrets cannot be guessed by timing."""
    if not isinstance(supplied, str):
        return False
    return secrets.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))


def purge_expired(now):
    """Delete sessions that stopped updating. Call only while holding LOCK."""
    for phone in [p for p, s in ACTIVE_SHARES.items() if now - s["updated_at"] > STALE_AFTER_SECONDS]:
        del ACTIVE_SHARES[phone]
    for phone in [p for p, r in FAILED_LOOKUPS.items() if now - r["since"] > LOCKOUT_SECONDS]:
        del FAILED_LOOKUPS[phone]


# NEW: whole function
def add_alert(session, kind, now):
    """Remember a security event so the owner's page can show it. Keep max 20."""
    alerts = session.setdefault("alerts", [])
    if len(alerts) < 20:
        alerts.append({"type": kind, "time": now})


# ---------------- API view 1: start / update sharing ----------------
@require_POST
def share_location(request):
    try:
        data = read_json_body(request)
    except ValueError as exc:
        return error_response(str(exc))

    phone = clean_phone(data.get("phone"))
    if phone is None:
        return error_response("Enter a valid mobile number (10 to 15 digits, optional leading +).")

    try:
        latitude, longitude, accuracy = validate_coordinates(data)
    except ValueError as exc:
        return error_response(str(exc))

    owner_token = data.get("owner_token")
    now = time.time()

    with LOCK:
        purge_expired(now)
        session = ACTIVE_SHARES.get(phone)
        created = session is None

        if created:
            session = {
                "owner_token": secrets.token_urlsafe(16),
                "view_code": f"{secrets.randbelow(1_000_000):06d}",
            }
            ACTIVE_SHARES[phone] = session
        elif not same_secret(owner_token, session["owner_token"]):
            add_alert(session, "takeover_attempt", now)          # NEW
            return error_response("This number is already being shared from another page.", 409)

        session["latitude"] = latitude
        session["longitude"] = longitude
        session["accuracy"] = accuracy
        session["updated_at"] = now

        response = {
            "ok": True,
            "latitude": latitude,
            "longitude": longitude,
            "accuracy": accuracy,
            "updated_at": now,
            "view_code": session["view_code"],
            "alerts": session.pop("alerts", []),                 # NEW: sent once, then cleared
        }
        if created:
            response["owner_token"] = session["owner_token"]  # sent only once, at creation
        return JsonResponse(response)


# ---------------- API view 2: viewer retrieves location ----------------
@require_GET
def get_location(request):
    phone = clean_phone(request.GET.get("phone"))
    if phone is None:
        return error_response("Enter a valid mobile number (10 to 15 digits, optional leading +).")

    code = request.GET.get("code", "").strip()
    if not CODE_PATTERN.fullmatch(code):
        return error_response("Enter the 6-digit share code given by the person sharing.")

    now = time.time()
    with LOCK:
        purge_expired(now)

        record = FAILED_LOOKUPS.get(phone)
        if record and record["count"] >= MAX_FAILED_ATTEMPTS:
            locked_session = ACTIVE_SHARES.get(phone)            # NEW
            if locked_session is not None:                       # NEW
                add_alert(locked_session, "locked", now)         # NEW
            return error_response("Too many wrong attempts. Wait a minute and try again.", 429)

        session = ACTIVE_SHARES.get(phone)
        # One generic message for "no session" and "wrong code" so nothing leaks.
        if session is None or not same_secret(code, session["view_code"]):
            if session is not None:                              # NEW
                add_alert(session, "wrong_code", now)            # NEW
            record = FAILED_LOOKUPS.setdefault(phone, {"count": 0, "since": now})
            record["count"] += 1
            return error_response("No active shared location found for this number and code.", 404)

        FAILED_LOOKUPS.pop(phone, None)
        if not session.get("view_notified"):                     # NEW
            session["view_notified"] = True                      # NEW
            add_alert(session, "viewed", now)                    # NEW
        return JsonResponse({
            "ok": True,
            "latitude": session["latitude"],
            "longitude": session["longitude"],
            "accuracy": session["accuracy"],
            "updated_at": session["updated_at"],
            "google_maps_url": f"https://www.google.com/maps?q={session['latitude']},{session['longitude']}",
        })


# ---------------- API view 3: stop sharing ----------------
@require_POST
def stop_sharing(request):
    try:
        data = read_json_body(request)
    except ValueError as exc:
        return error_response(str(exc))

    phone = clean_phone(data.get("phone"))
    if phone is None:
        return error_response("Enter a valid mobile number (10 to 15 digits, optional leading +).")

    with LOCK:
        session = ACTIVE_SHARES.get(phone)
        if session is None:
            return JsonResponse({"ok": True, "message": "Sharing was already stopped."})
        if not same_secret(data.get("owner_token"), session["owner_token"]):
            return error_response("You are not allowed to stop this session.", 403)
        del ACTIVE_SHARES[phone]
        return JsonResponse({"ok": True, "message": "Sharing stopped and location removed."})