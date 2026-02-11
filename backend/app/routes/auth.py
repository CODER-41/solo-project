"""
Authentication routes
"""
from flask import Blueprint, request, jsonify
from app import db
from app.models.models import User, UserRole
from datetime import datetime, timedelta
import jwt
from functools import wraps
import os

bp = Blueprint('auth', __name__)

def create_token(user_id, token_type='access'):
    """Create JWT token"""
    if token_type == 'access':
        exp_delta = timedelta(hours=1)
    else:  # refresh token
        exp_delta = timedelta(days=30)
    
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + exp_delta,
        'iat': datetime.utcnow(),
        'type': token_type
    }
    
    return jwt.encode(
        payload,
        os.getenv('JWT_SECRET_KEY', 'dev-secret'),
        algorithm='HS256'
    )


def token_required(f):
    """Decorator to protect routes"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Get token from header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]  # Bearer <token>
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            # Decode token
            payload = jwt.decode(
                token,
                os.getenv('JWT_SECRET_KEY', 'dev-secret'),
                algorithms=['HS256']
            )
            
            current_user = User.query.get(payload['user_id'])
            if not current_user or not current_user.is_active:
                return jsonify({'error': 'Invalid user'}), 401
                
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated


def role_required(*roles):
    """Decorator to check user role"""
    def decorator(f):
        @wraps(f)
        def decorated(current_user, *args, **kwargs):
            if current_user.role.value not in [r.value for r in roles]:
                return jsonify({'error': 'Insufficient permissions'}), 403
            return f(current_user, *args, **kwargs)
        return decorated
    return decorator


@bp.route('/register', methods=['POST'])
def register():
    """Register new user (guest)"""
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['email', 'password', 'first_name', 'last_name']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400
    
    # Check if user exists
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 400
    
    try:
        # Create new user (default role is guest for public registration)
        user = User(
            email=data['email'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            phone=data.get('phone'),
            role=UserRole.FRONT_DESK  # Guests don't need login for Phase 1, this is for testing
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        # Create tokens
        access_token = create_token(user.id, 'access')
        refresh_token = create_token(user.id, 'refresh')
        
        return jsonify({
            'message': 'User registered successfully',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/login', methods=['POST'])
def login():
    """User login"""
    data = request.get_json()
    
    if not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password are required'}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid email or password'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account is inactive'}), 401
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Create tokens
    access_token = create_token(user.id, 'access')
    refresh_token = create_token(user.id, 'refresh')
    
    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(),
        'access_token': access_token,
        'refresh_token': refresh_token
    }), 200


@bp.route('/refresh', methods=['POST'])
def refresh():
    """Refresh access token"""
    data = request.get_json()
    refresh_token = data.get('refresh_token')
    
    if not refresh_token:
        return jsonify({'error': 'Refresh token is required'}), 400
    
    try:
        payload = jwt.decode(
            refresh_token,
            os.getenv('JWT_SECRET_KEY', 'dev-secret'),
            algorithms=['HS256']
        )
        
        if payload['type'] != 'refresh':
            return jsonify({'error': 'Invalid token type'}), 401
        
        user = User.query.get(payload['user_id'])
        if not user or not user.is_active:
            return jsonify({'error': 'Invalid user'}), 401
        
        # Create new access token
        access_token = create_token(user.id, 'access')
        
        return jsonify({
            'access_token': access_token
        }), 200
        
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Refresh token has expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid refresh token'}), 401


@bp.route('/me', methods=['GET'])
@token_required
def get_current_user(current_user):
    """Get current user info"""
    return jsonify(current_user.to_dict()), 200


@bp.route('/logout', methods=['POST'])
@token_required
def logout(current_user):
    """Logout user (client should delete tokens)"""
    # In a production app, you might want to blacklist the token
    return jsonify({'message': 'Logged out successfully'}), 200
