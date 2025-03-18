from flask import Blueprint, jsonify, request, current_app, g
from flask_restful import Api, Resource, reqparse, fields, marshal_with
from functools import wraps
import validators
import tldextract
from datetime import datetime, timedelta

from app import db
from app.models import User, Domain, Email, Search
from app.services.email_finder import EmailFinder
from app.services.email_verifier import EmailVerifier

api_bp = Blueprint('api', __name__)
api = Api(api_bp)

# API Authentication decorator
def api_key_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return {'message': 'API key is missing'}, 401
        
        user = User.query.filter_by(api_key=api_key).first()
        if not user:
            return {'message': 'Invalid API key'}, 401
        
        # Check rate limits
        today = datetime.utcnow().date()
        midnight = datetime.combine(today, datetime.min.time())
        
        # Count today's searches
        search_count = Search.query.filter(
            Search.user_id == user.id,
            Search.created_at >= midnight
        ).count()
        
        if search_count >= current_app.config['MAX_REQUESTS_PER_DAY']:
            return {'message': 'Rate limit exceeded'}, 429
        
        # Set user for this request
        g.user = user
        return f(*args, **kwargs)
    return decorated

# Resource fields for marshalling
email_fields = {
    'email_address': fields.String,
    'first_name': fields.String,
    'last_name': fields.String,
    'position': fields.String,
    'confidence_score': fields.Float,
    'is_verified': fields.Boolean
}

# Parser for domain search
domain_parser = reqparse.RequestParser()
domain_parser.add_argument('domain', type=str, required=True, 
                          help='Domain name is required')

# Parser for email finder
email_finder_parser = reqparse.RequestParser()
email_finder_parser.add_argument('domain', type=str, required=True, 
                               help='Domain name is required')
email_finder_parser.add_argument('first_name', type=str)
email_finder_parser.add_argument('last_name', type=str)
email_finder_parser.add_argument('position', type=str)
email_finder_parser.add_argument('pattern', type=str)

# Parser for email verification
email_verify_parser = reqparse.RequestParser()
email_verify_parser.add_argument('email', type=str, required=True, 
                               help='Email address is required')

class DomainSearch(Resource):
    @api_key_required
    def get(self):
        args = domain_parser.parse_args()
        domain = args['domain']
        
        # Extract domain from URL if provided
        ext = tldextract.extract(domain)
        domain = f"{ext.domain}.{ext.suffix}"
        
        if not validators.domain(domain):
            return {'message': 'Invalid domain format'}, 400
        
        # Record the search
        search_record = Search(
            user_id=g.user.id,
            query=domain,
            search_type='domain'
        )
        db.session.add(search_record)
        
        # Check if domain exists in database
        domain_obj = Domain.query.filter_by(domain_name=domain).first()
        if not domain_obj:
            domain_obj = Domain(domain_name=domain)
            db.session.add(domain_obj)
            db.session.commit()
        
        # Get emails for this domain
        emails = Email.query.filter_by(domain_id=domain_obj.id).all()
        
        # If no emails are found, try to find them
        if not emails:
            try:
                email_finder = EmailFinder(domain)
                found_emails = email_finder.find_bulk_emails()
                
                # Store found emails
                for email_data in found_emails:
                    email = Email(
                        email_address=email_data['email'],
                        first_name=email_data.get('first_name'),
                        last_name=email_data.get('last_name'),
                        position=email_data.get('position'),
                        confidence_score=email_data.get('confidence', 0.0),
                        domain_id=domain_obj.id
                    )
                    db.session.add(email)
                
                # Update search record with result count
                search_record.results_count = len(found_emails)
                db.session.commit()
                
                # Get the newly added emails
                emails = Email.query.filter_by(domain_id=domain_obj.id).all()
                
            except Exception as e:
                current_app.logger.error(f"API error finding emails for {domain}: {str(e)}")
                return {'message': f'Error finding emails: {str(e)}'}, 500
        
        # Format the response
        result = {
            'domain': domain,
            'emails': [
                {
                    'email': email.email_address,
                    'first_name': email.first_name,
                    'last_name': email.last_name,
                    'position': email.position,
                    'confidence': email.confidence_score,
                    'verified': email.is_verified
                } for email in emails
            ],
            'count': len(emails)
        }
        
        return result

