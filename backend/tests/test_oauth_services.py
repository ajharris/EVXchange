import pytest
import responses
import json
from unittest.mock import patch, MagicMock
from services.oauth import (
    GoogleOAuthProvider, 
    FacebookOAuthProvider, 
    LinkedInOAuthProvider,
    OAuthService
)

class TestGoogleOAuthProvider:
    """Test cases for Google OAuth provider"""
    
    def test_initialization(self):
        """Test Google OAuth provider initialization"""
        provider = GoogleOAuthProvider('client_id', 'client_secret')
        assert provider.name == 'google'
        assert provider.client_id == 'client_id'
        assert provider.client_secret == 'client_secret'
    
    def test_get_authorization_url(self):
        """Test Google authorization URL generation"""
        provider = GoogleOAuthProvider('client_id', 'client_secret')
        redirect_uri = 'http://localhost:5000/auth/google/callback'
        
        auth_url = provider.get_authorization_url(redirect_uri)
        
        assert 'accounts.google.com/o/oauth2/v2/auth' in auth_url
        assert 'client_id=client_id' in auth_url
        assert 'response_type=code' in auth_url
        assert 'scope=openid+email+profile' in auth_url
        assert f'redirect_uri={redirect_uri}' in auth_url.replace('%3A', ':').replace('%2F', '/')
    
    def test_get_authorization_url_with_state(self):
        """Test Google authorization URL generation with state"""
        provider = GoogleOAuthProvider('client_id', 'client_secret')
        redirect_uri = 'http://localhost:5000/auth/google/callback'
        state = 'test_state'
        
        auth_url = provider.get_authorization_url(redirect_uri, state)
        
        assert f'state={state}' in auth_url
    
    @responses.activate
    def test_get_access_token_success(self):
        """Test successful access token exchange"""
        provider = GoogleOAuthProvider('client_id', 'client_secret')
        
        # Mock the token endpoint response
        responses.add(
            responses.POST,
            'https://oauth2.googleapis.com/token',
            json={'access_token': 'test_access_token', 'token_type': 'Bearer'},
            status=200
        )
        
        redirect_uri = 'http://localhost:5000/auth/google/callback'
        token_data = provider.get_access_token('test_code', redirect_uri)
        
        assert token_data['access_token'] == 'test_access_token'
        assert len(responses.calls) == 1
        
        # Verify request data
        request_body = responses.calls[0].request.body
        assert 'client_id=client_id' in request_body
        assert 'client_secret=client_secret' in request_body
        assert 'code=test_code' in request_body
    
    @responses.activate
    def test_get_access_token_failure(self):
        """Test access token exchange failure"""
        provider = GoogleOAuthProvider('client_id', 'client_secret')
        
        # Mock failed token endpoint response
        responses.add(
            responses.POST,
            'https://oauth2.googleapis.com/token',
            json={'error': 'invalid_grant'},
            status=400
        )
        
        redirect_uri = 'http://localhost:5000/auth/google/callback'
        
        with pytest.raises(Exception):
            provider.get_access_token('invalid_code', redirect_uri)
    
    @responses.activate
    def test_get_user_info_success(self):
        """Test successful user info retrieval"""
        provider = GoogleOAuthProvider('client_id', 'client_secret')
        
        # Mock user info endpoint response
        mock_user_data = {
            'id': '123456789',
            'email': 'test@gmail.com',
            'name': 'Test User',
            'picture': 'https://example.com/picture.jpg',
            'verified_email': True
        }
        
        responses.add(
            responses.GET,
            'https://www.googleapis.com/oauth2/v2/userinfo',
            json=mock_user_data,
            status=200
        )
        
        user_info = provider.get_user_info('test_access_token')
        
        assert user_info['id'] == '123456789'
        assert user_info['email'] == 'test@gmail.com'
        assert user_info['name'] == 'Test User'
        assert user_info['picture'] == 'https://example.com/picture.jpg'
        assert user_info['verified_email'] is True
        
        # Verify authorization header
        request_headers = responses.calls[0].request.headers
        assert request_headers['Authorization'] == 'Bearer test_access_token'


class TestFacebookOAuthProvider:
    """Test cases for Facebook OAuth provider"""
    
    def test_initialization(self):
        """Test Facebook OAuth provider initialization"""
        provider = FacebookOAuthProvider('app_id', 'app_secret')
        assert provider.name == 'facebook'
        assert provider.client_id == 'app_id'
        assert provider.client_secret == 'app_secret'
    
    def test_get_authorization_url(self):
        """Test Facebook authorization URL generation"""
        provider = FacebookOAuthProvider('app_id', 'app_secret')
        redirect_uri = 'http://localhost:5000/auth/facebook/callback'
        
        auth_url = provider.get_authorization_url(redirect_uri)
        
        assert 'facebook.com/v18.0/dialog/oauth' in auth_url
        assert 'client_id=app_id' in auth_url
        assert 'response_type=code' in auth_url
        assert 'scope=email%2Cpublic_profile' in auth_url
    
    @responses.activate
    def test_get_access_token_success(self):
        """Test successful Facebook access token exchange"""
        provider = FacebookOAuthProvider('app_id', 'app_secret')
        
        responses.add(
            responses.GET,
            'https://graph.facebook.com/v18.0/oauth/access_token',
            json={'access_token': 'fb_access_token'},
            status=200
        )
        
        redirect_uri = 'http://localhost:5000/auth/facebook/callback'
        token_data = provider.get_access_token('test_code', redirect_uri)
        
        assert token_data['access_token'] == 'fb_access_token'
    
    @responses.activate
    def test_get_user_info_success(self):
        """Test successful Facebook user info retrieval"""
        provider = FacebookOAuthProvider('app_id', 'app_secret')
        
        mock_user_data = {
            'id': 'fb123456789',
            'name': 'Facebook User',
            'email': 'test@facebook.com',
            'picture': {
                'data': {
                    'url': 'https://facebook.com/picture.jpg'
                }
            }
        }
        
        responses.add(
            responses.GET,
            'https://graph.facebook.com/v18.0/me',
            json=mock_user_data,
            status=200
        )
        
        user_info = provider.get_user_info('fb_access_token')
        
        assert user_info['id'] == 'fb123456789'
        assert user_info['email'] == 'test@facebook.com'
        assert user_info['name'] == 'Facebook User'
        assert user_info['picture'] == 'https://facebook.com/picture.jpg'
        assert user_info['verified_email'] is True


