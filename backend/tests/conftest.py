import os
import tempfile
import pytest
from app import create_app, db
from models.user import User

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # Create a temporary file to isolate the database for each test
    db_fd, db_path = tempfile.mkstemp()
    
    app = create_app('testing')
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret-key",
        "GOOGLE_CLIENT_ID": "test-google-client-id",
        "GOOGLE_CLIENT_SECRET": "test-google-client-secret",
        "FACEBOOK_APP_ID": "test-facebook-app-id",
        "FACEBOOK_APP_SECRET": "test-facebook-app-secret",
        "LINKEDIN_CLIENT_ID": "test-linkedin-client-id",
        "LINKEDIN_CLIENT_SECRET": "test-linkedin-client-secret",
    })
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
    
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()

@pytest.fixture
def sample_user(app):
    """Create a sample user for testing."""
    with app.app_context():
        user = User(
            email="test@example.com",
            name="Test User",
            google_id="123456789",
            is_verified=True
        )
        db.session.add(user)
        db.session.commit()
        db.session.refresh(user)  # Ensure user is attached to session
        return user
