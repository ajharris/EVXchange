import pytest
from flask import url_for
from models import user as user_model
from app import create_app
from dev_seed import seed_dev_data

@pytest.fixture(scope="module")
def test_client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        with app.app_context():
            seed_dev_data(app)
        yield client


def set_session_user(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)  # Flask-Login expects a string
        sess['_fresh'] = True

def test_admin_access_granted(test_client):
    # Simulate admin login by setting session
    from models.user import User
    with test_client.application.app_context():
        admin = User.query.filter_by(role='admin').first()
    set_session_user(test_client, admin.id)
    r = test_client.get("/api/admin/ping")
    assert r.status_code == 200
    assert r.json["message"] == "pong"

def test_non_admin_access_forbidden(test_client):
    # Simulate regular user login by setting session
    from models.user import User
    with test_client.application.app_context():
        user = User.query.filter_by(role='user').first()
    set_session_user(test_client, user.id)
    r = test_client.get("/api/admin/ping")
    assert r.status_code == 403
    assert "Forbidden" in r.json["error"]

def test_unauthenticated_access_denied(test_client):
    # No login
    r = test_client.get("/api/admin/ping")
    assert r.status_code == 401 or r.status_code == 403
