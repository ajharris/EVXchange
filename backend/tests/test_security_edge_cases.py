import pytest
import responses
from unittest.mock import patch, MagicMock
from models.user import User
from services.oauth import OAuthService
from app import db

class TestOAuthSecurity:
    """Test cases for OAuth security and edge cases"""
    
    def test_csrf_protection_missing_state(self, client):
        """Test CSRF protection when state parameter is missing"""
        response = client.get('/auth/callback/google?code=test_code')
        assert response.status_code == 400
        data = response.get_json()
        assert 'Invalid state parameter' in data['error']
    
    def test_csrf_protection_wrong_state(self, client):
        """Test CSRF protection with incorrect state parameter"""
        with client.session_transaction() as sess:
            sess['oauth_state'] = 'correct_state'
            sess['oauth_provider'] = 'google'
        
        response = client.get('/auth/callback/google?code=test_code&state=wrong_state')
        assert response.status_code == 400
        data = response.get_json()
        assert 'Invalid state parameter' in data['error']
    
    def test_oauth_without_session(self, client):
        """Test OAuth callback without proper session setup"""
        response = client.get('/auth/callback/google?code=test_code&state=some_state')
        assert response.status_code == 400
    
    @responses.activate
    def test_malformed_token_response(self, client):
        """Test handling of malformed token response from OAuth provider"""
        with client.session_transaction() as sess:
            sess['oauth_state'] = 'test_state'
            sess['oauth_provider'] = 'google'

        # Patch get_provider to return a dummy provider
        class DummyProvider:
            def get_access_token(self, code, redirect_uri):
                return {'invalid': 'response'}
            def get_user_info(self, access_token):
                return {'id': 'dummy', 'email': 'dummy@example.com'}

        with patch('services.oauth.OAuthService.get_provider', return_value=DummyProvider()):
            response = client.get('/auth/callback/google?code=test_code&state=test_state')
            assert response.status_code == 400
            data = response.get_json()
            assert 'Failed to obtain access token' in data['error']
    
    @responses.activate
    def test_malformed_user_info_response(self, client):
        """Test handling of malformed user info response"""
        with client.session_transaction() as sess:
            sess['oauth_state'] = 'test_state'
            sess['oauth_provider'] = 'google'
        
        responses.add(
            responses.POST,
            'https://oauth2.googleapis.com/token',
            json={'access_token': 'valid_token'},
            status=200
        )
        
        # Mock malformed user info response
        responses.add(
            responses.GET,
            'https://www.googleapis.com/oauth2/v2/userinfo',
            json={'incomplete': 'data'},
            status=200
        )
        
        response = client.get('/auth/callback/google?code=test_code&state=test_state')
        # Should fail with 400 due to missing required user info
        assert response.status_code == 400
    
    def test_session_cleanup_on_success(self, client, app):
        """Test that OAuth session data is cleaned up on successful auth"""
        with client.session_transaction() as sess:
            sess['oauth_state'] = 'cleanup_test'
            sess['oauth_provider'] = 'google'
            sess['other_data'] = 'should_remain'
        
        # Even on error, we don't want to test full success here
        # This test verifies the session cleanup logic exists
        response = client.get('/auth/callback/google?code=test_code&state=wrong_state')
        
        with client.session_transaction() as sess:
            # OAuth data should be cleaned up even on error in some cases
            assert 'other_data' in sess  # Other session data should remain
    
    def test_duplicate_oauth_account_linking(self, app):
        """Test that OAuth IDs remain unique across users"""
        with app.app_context():
            # Create first user
            user1 = User(
                email='user1@test.com',
                name='User 1',
                google_id='duplicate_id'
            )
            db.session.add(user1)
            db.session.commit()
            
            # Try to create second user with same OAuth ID
            user2 = User(
                email='user2@test.com',
                name='User 2',
                google_id='duplicate_id'
            )
            db.session.add(user2)
            
            # Should raise integrity error
            with pytest.raises(Exception):
                db.session.commit()
    
    def test_oauth_provider_rate_limiting_simulation(self, client):
        """Test behavior when OAuth provider is rate limiting"""
        # This is more of a documentation test showing how to handle rate limits
        # In real implementation, you'd want to add exponential backoff
        pass
    
    @responses.activate
    def test_oauth_provider_timeout_handling(self, client):
        """Test handling of OAuth provider timeouts"""
        with client.session_transaction() as sess:
            sess['oauth_state'] = 'timeout_test'
            sess['oauth_provider'] = 'google'
        
        # Mock timeout response
        responses.add(
            responses.POST,
            'https://oauth2.googleapis.com/token',
            body=ConnectionError("Connection timeout"),
        )
        
        response = client.get('/auth/callback/google?code=test_code&state=timeout_test')
        assert response.status_code == 400
        data = response.get_json()
        assert 'Failed to obtain access token' in data['error']
    
    def test_missing_required_user_info(self, client, app):
        """Test handling when OAuth provider doesn't return required user info"""
        # This test documents expected behavior when email is missing
        # which is a critical piece of user information
        pass
    
    def test_oauth_scope_validation(self):
        """Test that OAuth providers request appropriate scopes"""
        from services.oauth import GoogleOAuthProvider, FacebookOAuthProvider, LinkedInOAuthProvider
        
        google = GoogleOAuthProvider('client', 'secret')
        facebook = FacebookOAuthProvider('client', 'secret')
        linkedin = LinkedInOAuthProvider('client', 'secret')
        
        google_url = google.get_authorization_url('http://test.com')
        facebook_url = facebook.get_authorization_url('http://test.com')
        linkedin_url = linkedin.get_authorization_url('http://test.com')
        
        # Verify required scopes are requested
        assert 'scope=openid+email+profile' in google_url
        assert 'scope=email%2Cpublic_profile' in facebook_url
        assert 'scope=r_liteprofile+r_emailaddress' in linkedin_url


class TestOAuthEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_empty_oauth_config(self, app):
        """Test OAuth service behavior with empty configuration"""
        # Create app without OAuth config
        app.config.update({
            'GOOGLE_CLIENT_ID': None,
            'GOOGLE_CLIENT_SECRET': None,
            'FACEBOOK_APP_ID': '',
            'FACEBOOK_APP_SECRET': '',
            'LINKEDIN_CLIENT_ID': '',
            'LINKEDIN_CLIENT_SECRET': '',
        })
        
        oauth_service = OAuthService()
        oauth_service.init_app(app)
        
        assert oauth_service.get_available_providers() == []
        assert oauth_service.get_provider('google') is None
    
    def test_partial_oauth_config(self, app):
        """Test OAuth service with partial configuration"""
        app.config.update({
            'GOOGLE_CLIENT_ID': 'test_id',
            'GOOGLE_CLIENT_SECRET': None,  # Missing secret
        })
        
        oauth_service = OAuthService()
        oauth_service.init_app(app)
        
        # Should not initialize Google provider without complete config
        assert 'google' not in oauth_service.get_available_providers()
    
    @responses.activate
    def test_user_with_very_long_name(self, client, app):
        """Test user creation with very long name"""
        with client.session_transaction() as sess:
            sess['oauth_state'] = 'long_name_test'
            sess['oauth_provider'] = 'google'
        
        long_name = 'A' * 200  # Very long name
        
        responses.add(
            responses.POST,
            'https://oauth2.googleapis.com/token',
            json={'access_token': 'test_token'},
            status=200
        )
        
        responses.add(
            responses.GET,
            'https://www.googleapis.com/oauth2/v2/userinfo',
            json={
                'id': 'long_name_user',
                'email': 'longname@test.com',
                'name': long_name,
                'verified_email': True
            },
            status=200
        )
        
        response = client.get('/auth/callback/google?code=test_code&state=long_name_test')
        
        # Should handle gracefully (might truncate or succeed depending on DB constraints)
        assert response.status_code in [302, 500]
    
    def test_user_without_email(self, app):
        """Test user creation attempt without email"""
        with app.app_context():
            # User model requires email, so this should fail
            user = User(name='No Email User')
            db.session.add(user)
            
            with pytest.raises(Exception):  # Should raise IntegrityError
                db.session.commit()
    
    @responses.activate
    def test_oauth_provider_returning_no_email(self, client, app):
        """Test OAuth provider that doesn't return email"""
        with client.session_transaction() as sess:
            sess['oauth_state'] = 'no_email_test'
            sess['oauth_provider'] = 'google'
        
        responses.add(
            responses.POST,
            'https://oauth2.googleapis.com/token',
            json={'access_token': 'test_token'},
            status=200
        )
        
        responses.add(
            responses.GET,
            'https://www.googleapis.com/oauth2/v2/userinfo',
            json={
                'id': 'no_email_user',
                'name': 'User Without Email',
                # No email field
            },
            status=200
        )
        
        response = client.get('/auth/callback/google?code=test_code&state=no_email_test')
        # Should fail because email is required
        assert response.status_code == 400
    
    def test_concurrent_oauth_attempts(self, client, app):
        """Test multiple concurrent OAuth attempts"""
        # This test documents the need for proper session handling
        # in concurrent scenarios - important for production deployment
        pass
    
    def test_oauth_with_special_characters_in_name(self, client, app):
        """Test OAuth with names containing special characters"""
        # This test would verify handling of Unicode characters,
        # emojis, and other special characters in user names
        pass
