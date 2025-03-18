from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_caching import Cache

from config import config

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
cache = Cache()

def create_app(config_name='default'):
    """
    Application factory function that creates and configures the Flask application.
    
    Args:
        config_name (str): The configuration to use ('development', 'testing', 'production')
        
    Returns:
        app (Flask): The configured Flask application instance
    """
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    migrate.init_app(app, db)
    cache.init_app(app)
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.search import search_bp
    from app.routes.api import api_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    
    # Register error handlers
    from flask import render_template
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()
    
    return app