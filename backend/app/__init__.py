"""
Application factory for Flask app
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_cors import CORS
from flask_mail import Mail
from flask_socketio import SocketIO
from .config import config

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()
socketio = SocketIO()


def create_app(config_name='default'):
    """
    Application factory pattern
    
    Args:
        config_name: Configuration to use (development, production, testing)
    
    Returns:
        Flask application instance
    """
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    
    # Initialize CORS
    CORS(app, 
         origins=app.config['CORS_ORIGINS'],
         supports_credentials=True,
         allow_headers=['Content-Type', 'Authorization'],
         methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])
    
    # Initialize SocketIO
    socketio.init_app(app, 
                     cors_allowed_origins=app.config['CORS_ORIGINS'],
                     async_mode=app.config['SOCKETIO_ASYNC_MODE'],
                     message_queue=app.config.get('SOCKETIO_MESSAGE_QUEUE'))
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    
    # Register blueprints
    from .routes import auth, hotels, bookings, rooms, staff, payments, dashboard
    
    app.register_blueprint(auth.bp, url_prefix='/api/auth')
    app.register_blueprint(hotels.bp, url_prefix='/api/hotels')
    app.register_blueprint(bookings.bp, url_prefix='/api/bookings')
    app.register_blueprint(rooms.bp, url_prefix='/api/rooms')
    app.register_blueprint(staff.bp, url_prefix='/api/staff')
    app.register_blueprint(payments.bp, url_prefix='/api/payments')
    app.register_blueprint(dashboard.bp, url_prefix='/api/dashboard')
    
    # Register WebSocket events
    from .sockets import register_socket_events
    register_socket_events(socketio)
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'message': 'Hotel Management System API is running'}, 200
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Resource not found'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return {'error': 'Internal server error'}, 500
    
    return app
