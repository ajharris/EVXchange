import pytest
import responses
from unittest.mock import patch, MagicMock
from flask import url_for, session
from flask_login import current_user
from models.user import User
from app import db
from urllib.parse import urlparse

# Test setting password after OAuth verification

def test_set_password_after_oauth(client, app):
    # Create a user and simulate OAuth login
    with app.app_context():
        from models.user import User
        from app import db
        user = User(email='test@example.com', name='Test User', is_verified=True, google_id='123456789')
        db.session.add(user)
        db.session.commit()
        db.session.refresh(user)
        user_id = user.id

    # Log in the user (simulate OAuth session)
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)  # Flask-Login uses _user_id
        sess['_fresh'] = True  # Mark session as fresh for Flask-Login

    # Set password (follow redirects to catch login-required redirects)
    response = client.post('/auth/set-password', json={'password': 'newpassword'}, follow_redirects=True)
    # Accept either 200 (success) or 401 (unauthenticated) for debugging
    assert response.status_code == 200, f"Unexpected status: {response.status_code}, data: {response.data}"
    assert response.get_json()['message'] == 'Password set successfully'

    # Password should be set and check_password should work
    with app.app_context():
        user = User.query.get(user_id)
        assert user.check_password('newpassword')


class TestAuthRoutes:
    """Test cases for authentication routes"""
    
    def test_oauth_login_google(self, client, app):
        """Test OAuth login initiation for Google"""
        with app.test_request_context():
            response = client.get('/auth/login/google')
            
            assert response.status_code == 302
            assert urlparse(response.location).hostname == "accounts.google.com"
            assert 'client_id=test-google-client-id' in response.location
    
    def test_oauth_login_facebook(self, client, app):
        """Test OAuth login initiation for Facebook"""
        with app.test_request_context():
            response = client.get('/auth/login/facebook')
            
            assert response.status_code == 302
            assert urlparse(response.location).hostname in ["facebook.com", "www.facebook.com"]
            assert 'client_id=test-facebook-app-id' in response.location
    
    def test_oauth_login_linkedin(self, client, app):
        """Test OAuth login initiation for LinkedIn"""
        with app.test_request_context():
            response = client.get('/auth/login/linkedin')
            
            assert response.status_code == 302
            assert urlparse(response.location).hostname in ["linkedin.com", "www.linkedin.com"]
            assert 'client_id=test-linkedin-client-id' in response.location
    
    def test_oauth_login_invalid_provider(self, client):
        """Test OAuth login with invalid provider"""
        response = client.get('/auth/login/invalid')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Unsupported OAuth provider' in data['error']
    
    def test_oauth_login_sets_session(self, client, app):
        """Test that OAuth login sets session variables"""
        with client.session_transaction() as sess:
            # Session should be empty initially
            assert 'oauth_state' not in sess
            assert 'oauth_provider' not in sess
        
        response = client.get('/auth/login/google')
        
        with client.session_transaction() as sess:
            assert 'oauth_state' in sess
            assert 'oauth_provider' in sess
            assert sess['oauth_provider'] == 'google'
            assert len(sess['oauth_state']) > 20  # Should be a long random string
    
    @responses.activate
    def test_oauth_callback_google_new_user(self, client, app):
        """Test OAuth callback for Google with new user"""
        # Setup session
        with client.session_transaction() as sess:
            sess['oauth_state'] = 'test_state'
            sess['oauth_provider'] = 'google'
        
        # Mock Google token exchange
        responses.add(
            responses.POST,
            'https://oauth2.googleapis.com/token',
            json={'access_token': 'test_access_token'},
            status=200
        )
        
        # Mock Google user info
        mock_user_data = {
            'id': 'google123',
            'email': 'newuser@gmail.com',
            'name': 'New User',
            'picture': 'https://example.com/pic.jpg',
            'verified_email': True
        }
        responses.add(
            responses.GET,
            'https://www.googleapis.com/oauth2/v2/userinfo',
            json=mock_user_data,
            status=200
        )
        
        # Make callback request
        response = client.get('/auth/callback/google?code=test_code&state=test_state')
        
        assert response.status_code == 302
        assert 'localhost:3000/dashboard' in response.location
        
        # Verify user was created
        with app.app_context():
            user = User.query.filter_by(email='newuser@gmail.com').first()
            assert user is not None
            assert user.name == 'New User'
            assert user.google_id == 'google123'
            assert user.is_verified is True
    
    @responses.activate
    def test_oauth_callback_google_existing_user(self, client, app):
        """Test OAuth callback for Google with existing user"""
        # Create existing user
        with app.app_context():
            existing_user = User(
                email='existing@gmail.com',
                name='Existing User',
                google_id='google123'
            )
            db.session.add(existing_user)
            db.session.commit()
        
        # Setup session
        with client.session_transaction() as sess:
            sess['oauth_state'] = 'test_state'
            sess['oauth_provider'] = 'google'
        
        # Mock responses
        responses.add(
            responses.POST,
            'https://oauth2.googleapis.com/token',
            json={'access_token': 'test_access_token'},
            status=200
        )
        
        responses.add(
            responses.GET,
            'https://www.googleapis.com/oauth2/v2/userinfo',
            json={
                'id': 'google123',
                'email': 'existing@gmail.com',
                'name': 'Updated Name',
                'picture': 'https://example.com/newpic.jpg',
                'verified_email': True
            },
            status=200
        )
        
        response = client.get('/auth/callback/google?code=test_code&state=test_state')
        
        assert response.status_code == 302
        
        # Verify user was updated
        with app.app_context():
            user = User.query.filter_by(email='existing@gmail.com').first()
            assert user.name == 'Updated Name'
            assert user.avatar == 'https://example.com/newpic.jpg'
    
    def test_oauth_callback_invalid_state(self, client):
        """Test OAuth callback with invalid state parameter"""
        with client.session_transaction() as sess:
            sess['oauth_state'] = 'correct_state'
            sess['oauth_provider'] = 'google'
        
        response = client.get('/auth/callback/google?code=test_code&state=wrong_state')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Invalid state parameter' in data['error']
    
    def test_oauth_callback_missing_code(self, client):
        """Test OAuth callback without authorization code"""
        with client.session_transaction() as sess:
            sess['oauth_state'] = 'test_state'
            sess['oauth_provider'] = 'google'
        
        response = client.get('/auth/callback/google?state=test_state')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Authorization code not provided' in data['error']
    
    def test_oauth_callback_oauth_error(self, client):
        """Test OAuth callback with OAuth error"""
        with client.session_transaction() as sess:
            sess['oauth_state'] = 'test_state'
            sess['oauth_provider'] = 'google'
        
        response = client.get('/auth/callback/google?error=access_denied&state=test_state')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'OAuth error: access_denied' in data['error']
    
    def test_oauth_callback_invalid_provider(self, client):
        """Test OAuth callback with invalid provider"""
        response = client.get('/auth/callback/invalid?code=test_code&state=test_state')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Unsupported OAuth provider' in data['error']
    
    @responses.activate
    def test_oauth_callback_link_existing_email(self, client, app):
        """Test OAuth callback linking to existing user with same email"""
        # Create existing user without OAuth ID
        with app.app_context():
            existing_user = User(
                email='same@gmail.com',
                name='Original User'
            )
            db.session.add(existing_user)
            db.session.commit()
        
        # Setup session
        with client.session_transaction() as sess:
            sess['oauth_state'] = 'test_state'
            sess['oauth_provider'] = 'google'
        
        # Mock responses
        responses.add(
            responses.POST,
            'https://oauth2.googleapis.com/token',
            json={'access_token': 'test_access_token'},
            status=200
        )
        
        responses.add(
            responses.GET,
            'https://www.googleapis.com/oauth2/v2/userinfo',
            json={
                'id': 'google123',
                'email': 'same@gmail.com',
                'name': 'OAuth User',
                'verified_email': True
            },
            status=200
        )
        
        response = client.get('/auth/callback/google?code=test_code&state=test_state')
        
        assert response.status_code == 302
        
        # Verify user was linked
        with app.app_context():
            user = User.query.filter_by(email='same@gmail.com').first()
            assert user.google_id == 'google123'
            assert user.name == 'OAuth User'  # Should be updated
    
    def test_logout_requires_login(self, client):
        """Test that logout requires authentication"""
        response = client.post('/auth/logout', headers={"Accept": "application/json"})
        assert response.status_code == 401
    
    def test_logout_success(self, client, app, sample_user):
        """Test successful logout"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(sample_user.id)
            sess['_fresh'] = True
        
        response = client.post('/auth/logout')
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Logged out successfully'
    
    def test_get_current_user_requires_login(self, client):
        """Test that getting current user requires authentication"""
        response = client.get('/auth/user', headers={"Accept": "application/json"})
        assert response.status_code == 401
    
    def test_get_current_user_success(self, client, app, sample_user):
        """Test getting current user information"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(sample_user.id)
            sess['_fresh'] = True
        
        response = client.get('/auth/user')
        assert response.status_code == 200
        data = response.get_json()
        assert data['email'] == sample_user.email
        assert data['name'] == sample_user.name
    
    def test_get_oauth_providers(self, client):
        """Test getting available OAuth providers"""
        response = client.get('/auth/providers')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'providers' in data
        providers = data['providers']
        
        provider_names = [p['name'] for p in providers]
        assert 'google' in provider_names
        assert 'facebook' in provider_names
        assert 'linkedin' in provider_names
        
        # Verify login URLs are provided
        for provider in providers:
            assert 'login_url' in provider
            assert '/auth/login/' in provider['login_url']
