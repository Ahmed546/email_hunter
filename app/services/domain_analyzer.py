import requests
import whois
import re
import logging
import tldextract
from bs4 import BeautifulSoup
import time
from collections import Counter

class DomainAnalyzer:
    """Service for analyzing domain information and patterns."""
    
    def __init__(self, domain):
        """
        Initialize the DomainAnalyzer with a domain.
        
        Args:
            domain (str): The domain to analyze
        """
        self.domain = domain
        self.logger = logging.getLogger(__name__)
    
    def get_domain_info(self):
        """
        Get basic information about the domain using WHOIS lookup.
        
        Returns:
            dict: Domain information
        """
        try:
            domain_info = whois.whois(self.domain)
            
            # Extract relevant information
            info = {
                'domain': self.domain,
                'registrar': domain_info.registrar,
                'creation_date': domain_info.creation_date,
                'expiration_date': domain_info.expiration_date,
                'updated_date': domain_info.updated_date,
                'name_servers': domain_info.name_servers
            }
            
            # Try to get organization or registrant info
            if hasattr(domain_info, 'org') and domain_info.org:
                info['organization'] = domain_info.org
            elif hasattr(domain_info, 'organization') and domain_info.organization:
                info['organization'] = domain_info.organization
            
            return info
        except Exception as e:
            self.logger.error(f"Error getting domain info for {self.domain}: {str(e)}")
            return {'domain': self.domain, 'error': str(e)}
    
    def detect_email_pattern(self):
        """
        Try to detect the most common email pattern used by the domain.
        
        Returns:
            str: The detected email pattern or None if not detected
        """
        # First, try to find emails on the website
        emails = self.find_emails_on_website()
        
        if not emails:
            return None
        
        # Analyze the patterns
        patterns = []
        
        for email in emails:
            username, domain = email.split('@')
            
            # Skip if domain doesn't match
            if domain != self.domain:
                continue
            
            # Check for common patterns
            if '.' in username:
                # Could be first.last pattern
                parts = username.split('.')
                if len(parts) == 2:
                    patterns.append('{first}.{last}@{domain}')
            elif len(username) > 1 and username[1:].isalpha() and username[0].isalpha():
                # Could be first initial + last name
                patterns.append('{first_initial}{last}@{domain}')
            elif '_' in username:
                # Could be first_last pattern
                patterns.append('{first}_{last}@{domain}')
            elif '-' in username:
                # Could be first-last pattern
                patterns.append('{first}-{last}@{domain}')
            else:
                # Other patterns are harder to detect automatically
                continue
        
        # Find the most common pattern
        if patterns:
            pattern_counter = Counter(patterns)
            most_common = pattern_counter.most_common(1)
            if most_common:
                return most_common[0][0]
        
        # Default to the most common pattern if we couldn't detect
        return '{first}.{last}@{domain}'
    
    def find_emails_on_website(self):
        """
        Find email addresses on the domain's website.
        
        Returns:
            list: List of email addresses found
        """
        found_emails = []
        urls_to_check = [
            f'https://{self.domain}',
            f'https://www.{self.domain}',
            f'https://{self.domain}/contact',
            f'https://www.{self.domain}/contact',
            f'https://{self.domain}/about',
            f'https://www.{self.domain}/about',
            f'https://{self.domain}/team',
            f'https://www.{self.domain}/team'
        ]
        
        # User agent for requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        for url in urls_to_check:
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    # Look for emails using regex
                    email_regex = rf'\b[A-Za-z0-9._%+-]+@{re.escape(self.domain)}\b'
                    found = re.findall(email_regex, response.text)
                    found_emails.extend(found)
                    
                    # Look for emails in mailto links
                    soup = BeautifulSoup(response.text, 'html.parser')
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        if href.startswith('mailto:'):
                            email = href[7:]  # Remove 'mailto:'
                            if email.endswith(f'@{self.domain}'):
                                found_emails.append(email)
                
                # Be nice to the server
                time.sleep(1)
                
            except Exception as e:
                self.logger.warning(f"Error scraping {url}: {str(e)}")
        
        # Remove duplicates
        return list(set(found_emails))
    
    def get_company_name(self):
        """
        Try to determine the company name from the domain.
        
        Returns:
            str: Company name or None if not determined
        """
        try:
            # First, check WHOIS information
            domain_info = self.get_domain_info()
            if 'organization' in domain_info and domain_info['organization']:
                return domain_info['organization']
            
            # Try to extract from the domain name itself
            ext = tldextract.extract(self.domain)
            company_name = ext.domain.title()
            
            # Check if it looks like a company name
            if len(company_name) >= 3:
                return company_name
            
            # Try to find it on the website
            urls_to_check = [
                f'https://{self.domain}',
                f'https://www.{self.domain}'
            ]
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            for url in urls_to_check:
                try:
                    response = requests.get(url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        # Look for title
                        if soup.title:
                            title = soup.title.string
                            if title:
                                # Remove common terms
                                title = title.replace('Home', '').replace('Homepage', '')
                                title = title.replace('Welcome to', '').replace('Official Site', '')
                                title = title.strip(' |:-')
                                if title and len(title) > 2:
                                    return title
                        
                        # Look for company name in meta tags
                        meta_tags = soup.find_all('meta')
                        for tag in meta_tags:
                            if tag.get('name') in ['author', 'publisher', 'owner']:
                                content = tag.get('content')
                                if content and len(content) > 2:
                                    return content
                        
                        # Look for logo alt text
                        logo = soup.find('img', alt=True, src=lambda s: 'logo' in s.lower() if s else False)
                        if logo and logo['alt'] and len(logo['alt']) > 2:
                            return logo['alt']
                    
                except Exception as e:
                    self.logger.warning(f"Error scraping {url} for company name: {str(e)}")
            
            # If all else fails, use the domain name
            return company_name
        
        except Exception as e:
            self.logger.error(f"Error getting company name for {self.domain}: {str(e)}")
            
            # Fall back to domain name
            ext = tldextract.extract(self.domain)
            return ext.domain.title()