class TestLinkedInOAuthProvider:
    """Test cases for LinkedIn OAuth provider"""
    
    def test_initialization(self):
        """Test LinkedIn OAuth provider initialization"""
        provider = LinkedInOAuthProvider('client_id', 'client_secret')
        assert provider.name == 'linkedin'
        assert provider.client_id == 'client_id'
        assert provider.client_secret == 'client_secret'
    
    def test_get_authorization_url(self):
        """Test LinkedIn authorization URL generation"""
        provider = LinkedInOAuthProvider('client_id', 'client_secret')
        redirect_uri = 'http://localhost:5000/auth/linkedin/callback'
        
        auth_url = provider.get_authorization_url(redirect_uri)
        
        assert 'linkedin.com/oauth/v2/authorization' in auth_url
        assert 'client_id=client_id' in auth_url
        assert 'response_type=code' in auth_url
        assert 'scope=r_liteprofile+r_emailaddress' in auth_url
    
    @responses.activate
    def test_get_access_token_success(self):
        """Test successful LinkedIn access token exchange"""
        provider = LinkedInOAuthProvider('client_id', 'client_secret')
        
        responses.add(
            responses.POST,
            'https://www.linkedin.com/oauth/v2/accessToken',
            json={'access_token': 'linkedin_access_token'},
            status=200
        )
        
        redirect_uri = 'http://localhost:5000/auth/linkedin/callback'
        token_data = provider.get_access_token('test_code', redirect_uri)
        
        assert token_data['access_token'] == 'linkedin_access_token'
    
    @responses.activate
    def test_get_user_info_success(self):
        """Test successful LinkedIn user info retrieval"""
        provider = LinkedInOAuthProvider('client_id', 'client_secret')
        
        # Mock profile response
        profile_data = {
            'id': 'linkedin123',
            'firstName': {'localized': {'en_US': 'John'}},
            'lastName': {'localized': {'en_US': 'Doe'}},
            'profilePicture': {
                'displayImage~': {
                    'elements': [{
                        'identifiers': [{'identifier': 'https://linkedin.com/pic.jpg'}]
                    }]
                }
            }
        }
        
        # Mock email response
        email_data = {
            'elements': [{
                'handle~': {'emailAddress': 'john.doe@linkedin.com'}
            }]
        }
        
        responses.add(
            responses.GET,
            'https://api.linkedin.com/v2/people/~',
            json=profile_data,
            status=200
        )
        
        responses.add(
            responses.GET,
            'https://api.linkedin.com/v2/emailAddresses',
            json=email_data,
            status=200
        )
        
        user_info = provider.get_user_info('linkedin_access_token')
        
        assert user_info['id'] == 'linkedin123'
        assert user_info['name'] == 'John Doe'
        assert user_info['email'] == 'john.doe@linkedin.com'
        assert user_info['picture'] == 'https://linkedin.com/pic.jpg'
        assert user_info['verified_email'] is True


class TestOAuthService:
    """Test cases for OAuth service"""
    
    def test_initialization(self):
        """Test OAuth service initialization"""
        service = OAuthService()
        assert service.providers == {}
    
    def test_init_app(self, app):
        """Test OAuth service app initialization"""
        service = OAuthService()
        service.init_app(app)
        
        assert 'google' in service.providers
        assert 'facebook' in service.providers
        assert 'linkedin' in service.providers
        
        assert isinstance(service.providers['google'], GoogleOAuthProvider)
        assert isinstance(service.providers['facebook'], FacebookOAuthProvider)
        assert isinstance(service.providers['linkedin'], LinkedInOAuthProvider)
    
    def test_get_provider(self, app):
        """Test getting OAuth provider by name"""
        service = OAuthService()
        service.init_app(app)
        
        google_provider = service.get_provider('google')
        assert isinstance(google_provider, GoogleOAuthProvider)
        
        invalid_provider = service.get_provider('invalid')
        assert invalid_provider is None
    
    def test_get_available_providers(self, app):
        """Test getting list of available providers"""
        service = OAuthService()
        service.init_app(app)
        
        providers = service.get_available_providers()
        assert 'google' in providers
        assert 'facebook' in providers
        assert 'linkedin' in providers
        assert len(providers) == 3
    
    def test_init_app_missing_config(self):
        """Test OAuth service with missing configuration"""
        from flask import Flask
        
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test'
        # No OAuth configs
        
        service = OAuthService()
        service.init_app(app)
        
        assert service.providers == {}
        assert service.get_available_providers() == []
