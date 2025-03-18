from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager
import uuid

class User(UserMixin, db.Model):
    """User model for authentication and tracking usage."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    email = db.Column(db.String(120), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    api_key = db.Column(db.String(64), unique=True, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    searches = db.relationship('Search', backref='user', lazy='dynamic')
    
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        self.api_key = str(uuid.uuid4())
    
    @property
    def password(self):
        """Password getter to prevent direct access."""
        raise AttributeError('password is not a readable attribute')
    
    @password.setter
    def password(self, password):
        """Sets the password hash."""
        self.password_hash = generate_password_hash(password)
    
    def verify_password(self, password):
        """Verify the password against the stored hash."""
        return check_password_hash(self.password_hash, password)
    
    def generate_new_api_key(self):
        """Generate a new API key for the user."""
        self.api_key = str(uuid.uuid4())
        return self.api_key
    
    def __repr__(self):
        return f'<User {self.username}>'


class Domain(db.Model):
    """Model for storing domain information."""
    __tablename__ = 'domains'
    
    id = db.Column(db.Integer, primary_key=True)
    domain_name = db.Column(db.String(255), unique=True, index=True)
    company_name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    emails = db.relationship('Email', backref='domain', lazy='dynamic')
    
    def __repr__(self):
        return f'<Domain {self.domain_name}>'


class Email(db.Model):
    """Model for storing email information."""
    __tablename__ = 'emails'
    
    id = db.Column(db.Integer, primary_key=True)
    email_address = db.Column(db.String(255), unique=True, index=True)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    position = db.Column(db.String(255), nullable=True)
    confidence_score = db.Column(db.Float, default=0.0)  # 0.0 to 1.0
    is_verified = db.Column(db.Boolean, default=False)
    verification_date = db.Column(db.DateTime, nullable=True)
    domain_id = db.Column(db.Integer, db.ForeignKey('domains.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Email {self.email_address}>'


class Search(db.Model):
    """Model for tracking user searches."""
    __tablename__ = 'searches'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    query = db.Column(db.String(255))
    search_type = db.Column(db.String(50))  # 'domain', 'email', 'name', etc.
    results_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Search {self.query}>'


class EmailPattern(db.Model):
    """Model for storing common email patterns for domains."""
    __tablename__ = 'email_patterns'
    
    id = db.Column(db.Integer, primary_key=True)
    domain_id = db.Column(db.Integer, db.ForeignKey('domains.id'))
    pattern = db.Column(db.String(100))  # e.g., '{first}.{last}', '{first_initial}{last}'
    confidence = db.Column(db.Float, default=0.0)  # 0.0 to 1.0
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    domain = db.relationship('Domain', backref='email_patterns')
    
    def __repr__(self):
        return f'<EmailPattern {self.pattern} for {self.domain.domain_name}>'


# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    """Load a user by ID."""
    return User.query.get(int(user_id))