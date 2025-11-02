
import requests
import os
import stripe
from flask import Blueprint, jsonify, request, g
from flask_login import login_required, current_user
import logging


api_bp = Blueprint('api', __name__)


from functools import wraps

api_bp = Blueprint('api', __name__)

# --- Admin-only Middleware ---
def admin_required(f):
    from flask_login import current_user
    from flask import jsonify
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(current_user, 'role') or current_user.role != 'admin':
            return jsonify({'error': 'Forbidden: admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# --- Example Admin Endpoint ---
@api_bp.route('/admin/ping', methods=['GET'])
@login_required
@admin_required
def admin_ping():
    """
    GET /api/admin/ping
    - Description: Simple admin-only endpoint for testing
    - Auth: Admin session required
    - Response: {"message": "pong"}
    - Errors: 403 (Forbidden)
    """
    from flask import jsonify
    return jsonify({'message': 'pong'})

# --- Proxy for Government of Canada EV Stations API to avoid CORS ---
@api_bp.route('/external/canada_ev/locations', methods=['GET'])
def proxy_canada_ev_locations():
    """
    Proxies the Government of Canada EV station API to avoid CORS issues on the frontend.
    """
    try:
        url = 'https://services.arcgis.com/zmLUiqh7X11gGV2d/arcgis/rest/services/alt_fuel_stations/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=json'
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return jsonify(resp.json())
    except Exception as e:
        logger.exception("Failed to fetch Canada EV locations")
        return jsonify({"features": []}), 502

# --- Proxy for ChargeHub API to avoid CORS ---
@api_bp.route('/external/chargehub/locations', methods=['GET'])
def proxy_chargehub_locations():
    """
    Proxies the ChargeHub trial API to avoid CORS issues on the frontend.
    """
    try:
        resp = requests.get('https://apiv3.chargehub.com/trial/locations', timeout=10)
        resp.raise_for_status()
        # Pass through the JSON data
        return jsonify(resp.json())
    except Exception as e:
        logger.exception("Failed to fetch ChargeHub locations")
        return jsonify([]), 502

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# --- User Dashboard Endpoint (Mock) ---
@api_bp.route('/dashboard')
@login_required
def user_dashboard():
    """
    GET /api/dashboard
    - Description: Get user dashboard (bookings, payments, reviews)
    - Auth: Session required
    - Response: {"bookings": [...], "payments": [...], "reviews": [...]}
    """
    user_id = current_user.id
    # Mock bookings for this user
    user_bookings = [
        b for b in bookings_db if b["user_id"] == user_id
    ]
    # Mock payments for this user (simulate one per booking)
    user_payments = [
        {
            "payment_id": b["booking_id"],
            "booking_id": b["booking_id"],
            "amount": 1000,
            "currency": "usd",
            "status": "paid"
        }
        for b in user_bookings
    ]
    # Mock reviews for this user
    user_reviews = [
        r for r in reviews_db if r["user_id"] == user_id
    ]
    return jsonify({
        "bookings": user_bookings,
        "payments": user_payments,
        "reviews": user_reviews
    })

# In-memory mock for stations (per host)
stations_db = []
station_id_counter = [1]

# --- Host Station Management Endpoints ---
@api_bp.route('/host/stations', methods=['POST'])
@login_required
def create_station():
    """
    POST /api/host/stations
    - Description: Create a new charging station (host only)
    - Auth: Session required
    - Request: {"name": str, "lat": float, "lng": float, "address": str}
    - Response: Station object
    - Errors: 400 (missing data)
    """
    data = request.get_json() or {}
    required = ["name", "lat", "lng", "address"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing station data"}), 400
    sid = station_id_counter[0]
    station_id_counter[0] += 1
    station = {
        "station_id": sid,
        "host_id": current_user.id if hasattr(current_user, 'id') else 1,
        "name": data["name"],
        "lat": data["lat"],
        "lng": data["lng"],
        "address": data["address"]
    }
    stations_db.append(station)
    return jsonify(station), 201

@api_bp.route('/host/stations', methods=['GET'])
@login_required
def list_host_stations():
    """
    GET /api/host/stations
    - Description: List all stations for the current host
    - Auth: Session required
    - Response: {"stations": [...]}
    """
    host_id = current_user.id if hasattr(current_user, 'id') else 1
    host_stations = [s for s in stations_db if s["host_id"] == host_id]
    return jsonify({"stations": host_stations})

@api_bp.route('/host/stations/<int:station_id>', methods=['PUT'])
@login_required
def update_station(station_id):
    """
    PUT /api/host/stations/<station_id>
    - Description: Update a station (host only)
    - Auth: Session required
    - Request: Partial station object
    - Response: Updated station object
    - Errors: 404 (not found)
    """
    host_id = current_user.id if hasattr(current_user, 'id') else 1
    station = next((s for s in stations_db if s["station_id"] == station_id and s["host_id"] == host_id), None)
    if not station:
        return jsonify({"error": "Station not found"}), 404
    data = request.get_json() or {}
    for k in ["name", "lat", "lng", "address"]:
        if k in data:
            station[k] = data[k]
    return jsonify(station)

@api_bp.route('/host/stations/<int:station_id>', methods=['DELETE'])
@login_required
def delete_station(station_id):
    """
    DELETE /api/host/stations/<station_id>
    - Description: Delete a station (host only)
    - Auth: Session required
    - Response: 204 No Content
    - Errors: 404 (not found)
    """
    host_id = current_user.id if hasattr(current_user, 'id') else 1
    idx = next((i for i, s in enumerate(stations_db) if s["station_id"] == station_id and s["host_id"] == host_id), None)
    if idx is None:
        return jsonify({"error": "Station not found"}), 404
    stations_db.pop(idx)
    return '', 204

from datetime import datetime, timezone
bookings_db = []  # In-memory mock for bookings

# --- Booking Endpoints ---
@api_bp.route('/bookings/', methods=['POST'])
def create_booking():
    """
    POST /api/bookings/
    - Description: Create a new booking
    - Auth: None (should be session, see code)
    - Request: {"station_id": int, "user_id": int, "start_time": str, "end_time": str}
    - Response: {"booking_id": int, "status": "confirmed"}
    - Errors: 400 (missing/invalid), 409 (overlap)
    """
    data = request.get_json() or {}
    required = ["station_id", "user_id", "start_time", "end_time"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing booking data"}), 400
    try:
        start = datetime.fromisoformat(data["start_time"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(data["end_time"].replace("Z", "+00:00"))
    except Exception:
        return jsonify({"error": "Invalid date format"}), 400
    # Check for overlap
    for b in bookings_db:
        if b["station_id"] == data["station_id"] and not (end <= b["start_time"] or start >= b["end_time"]):
            return jsonify({"error": "Booking time overlaps with existing booking"}), 409
    booking_id = len(bookings_db) + 1
    booking = {
        "booking_id": booking_id,
        "station_id": data["station_id"],
        "user_id": data["user_id"],
        "start_time": start,
        "end_time": end,
        "status": "confirmed"
    }
    bookings_db.append(booking)
    return jsonify({"booking_id": booking_id, "status": "confirmed"}), 201

@api_bp.route('/stations/<int:station_id>/availability')
def station_availability(station_id):
    """
    GET /api/stations/<station_id>/availability?date=YYYY-MM-DD
    - Description: Get available booking slots for a station on a given date
    - Auth: None
    - Query: date (ISO string)
    - Response: {"available_slots": [{"start": str, "end": str}]}
    - Errors: 400 (missing/invalid date)
    """
    date_str = request.args.get("date")
    if not date_str:
        return jsonify({"error": "Missing date parameter"}), 400
    try:
        date = datetime.fromisoformat(date_str)
    except Exception:
        return jsonify({"error": "Invalid date format"}), 400
    # Mock: 8am-8pm, 1hr slots, remove slots with bookings
    slots = [
        (date.replace(hour=h, minute=0, second=0, microsecond=0, tzinfo=timezone.utc),
         date.replace(hour=h+1, minute=0, second=0, microsecond=0, tzinfo=timezone.utc))
        for h in range(8, 20)
    ]
    available = []
    for start, end in slots:
        overlap = False
        for b in bookings_db:
            if b["station_id"] == station_id and not (end <= b["start_time"] or start >= b["end_time"]):
                overlap = True
                break
        if not overlap:
            available.append({"start": start.isoformat(), "end": end.isoformat()})
    return jsonify({"available_slots": available})

@api_bp.route('/health')
def health_check():
    """
    GET /api/health
    - Description: API health check
    - Auth: None
    - Response: {"status": "healthy", "message": "evxchange API is running"}
    """
    return jsonify({'status': 'healthy', 'message': 'evxchange API is running'})


# --- Profile Endpoints ---
from models.user import User

@api_bp.route('/profile', methods=['GET', 'PUT'])
@login_required
def profile():
    """
    GET /api/profile: Get current user profile (all fields)
    PUT /api/profile: Update editable fields of current user profile
    - Editable fields: all columns except id, email, role, tier, created_at, updated_at, oauth ids
    - Returns: updated user object
    """
    user: User = current_user
    if request.method == 'GET':
        # Dynamically return all fields
        return jsonify(user.to_dict())

    # PUT: update editable fields
    data = request.get_json(force=True)
    # Get all column names from User model
    editable_fields = [
        c.name for c in User.__table__.columns
        if c.name not in ('id', 'email', 'role', 'tier', 'created_at', 'updated_at', 'google_id', 'facebook_id', 'linkedin_id')
    ]
    updated = False
    for field in editable_fields:
        if field in data:
            setattr(user, field, data[field])
            updated = True
    if updated:
        from app import db
        db.session.commit()
    return jsonify(user.to_dict())


# --- New endpoint: Nearby Charging Stations ---
@api_bp.route('/nearby_stations')
def nearby_stations():
    """
    GET /api/nearby_stations?lat=...&lng=...
    - Description: Return a list of nearby charging stations for given lat/lng
    - Auth: None
    - Query: lat, lng (float)
    - Response: {"stations": [...]}
    - Errors: 400 (invalid/missing lat/lng)
    """
    lat = request.args.get('lat')
    lng = request.args.get('lng')
    try:
        if lat is None or lng is None:
            raise ValueError("Missing lat/lng parameters")
        lat = float(lat)
        lng = float(lng)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid or missing lat/lng parameters"}), 400

    # Mock data for demonstration
    stations = [
        {
            "id": 1,
            "name": "evxchange Station Downtown",
            "lat": lat + 0.001,
            "lng": lng + 0.001,
            "address": "123 Main St, Cityville"
        },
        {
            "id": 2,
            "name": "evxchange Station Uptown",
            "lat": lat - 0.001,
            "lng": lng - 0.001,
            "address": "456 Oak Ave, Cityville"
        }
    ]
    return jsonify({"stations": stations})

# --- Stripe Payment Endpoints ---
@api_bp.route('/payments/checkout', methods=['POST'])
def create_checkout_session():
    """
    POST /api/payments/checkout
    - Description: Create a Stripe checkout session for a booking
    - Auth: None
    - Request: {"booking_id": int, "amount": int, "currency": str, "success_url": str, "cancel_url": str}
    - Response: {"checkout_url": str}
    - Errors: 400 (missing/invalid, Stripe error)
    """
    data = request.get_json() or {}
    required = ["booking_id", "amount", "currency", "success_url", "cancel_url"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing or invalid data"}), 400
    # In real use, set your Stripe secret key from env
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": data["currency"],
                    "product_data": {"name": f"Booking {data['booking_id']}"},
                    "unit_amount": data["amount"]
                },
                "quantity": 1
            }],
            mode="payment",
            success_url=data["success_url"],
            cancel_url=data["cancel_url"]
        )
        return jsonify({"checkout_url": session.url})
    except Exception as e:
        logger.exception("Error creating Stripe checkout session.")
        return jsonify({"error": "Failed to create checkout session."}), 400

@api_bp.route('/payments/webhook', methods=['POST'])
def stripe_webhook():
    """
    POST /api/payments/webhook
    - Description: Stripe webhook handler (for Stripe use only)
    - Auth: None
    - Request: Stripe event payload
    - Response: {"status": "success"}
    - Errors: 400 (invalid payload/signature)
    """
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature', '')
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_dummy")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except Exception as e:
        logger.exception("Error while processing Stripe webhook event.")
        return jsonify({"error": "Invalid payload or signature"}), 400
    # Handle event type
    if event["type"] == "checkout.session.completed":
        # Here you would update booking/payment status
        return jsonify({"status": "success"})
    return jsonify({"status": "ignored"})

# --- Ratings and Reviews (In-memory mock) ---
reviews_db = []
review_id_counter = [1]

@api_bp.route('/bookings/<int:booking_id>/review', methods=['POST'])
@login_required
def add_review(booking_id):
    """
    POST /api/bookings/<booking_id>/review
    - Description: Add a review for a booking
    - Auth: Session required
    - Request: {"rating": int, "review": str}
    - Response: Review object
    - Errors: 400 (missing), 409 (exists)
    """
    data = request.get_json() or {}
    if "rating" not in data or "review" not in data:
        return jsonify({"error": "Missing rating or review"}), 400
    # For test: allow any booking_id, but only one review per booking/user
    existing = next((r for r in reviews_db if r["booking_id"] == booking_id and r["user_id"] == current_user.id), None)
    if existing:
        return jsonify({"error": "Review already exists"}), 409
    rid = review_id_counter[0]
    review_id_counter[0] += 1
    review = {
        "review_id": rid,
        "booking_id": booking_id,
        "station_id": 1,  # For mock, always station 1
        "user_id": current_user.id,
        "rating": data["rating"],
        "review": data["review"]
    }
    reviews_db.append(review)
    return jsonify(review), 201

@api_bp.route('/stations/<int:station_id>/reviews', methods=['GET'])
def get_reviews_for_station(station_id):
    """
    GET /api/stations/<station_id>/reviews
    - Description: List reviews for a station
    - Auth: None
    - Response: {"reviews": [...]}
    """
    station_reviews = [r for r in reviews_db if r["station_id"] == station_id]
    return jsonify({"reviews": station_reviews})

@api_bp.route('/reviews/<int:review_id>', methods=['PUT'])
@login_required
def update_review(review_id):
    """
    PUT /api/reviews/<review_id>
    - Description: Update a review
    - Auth: Session required
    - Request: {"rating": int, "review": str}
    - Response: Review object
    - Errors: 404 (not found)
    """
    review = next((r for r in reviews_db if r["review_id"] == review_id and r["user_id"] == current_user.id), None)
    if not review:
        return jsonify({"error": "Review not found"}), 404
    data = request.get_json() or {}
    if "rating" in data:
        review["rating"] = data["rating"]
    if "review" in data:
        review["review"] = data["review"]
    return jsonify(review)

@api_bp.route('/reviews/<int:review_id>', methods=['DELETE'])
@login_required
def delete_review(review_id):
    """
    DELETE /api/reviews/<review_id>
    - Description: Delete a review
    - Auth: Session required
    - Response: 204 No Content
    - Errors: 404 (not found)
    """
    idx = next((i for i, r in enumerate(reviews_db) if r["review_id"] == review_id and r["user_id"] == current_user.id), None)
    if idx is None:
        return jsonify({"error": "Review not found"}), 404
    reviews_db.pop(idx)
    return '', 204

@api_bp.route('/reviews/<int:review_id>', methods=['GET'])
def get_review(review_id):
    """
    GET /api/reviews/<review_id>
    - Description: Get a single review
    - Auth: None
    - Response: Review object or 404
    """
    review = next((r for r in reviews_db if r["review_id"] == review_id), None)
    if not review:
        return jsonify({"error": "Review not found"}), 404
    return jsonify(review)

# --- Geolocation Endpoint (Mock) ---
@api_bp.route('/geolocation')
@login_required
def get_user_geolocation():
    """
    GET /api/geolocation
    - Description: Get current user's geolocation (mock)
    - Auth: Session required
    - Response: {"lat": float, "lng": float}
    """
    # In a real app, use IP or device info; here, return a fixed mock location
    return jsonify({"lat": 37.7749, "lng": -122.4194})