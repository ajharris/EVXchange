import os
import pytest
from models.user import User

@pytest.fixture(autouse=True)
def seed_users(app):
    # Import and run the seeder in the test app context
    from dev_seed import seed_dev_data
    seed_dev_data(app)

def test_admin_user_seeded(app):
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@evxchange.com')
    admin = User.query.filter_by(email=admin_email).first()
    assert admin is not None
    assert admin.role == 'admin'
    assert admin.name == 'Admin'

def test_regular_users_seeded(app):
    users = User.query.filter(User.role == 'user').all()
    emails = [u.email for u in users]
    assert 'alice.driver@example.com' in emails
    assert 'bob.owner@example.com' in emails
    assert 'charlie.both@example.com' in emails
    for user in users:
        assert user.role == 'user'
        assert user.is_verified is True
