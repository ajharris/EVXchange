

import os
import secrets
from flask import Blueprint, request, redirect, url_for, session, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from models.user import User
from services.oauth import OAuthService
from app import db

auth_bp = Blueprint('auth', __name__)
oauth_service = OAuthService()

# Set password after OAuth verification
@auth_bp.route('/set-password', methods=['POST'])
@login_required
def set_password():
    """
    POST /auth/set-password
    - Description: Set a password for email login after OAuth verification.
    - Request: {"password": "..."}
    - Auth: User must be logged in via OAuth
    - Response: {"message": "Password set successfully"}
    """
    data = request.get_json()
    if not data or 'password' not in data:
        return jsonify({'error': 'Password required'}), 400
    password = data['password']
    current_user.set_password(password)
    db.session.commit()
    return jsonify({'message': 'Password set successfully'})

# Email login route (must be after auth_bp is defined)
@auth_bp.route('/email-login', methods=['POST'])
def email_login():
    """
    POST /auth/email-login
    - Description: Login by email only (no password).
    - Only allows:
        * Admin user (role='admin')
        * Any user who is_verified=True (i.e., has previously verified via OAuth)
    - Request: {"email": "..."}
    - Response: User object (id, email, name, avatar, is_verified, role)
    """
    data = request.get_json()
    if not data or 'email' not in data:
        return jsonify({'error': 'Email required'}), 400
    email = data['email'].strip().lower()
    password = data.get('password')
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'No user found with that email'}), 404

    # Only allow admin or previously verified users
    if user.role == 'admin' or user.is_verified:
        # If user is already authenticated via OAuth (session), allow login without password
        oauth_logged_in = False
        if session.get('_user_id') and session.get('role') == user.role:
            oauth_logged_in = True
        # If not logged in, require password if user has a password set
        if not oauth_logged_in:
            if user.password_hash:
                if not password:
                    return jsonify({'error': 'Password required'}), 400
                if not user.check_password(password):
                    return jsonify({'error': 'Invalid password'}), 403
        login_user(user)
        session['role'] = user.role
        return jsonify(user.to_dict())
    return jsonify({'error': 'Email login not allowed for this user. Please login with OAuth first.'}), 403


# Provider-less login route for Flask-Login redirects
@auth_bp.route('/login')
def login():
    """Generic login route for Flask-Login redirects (no provider required)."""
    # If you have a login page, render it here. For API, return JSON error.
    if request.accept_mimetypes.accept_json:
        return jsonify({"error": "Authentication required", "providers": ["google", "facebook", "linkedin"]}), 401
    return "<h1>Authentication required</h1><p>Please login with one of the supported OAuth providers.</p>", 401

@auth_bp.record
def record_auth(setup_state):
    """Initialize OAuth service when blueprint is registered"""
    oauth_service.init_app(setup_state.app)

@auth_bp.route('/login/<provider>')
def oauth_login(provider):
    """Initiate OAuth login for the specified provider"""
    oauth_provider = oauth_service.get_provider(provider)
    if not oauth_provider:
        return jsonify({'error': 'Unsupported OAuth provider'}), 400
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session['oauth_provider'] = provider
    
    # Build redirect URI
    redirect_uri = url_for('auth.oauth_callback', provider=provider, _external=True)
    
    # Get authorization URL
    auth_url = oauth_provider.get_authorization_url(redirect_uri, state)
    
    return redirect(auth_url)

@auth_bp.route('/callback/<provider>')
def oauth_callback(provider):
    """Handle OAuth callback"""
    oauth_provider = oauth_service.get_provider(provider)
    if not oauth_provider:
        return jsonify({'error': 'Unsupported OAuth provider'}), 400
    
    # Verify state for CSRF protection
    state = request.args.get('state')
    if not state or state != session.get('oauth_state'):
        return jsonify({'error': 'Invalid state parameter'}), 400
    
    if request.args.get('error'):
        return jsonify({'error': f'OAuth error: {request.args.get("error")}'}), 400
    
    code = request.args.get('code')
    if not code:
        return jsonify({'error': 'Authorization code not provided'}), 400
    
    try:
        # Exchange code for access token
        redirect_uri = url_for('auth.oauth_callback', provider=provider, _external=True)
        try:
            token_data = oauth_provider.get_access_token(code, redirect_uri)
        except Exception as e:
            current_app.logger.error(f'OAuth token exchange error: {str(e)}')
            return jsonify({'error': 'Failed to obtain access token'}), 400
        access_token = None
        if isinstance(token_data, dict):
            access_token = token_data.get('access_token')
        if not access_token:
            return jsonify({'error': 'Failed to obtain access token'}), 400
        
        # Get user info
        user_info = oauth_provider.get_user_info(access_token)
        # Require email in user info
        if not user_info.get('email'):
            return jsonify({'error': 'Email is required from OAuth provider'}), 400
        # Find or create user
        user = User.find_by_oauth_id(provider, user_info['id'])
        
        if user:
            # Update existing user info
            user.name = user_info.get('name', user.name)
            user.avatar = user_info.get('picture', user.avatar)
            if user_info.get('verified_email'):
                user.is_verified = True
        else:
            # Check if user exists with same email
            existing_user = User.query.filter_by(email=user_info.get('email')).first()
            if existing_user:
                # Link OAuth account to existing user
                existing_user.set_oauth_id(provider, user_info['id'])
                existing_user.name = user_info.get('name', existing_user.name)
                existing_user.avatar = user_info.get('picture', existing_user.avatar)
                if user_info.get('verified_email'):
                    existing_user.is_verified = True
                user = existing_user
            else:
                # Create new user
                user = User(
                    email=user_info.get('email'),
                    name=user_info.get('name', ''),
                    avatar=user_info.get('picture'),
                    is_verified=user_info.get('verified_email', False)
                )
                user.set_oauth_id(provider, user_info['id'])
                db.session.add(user)
        
        db.session.commit()
        
        # Log in user
        login_user(user)
        # Store role in session for frontend use
        session['role'] = user.role
        # Clean up session
        session.pop('oauth_state', None)
        session.pop('oauth_provider', None)
        # Redirect to frontend or return success
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        return redirect(f'{frontend_url}/dashboard')
    except Exception as e:
        current_app.logger.error(f'OAuth callback error: {str(e)}')
        return jsonify({'error': 'Authentication failed'}), 500

@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """
    POST /auth/logout
    - Description: Log out the current user.
    - Auth: Session required
    - Response: {"message": "Logged out successfully"}
    """
    logout_user()
    return jsonify({'message': 'Logged out successfully'})

@auth_bp.route('/user')
@login_required
def get_current_user():
    """
    GET /auth/user
    - Description: Get current user information.
    - Auth: Session required
    - Response: User object (id, email, name, avatar, is_verified)
    """
    # Add role to response for clarity
    user_dict = current_user.to_dict()
    user_dict['role'] = current_user.role
    return jsonify(user_dict)

@auth_bp.route('/providers')
def get_oauth_providers():
    """
    GET /auth/providers
    - Description: Get available OAuth providers and their login URLs.
    - Auth: None
    - Response: {"providers": [{"name": ..., "login_url": ...}]}
    """
    providers = oauth_service.get_available_providers()
    provider_info = []
    
    for provider in providers:
        provider_info.append({
            'name': provider,
            'login_url': url_for('auth.oauth_login', provider=provider, _external=True)
        })
    
    return jsonify({'providers': provider_info})
