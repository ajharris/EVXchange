
import pytest
from models.user import User



def create_user(email, role='user', is_verified=False):
    user = User(email=email, name='Test', role=role, is_verified=is_verified)
    from app import db
    db.session.add(user)
    db.session.commit()
    return user

def test_email_login_admin(client):
    create_user('admin@example.com', role='admin', is_verified=False)
    res = client.post('/auth/email-login', json={'email': 'admin@example.com'})
    if res.status_code == 405:
        # Print all routes for debugging
        print("\nAvailable routes:")
        for rule in client.application.url_map.iter_rules():
            print(rule)
    assert res.status_code == 200
    data = res.get_json()
    assert data['email'] == 'admin@example.com'
    assert data['role'] == 'admin'

def test_email_login_verified_user(client):
    create_user('user1@example.com', is_verified=True)
    res = client.post('/auth/email-login', json={'email': 'user1@example.com'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['email'] == 'user1@example.com'
    assert data['is_verified'] is True

def test_email_login_unverified_user(client):
    create_user('user2@example.com', is_verified=False)
    res = client.post('/auth/email-login', json={'email': 'user2@example.com'})
    assert res.status_code == 403
    data = res.get_json()
    assert 'not allowed' in data['error'].lower()

def test_email_login_no_user(client):
    res = client.post('/auth/email-login', json={'email': 'nouser@example.com'})
    assert res.status_code == 404
    data = res.get_json()
    assert 'no user' in data['error'].lower()
