from flask import Blueprint, render_template, request, jsonify, current_app, flash, redirect, url_for
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField
from wtforms.validators import DataRequired, Optional, ValidationError
import validators
import tldextract

from app import db, cache
from app.models import Search, Domain, Email
from app.services.email_finder import EmailFinder
from app.services.email_verifier import EmailVerifier

search_bp = Blueprint('search', __name__)

class DomainSearchForm(FlaskForm):
    domain = StringField('Domain', validators=[DataRequired()])
    submit = SubmitField('Search')
    
    def validate_domain(self, field):
        # Extract the domain from URL if provided
        ext = tldextract.extract(field.data)
        domain = f"{ext.domain}.{ext.suffix}"
        
        if not validators.domain(domain):
            raise ValidationError('Invalid domain. Please enter a valid domain name.')

class EmailFinderForm(FlaskForm):
    domain = StringField('Domain', validators=[DataRequired()])
    first_name = StringField('First Name', validators=[Optional()])
    last_name = StringField('Last Name', validators=[Optional()])
    position = StringField('Position', validators=[Optional()])
    pattern = SelectField('Email Pattern', choices=[
        ('', 'Auto-detect'),
        ('{first}.{last}', '{first}.{last}@domain.com'),
        ('{first_initial}{last}', '{first_initial}{last}@domain.com'),
        ('{first}', '{first}@domain.com'),
        ('{last}', '{last}@domain.com'),
        ('{first}{last}', '{first}{last}@domain.com'),
        ('{first_initial}.{last}', '{first_initial}.{last}@domain.com')
    ], validators=[Optional()])
    submit = SubmitField('Find Email')

@search_bp.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    domain_form = DomainSearchForm()
    email_form = EmailFinderForm()
    
    if domain_form.submit.data and domain_form.validate_on_submit():
        # Extract the domain
        ext = tldextract.extract(domain_form.domain.data)
        domain = f"{ext.domain}.{ext.suffix}"
        
        # Record the search
        search_record = Search(
            user_id=current_user.id,
            query=domain,
            search_type='domain'
        )
        db.session.add(search_record)
        
        # Check if domain exists in our database
        domain_obj = Domain.query.filter_by(domain_name=domain).first()
        if not domain_obj:
            domain_obj = Domain(domain_name=domain)
            db.session.add(domain_obj)
        
        db.session.commit()
        
        return redirect(url_for('search.domain_results', domain=domain))
    
    if email_form.submit.data and email_form.validate_on_submit():
        # Extract the domain
        ext = tldextract.extract(email_form.domain.data)
        domain = f"{ext.domain}.{ext.suffix}"
        
        # Record the search
        search_record = Search(
            user_id=current_user.id,
            query=f"{email_form.first_name.data} {email_form.last_name.data} - {domain}",
            search_type='email'
        )
        db.session.add(search_record)
        db.session.commit()
        
        # Redirect to the email finder with parameters
        return redirect(url_for('search.email_finder', 
                                domain=domain,
                                first_name=email_form.first_name.data,
                                last_name=email_form.last_name.data,
                                position=email_form.position.data,
                                pattern=email_form.pattern.data))
    
    return render_template('search/search.html', 
                          title='Search',
                          domain_form=domain_form,
                          email_form=email_form)

@search_bp.route('/domain/<domain>')
@login_required
def domain_results(domain):
    # Check if the domain exists in our database
    domain_obj = Domain.query.filter_by(domain_name=domain).first()
    
    if not domain_obj:
        flash(f"Domain {domain} not found in our database.", "warning")
        return redirect(url_for('search.search'))
    
    # Get emails associated with this domain
    emails = Email.query.filter_by(domain_id=domain_obj.id).all()
    
    # If we don't have emails yet, try to find them
    if not emails:
        try:
            email_finder = EmailFinder(domain)
            found_emails = email_finder.find_bulk_emails()
            
            # Store the found emails
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
            
            # Update the search record with the number of results
            search_record = Search.query.filter_by(
                user_id=current_user.id,
                query=domain,
                search_type='domain'
            ).order_by(Search.created_at.desc()).first()
            
            if search_record:
                search_record.results_count = len(found_emails)
                db.session.commit()
            
            # Get the newly added emails
            emails = Email.query.filter_by(domain_id=domain_obj.id).all()
            
        except Exception as e:
            current_app.logger.error(f"Error finding emails for {domain}: {str(e)}")
            flash(f"An error occurred while searching for emails on {domain}.", "danger")
    
    return render_template('search/domain_results.html',
                          title=f'Results for {domain}',
                          domain=domain_obj,
                          emails=emails)

@search_bp.route('/email-finder')
@login_required
def email_finder():
    domain = request.args.get('domain')
    first_name = request.args.get('first_name')
    last_name = request.args.get('last_name')
    position = request.args.get('position')
    pattern = request.args.get('pattern')
    
    if not domain or (not first_name and not last_name):
        flash("Please provide at least a domain and a name.", "warning")
        return redirect(url_for('search.search'))
    
    # Check if domain exists in our database
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
                search_record = Search.query.filter_by(
                    user_id=current_user.id,
                    query=f"{first_name} {last_name} - {domain}",
                    search_type='email'
                ).order_by(Search.created_at.desc()).first()
                
                if search_record:
                    search_record.results_count = 1
                    db.session.commit()
                
            # Verify the email if it hasn't been verified
            if not email_obj.is_verified:
                verifier = EmailVerifier()
                is_valid = verifier.verify_email(email_obj.email_address)
                email_obj.is_verified = is_valid
                db.session.commit()
            
            return render_template('search/email_result.html',
                                  title='Email Finder Result',
                                  email=email_obj,
                                  domain=domain_obj)
        else:
            flash("No email could be found with the provided information.", "warning")
            return redirect(url_for('search.search'))
            
    except Exception as e:
        current_app.logger.error(f"Error finding email: {str(e)}")
        flash("An error occurred while finding the email.", "danger")
        return redirect(url_for('search.search'))

@search_bp.route('/verify-email/<int:email_id>')
@login_required
def verify_email(email_id):
    email = Email.query.get_or_404(email_id)
    
    verifier = EmailVerifier()
    is_valid = verifier.verify_email(email.email_address)
    
    email.is_verified = is_valid
    db.session.commit()
    
    return jsonify({
        'id': email.id,
        'is_verified': email.is_verified
    })