class EmailFindAPI(Resource):
    @api_key_required
    def get(self):
        args = email_finder_parser.parse_args()
        domain = args['domain']
        first_name = args['first_name']
        last_name = args['last_name']
        position = args['position']
        pattern = args['pattern']
        
        # Extract domain
        ext = tldextract.extract(domain)
        domain = f"{ext.domain}.{ext.suffix}"
        
        if not validators.domain(domain):
            return {'message': 'Invalid domain format'}, 400
        
        if not first_name and not last_name:
            return {'message': 'First name or last name is required'}, 400
        
        # Record the search
        search_record = Search(
            user_id=g.user.id,
            query=f"{first_name} {last_name} - {domain}",
            search_type='email'
        )
        db.session.add(search_record)
        
        # Check if domain exists
        domain_obj = Domain.query.filter_by(domain_name=domain).first()
        if not domain_obj:
            domain_obj = Domain(domain_name=domain)
            db.session.add(domain_obj)
            db.session.commit()
        
        try:
            email_finder = EmailFinder(domain)
            email_data = email_finder.find_email(
                first_name=first_name,
                last_name=last_name,
                position=position,
                pattern=pattern
            )
            
            if email_data and 'email' in email_data:
                # Check if email already exists
                email_obj = Email.query.filter_by(email_address=email_data['email']).first()
                
                if not email_obj:
                    email_obj = Email(
                        email_address=email_data['email'],
                        first_name=first_name,
                        last_name=last_name,
                        position=position,
                        confidence_score=email_data.get('confidence', 0.0),
                        domain_id=domain_obj.id
                    )
                    db.session.add(email_obj)
                    
                    # Update search record
                    search_record.results_count = 1
                    db.session.commit()
                
                return {
                    'email': email_obj.email_address,
                    'first_name': email_obj.first_name,
                    'last_name': email_obj.last_name,
                    'position': email_obj.position,
                    'confidence': email_obj.confidence_score,
                    'verified': email_obj.is_verified
                }
            else:
                return {'message': 'No email found'}, 404
                
        except Exception as e:
            current_app.logger.error(f"API error finding email: {str(e)}")
            return {'message': f'Error finding email: {str(e)}'}, 500

class EmailVerifyAPI(Resource):
    @api_key_required
    def get(self):
        args = email_verify_parser.parse_args()
        email_address = args['email']
        
        if not validators.email(email_address):
            return {'message': 'Invalid email format'}, 400
        
        # Record the verification attempt
        search_record = Search(
            user_id=g.user.id,
            query=email_address,
            search_type='verify'
        )
        db.session.add(search_record)
        db.session.commit()
        
        try:
            verifier = EmailVerifier()
            verification_result = verifier.verify_email(email_address)
            
            # Check if email exists in our database
            email_obj = Email.query.filter_by(email_address=email_address).first()
            if email_obj:
                email_obj.is_verified = verification_result
                db.session.commit()
            
            return {
                'email': email_address,
                'is_valid': verification_result
            }
            
        except Exception as e:
            current_app.logger.error(f"API error verifying email {email_address}: {str(e)}")
            return {'message': f'Error verifying email: {str(e)}'}, 500

# Register API resources
api.add_resource(DomainSearch, '/domain/search')
api.add_resource(EmailFindAPI, '/email/find')
api.add_resource(EmailVerifyAPI, '/email/verify')

# Simple endpoint for API status check
@api_bp.route('/status')
def api_status():
    return jsonify({
        'status': 'online',
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat()
    })