from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Search, Domain, Email
from sqlalchemy import func
from app import db

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    # Get recent searches
    recent_searches = Search.query.filter_by(user_id=current_user.id).order_by(
        Search.created_at.desc()
    ).limit(10).all()
    
    # Get some usage statistics
    search_count = Search.query.filter_by(user_id=current_user.id).count()
    
    # Get the number of emails found in searches
    email_count = db.session.query(func.sum(Search.results_count)).filter_by(
        user_id=current_user.id
    ).scalar() or 0
    
    context = {
        'title': 'Dashboard',
        'recent_searches': recent_searches,
        'search_count': search_count,
        'email_count': email_count
    }
    
    return render_template('dashboard/index.html', **context)

@dashboard_bp.route('/search-history')
@login_required
def search_history():
    searches = Search.query.filter_by(user_id=current_user.id).order_by(
        Search.created_at.desc()
    ).all()
    
    return render_template('dashboard/search_history.html', 
                          title='Search History',
                          searches=searches)

@dashboard_bp.route('/domains')
@login_required
def domains():
    # Get domains from the user's searches
    # This is a simplified approach and would need to be refined
    search_domains = db.session.query(Search.query).filter(
        Search.user_id == current_user.id,
        Search.search_type == 'domain'
    ).distinct().all()
    
    domain_objects = []
    for domain_query in search_domains:
        domain = Domain.query.filter_by(domain_name=domain_query[0]).first()
        if domain:
            domain_objects.append(domain)
    
    return render_template('dashboard/domains.html',
                          title='Domains',
                          domains=domain_objects)

@dashboard_bp.route('/saved-emails')
@login_required
def saved_emails():
    # In a real implementation, you'd have a user_emails table
    # This is a placeholder implementation
    
    # Get all emails from domains the user has searched
    user_searches = Search.query.filter_by(
        user_id=current_user.id,
        search_type='domain'
    ).all()
    
    domain_names = [search.query for search in user_searches]
    domains = Domain.query.filter(Domain.domain_name.in_(domain_names)).all()
    
    domain_ids = [domain.id for domain in domains]
    emails = Email.query.filter(Email.domain_id.in_(domain_ids)).all()
    
    return render_template('dashboard/saved_emails.html',
                          title='Saved Emails',
                          emails=emails)