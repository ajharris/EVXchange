import pytest
import responses
from models.user import User
from app import db

class TestOAuthIntegration:
    """Integration tests for OAuth authentication flow"""
    
    @responses.activate
    def test_complete_google_oauth_flow(self, client, app):
        """Test complete Google OAuth authentication flow"""
        # Step 1: Initiate OAuth login
        response = client.get('/auth/login/google')
        assert response.status_code == 302
        
        # Verify session state was set
        with client.session_transaction() as sess:
            oauth_state = sess.get('oauth_state')
            assert oauth_state is not None
        
        # Step 2: Mock OAuth callback
        responses.add(
            responses.POST,
            'https://oauth2.googleapis.com/token',
            json={'access_token': 'integration_test_token'},
            status=200
        )
        
        responses.add(
            responses.GET,
            'https://www.googleapis.com/oauth2/v2/userinfo',
            json={
                'id': 'integration_google_123',
                'email': 'integration@test.com',
                'name': 'Integration Test User',
                'picture': 'https://example.com/integration.jpg',
                'verified_email': True
            },
            status=200
        )
        
        # Step 3: Complete OAuth callback
        callback_response = client.get(f'/auth/callback/google?code=test_code&state={oauth_state}')
        assert callback_response.status_code == 302
        
        # Step 4: Verify user was created and is logged in
        with app.app_context():
            user = User.query.filter_by(email='integration@test.com').first()
            assert user is not None
            assert user.google_id == 'integration_google_123'
            assert user.is_verified is True
        
        # Step 5: Test authenticated endpoint
        user_response = client.get('/auth/user')
        assert user_response.status_code == 200
        user_data = user_response.get_json()
        assert user_data['email'] == 'integration@test.com'
    
    @responses.activate  
    def test_multiple_provider_linking(self, client, app):
        """Test linking multiple OAuth providers to same user"""
        # Create user with Google
        with app.app_context():
            user = User(
                email='multi@test.com',
                name='Multi Provider User',
                google_id='google_multi_123'
            )
            db.session.add(user)
            db.session.commit()
            user_id = user.id
        
        # Login with Google first
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_id)
            sess['_fresh'] = True
        
        # Now try to link Facebook
        facebook_response = client.get('/auth/login/facebook')
        assert facebook_response.status_code == 302
        
        with client.session_transaction() as sess:
            facebook_state = sess.get('oauth_state')
        
        # Mock Facebook OAuth
        responses.add(
            responses.GET,
            'https://graph.facebook.com/v18.0/oauth/access_token',
            json={'access_token': 'facebook_token'},
            status=200
        )
        
        responses.add(
            responses.GET,
            'https://graph.facebook.com/v18.0/me',
            json={
                'id': 'facebook_multi_123',
                'email': 'multi@test.com',  # Same email
                'name': 'Multi Provider User',
                'picture': {'data': {'url': 'https://facebook.com/pic.jpg'}}
            },
            status=200
        )
        
        # Complete Facebook OAuth
        fb_callback = client.get(f'/auth/callback/facebook?code=fb_code&state={facebook_state}')
        assert fb_callback.status_code == 302
        
        # Verify both providers are linked
        with app.app_context():
            user = User.query.get(user_id)
            assert user.google_id == 'google_multi_123'
            assert user.facebook_id == 'facebook_multi_123'
    
    def test_oauth_providers_endpoint(self, client):
        """Test OAuth providers information endpoint"""
        response = client.get('/auth/providers')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'providers' in data
        
        providers = {p['name']: p for p in data['providers']}
        assert 'google' in providers
        assert 'facebook' in providers  
        assert 'linkedin' in providers
        
        # Verify each provider has required fields
        for provider_name, provider_info in providers.items():
            assert 'login_url' in provider_info
            assert f'/auth/login/{provider_name}' in provider_info['login_url']
    
    def test_api_health_check(self, client):
        """Test API health check endpoint"""
        response = client.get('/api/health')
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'healthy'
        assert 'evxchange API' in data['message']
    
    def test_api_profile_requires_auth(self, client):
        """Test that API profile endpoint requires authentication"""
        response = client.get('/api/profile')
        assert response.status_code == 401
    
    def test_api_profile_with_auth(self, client, app, sample_user):
        """Test API profile endpoint with authentication"""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(sample_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/profile')
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['email'] == sample_user.email
        assert data['name'] == sample_user.name
    
    @responses.activate
    def test_oauth_error_handling(self, client, app):
        """Test OAuth error handling scenarios"""
        # Test token exchange failure
        with client.session_transaction() as sess:
            sess['oauth_state'] = 'error_test_state'
            sess['oauth_provider'] = 'google'
        
        responses.add(
            responses.POST,
            'https://oauth2.googleapis.com/token',
            json={'error': 'invalid_grant'},
            status=400
        )
        
        response = client.get('/auth/callback/google?code=bad_code&state=error_test_state')
        assert response.status_code == 400
        data = response.get_json()
        assert 'Failed to obtain access token' in data['error']
    
    @responses.activate
    def test_user_info_failure_handling(self, client, app):
        """Test handling of user info API failures"""
        with client.session_transaction() as sess:
            sess['oauth_state'] = 'userinfo_test_state'
            sess['oauth_provider'] = 'google'
        
        # Token exchange succeeds
        responses.add(
            responses.POST,
            'https://oauth2.googleapis.com/token',
            json={'access_token': 'valid_token'},
            status=200
        )
        
        # User info fails
        responses.add(
            responses.GET,
            'https://www.googleapis.com/oauth2/v2/userinfo',
            json={'error': 'invalid_token'},
            status=401
        )
        
        response = client.get('/auth/callback/google?code=test_code&state=userinfo_test_state')
        assert response.status_code == 500
        data = response.get_json()
        assert 'Authentication failed' in data['error']
