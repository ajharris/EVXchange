import pytest
from datetime import datetime
from models.user import User
from app import db

class TestUserModel:
    """Test cases for the User model"""
    
    def test_user_creation(self, app):
        """Test creating a new user"""
        with app.app_context():
            user = User(
                email="test@example.com",
                name="Test User",
                google_id="123456789"
            )
            db.session.add(user)
            db.session.commit()
            
            assert user.id is not None
            assert user.email == "test@example.com"
            assert user.name == "Test User"
            assert user.google_id == "123456789"
            assert user.is_active is True
            assert user.is_verified is False
            assert isinstance(user.created_at, datetime)
    
    def test_user_repr(self, app):
        """Test user string representation"""
        with app.app_context():
            user = User(email="test@example.com", name="Test User")
            assert repr(user) == '<User test@example.com>'
    
    def test_user_to_dict(self, app):
        """Test user to dictionary conversion"""
        with app.app_context():
            user = User(
                email="test@example.com",
                name="Test User",
                avatar="http://example.com/pic.jpg",
                is_verified=True
            )
            db.session.add(user)
            db.session.commit()
            
            user_dict = user.to_dict()
            expected_keys = {'id', 'email', 'name', 'avatar', 'is_verified', 'created_at', 'tier', 'role'}
            assert set(user_dict.keys()) == expected_keys
            assert user_dict['email'] == "test@example.com"
            assert user_dict['name'] == "Test User"
            assert user_dict['is_verified'] is True
    
    def test_find_by_oauth_id_google(self, app):
        """Test finding user by Google OAuth ID"""
        with app.app_context():
            user = User(
                email="test@example.com",
                name="Test User",
                google_id="google123"
            )
            db.session.add(user)
            db.session.commit()
            
            found_user = User.find_by_oauth_id('google', 'google123')
            assert found_user is not None
            assert found_user.email == "test@example.com"
            
            not_found = User.find_by_oauth_id('google', 'nonexistent')
            assert not_found is None
    
    def test_find_by_oauth_id_facebook(self, app):
        """Test finding user by Facebook OAuth ID"""
        with app.app_context():
            user = User(
                email="test@example.com",
                name="Test User",
                facebook_id="facebook123"
            )
            db.session.add(user)
            db.session.commit()
            
            found_user = User.find_by_oauth_id('facebook', 'facebook123')
            assert found_user is not None
            assert found_user.email == "test@example.com"
    
    def test_find_by_oauth_id_linkedin(self, app):
        """Test finding user by LinkedIn OAuth ID"""
        with app.app_context():
            user = User(
                email="test@example.com",
                name="Test User",
                linkedin_id="linkedin123"
            )
            db.session.add(user)
            db.session.commit()
            
            found_user = User.find_by_oauth_id('linkedin', 'linkedin123')
            assert found_user is not None
            assert found_user.email == "test@example.com"
    
    def test_find_by_oauth_id_invalid_provider(self, app):
        """Test finding user with invalid OAuth provider"""
        with app.app_context():
            found_user = User.find_by_oauth_id('invalid', 'some_id')
            assert found_user is None
    
    def test_set_oauth_id_google(self, app):
        """Test setting Google OAuth ID"""
        with app.app_context():
            user = User(email="test@example.com", name="Test User")
            user.set_oauth_id('google', 'google123')
            
            assert user.google_id == 'google123'
            assert user.facebook_id is None
            assert user.linkedin_id is None
    
    def test_set_oauth_id_facebook(self, app):
        """Test setting Facebook OAuth ID"""
        with app.app_context():
            user = User(email="test@example.com", name="Test User")
            user.set_oauth_id('facebook', 'facebook123')
            
            assert user.facebook_id == 'facebook123'
            assert user.google_id is None
            assert user.linkedin_id is None
    
    def test_set_oauth_id_linkedin(self, app):
        """Test setting LinkedIn OAuth ID"""
        with app.app_context():
            user = User(email="test@example.com", name="Test User")
            user.set_oauth_id('linkedin', 'linkedin123')
            
            assert user.linkedin_id == 'linkedin123'
            assert user.google_id is None
            assert user.facebook_id is None
    
    def test_unique_email_constraint(self, app):
        """Test that email uniqueness is enforced"""
        with app.app_context():
            user1 = User(email="test@example.com", name="User 1")
            user2 = User(email="test@example.com", name="User 2")
            
            db.session.add(user1)
            db.session.commit()
            
            db.session.add(user2)
            with pytest.raises(Exception):  # Should raise IntegrityError
                db.session.commit()
    
    def test_unique_oauth_ids(self, app):
        """Test that OAuth IDs are unique"""
        with app.app_context():
            user1 = User(email="user1@example.com", name="User 1", google_id="google123")
            user2 = User(email="user2@example.com", name="User 2", google_id="google123")
            
            db.session.add(user1)
            db.session.commit()
            
            db.session.add(user2)
            with pytest.raises(Exception):  # Should raise IntegrityError
                db.session.commit()
