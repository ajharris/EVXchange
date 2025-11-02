from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from app import db

class User(UserMixin, db.Model):
    """User model for authentication and profile management"""
    
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    avatar = db.Column(db.String(200))
    tier = db.Column(db.String(20), default='free')  # 'free' or 'pro'
    role = db.Column(db.String(20), default='user')  # 'user' or 'admin'
    
    # OAuth provider information
    google_id = db.Column(db.String(100), unique=True)
    facebook_id = db.Column(db.String(100), unique=True)
    linkedin_id = db.Column(db.String(100), unique=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    

    # User status
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)

    # Password hash for email login
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return self.password_hash and check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def to_dict(self):
        """Convert user object to dictionary"""
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'avatar': self.avatar,
            'tier': self.tier,
            'role': self.role,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def find_by_oauth_id(provider, oauth_id):
        """Find user by OAuth provider ID"""
        if provider == 'google':
            return User.query.filter_by(google_id=oauth_id).first()
        elif provider == 'facebook':
            return User.query.filter_by(facebook_id=oauth_id).first()
        elif provider == 'linkedin':
            return User.query.filter_by(linkedin_id=oauth_id).first()
        return None
    
    def set_oauth_id(self, provider, oauth_id):
        """Set OAuth provider ID"""
        if provider == 'google':
            self.google_id = oauth_id
        elif provider == 'facebook':
            self.facebook_id = oauth_id
        elif provider == 'linkedin':
            self.linkedin_id = oauth_id
