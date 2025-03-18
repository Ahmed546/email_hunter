import requests
import re
import time
from bs4 import BeautifulSoup
import logging
import random
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import dns.resolver
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from app.services.domain_analyzer import DomainAnalyzer

class EmailFinder:
    """Service for finding email addresses associated with a domain."""
    
    def __init__(self, domain):
        """
        Initialize the EmailFinder with a domain.
        
        Args:
            domain (str): The domain to search for emails
        """
        self.domain = domain
        self.found_emails = set()
        self.common_patterns = [
            '{first}.{last}@{domain}',
            '{first_initial}{last}@{domain}',
            '{first}@{domain}',
            '{last}@{domain}',
            '{first}{last}@{domain}',
            '{first_initial}.{last}@{domain}'
        ]
        self.base_urls = [
            f'https://{domain}',
            f'https://www.{domain}'
        ]
        self.visited_urls = set()
        self.domain_analyzer = DomainAnalyzer(domain)
        self.logger = logging.getLogger(__name__)
        
        # User agents for rotating
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0'
        ]
    
    def get_random_user_agent(self):
        """Return a random user agent from the list."""
        return random.choice(self.user_agents)
    
    def get_common_email_pattern(self):
        """
        Try to determine the most common email pattern for the domain.
        
        Returns:
            str: The most common email pattern or None if not determined
        """
        try:
            # First, check if we have email patterns stored in our database
            # This would be implemented in a real application
            
            # If not, analyze the domain's website and other sources
            pattern = self.domain_analyzer.detect_email_pattern()
            if pattern:
                return pattern
            
            # Default to the most common pattern
            return '{first}.{last}@{domain}'
        except Exception as e:
            self.logger.error(f"Error getting email pattern: {str(e)}")
            return '{first}.{last}@{domain}'
    
    def find_emails_on_page(self, url):
        """
        Find all email addresses on a given web page.
        
        Args:
            url (str): URL to scrape for emails
            
        Returns:
            set: Set of email addresses found
        """
        page_emails = set()
        headers = {'User-Agent': self.get_random_user_agent()}
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Extract emails using regex
            email_regex = rf'\b[A-Za-z0-9._%+-]+@{re.escape(self.domain)}\b'
            found = re.findall(email_regex, response.text)
            page_emails.update(found)
            
            # Parse HTML for additional emails
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for emails in mailto links
            for link in soup.find_all('a', href=True):
                href = link['href']
                if href.startswith('mailto:'):
                    email = href[7:]  # Remove 'mailto:'
                    if email.endswith(f'@{self.domain}'):
                        page_emails.add(email)
            
            # Find contact and about pages
            contact_links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                link_text = link.text.lower()
                if ('contact' in href.lower() or 'about' in href.lower() or 
                    'team' in href.lower() or 'contact' in link_text or 
                    'about' in link_text or 'team' in link_text):
                    full_url = urljoin(url, href)
                    if full_url not in self.visited_urls and self.is_same_domain(full_url):
                        contact_links.append(full_url)
                        self.visited_urls.add(full_url)
            
            # Recursively check contact and about pages
            for link in contact_links[:3]:  # Limit to avoid too much scraping
                try:
                    time.sleep(1)  # Be respectful with rate limiting
                    sub_page_emails = self.find_emails_on_page(link)
                    page_emails.update(sub_page_emails)
                except Exception as sub_e:
                    self.logger.warning(f"Error scraping sub-page {link}: {str(sub_e)}")
        
        except Exception as e:
            self.logger.warning(f"Error scraping {url}: {str(e)}")
        
        return page_emails
    
    def is_same_domain(self, url):
        """Check if a URL belongs to the same domain."""
        parsed = urlparse(url)
        return parsed.netloc == self.domain or parsed.netloc == f'www.{self.domain}'
    
    def find_bulk_emails(self):
        """
        Find all available email addresses for the domain.
        
        Returns:
            list: List of dictionaries with email information
        """
        self.found_emails = set()
        
        # Try each base URL
        for url in self.base_urls:
            try:
                page_emails = self.find_emails_on_page(url)
                self.found_emails.update(page_emails)
            except Exception as e:
                self.logger.warning(f"Error scraping {url}: {str(e)}")
        
        # Check common pages
        common_pages = ['contact', 'about', 'team', 'leadership', 'staff', 'faculty']
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_url = {}
            for page in common_pages:
                for base_url in self.base_urls:
                    url = f"{base_url}/{page}"
                    if url not in self.visited_urls:
                        self.visited_urls.add(url)
                        future_to_url[executor.submit(self.find_emails_on_page, url)] = url
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    page_emails = future.result()
                    self.found_emails.update(page_emails)
                except Exception as e:
                    self.logger.warning(f"Error scraping {url}: {str(e)}")
        
        # Process found emails to extract names and other information
        result = []
        for email in self.found_emails:
            email_info = self.parse_email_info(email)
            result.append(email_info)
        
        return result
    
    def parse_email_info(self, email):
        """
        Parse additional information from an email address.
        
        Args:
            email (str): Email address
            
        Returns:
            dict: Dictionary with email information
        """
        try:
            username = email.split('@')[0]
            
            # Try to identify first and last names
            first_name = None
            last_name = None
            
            # Check common naming patterns
            if '.' in username:
                parts = username.split('.')
                first_name = parts[0].capitalize()
                if len(parts) > 1:
                    last_name = parts[1].capitalize()
            elif len(username) > 2:
                # Try to guess if it's first initial + last name
                if username[1:].isalpha() and username[0].isalpha():
                    first_name = username[0].upper()
                    last_name = username[1:].capitalize()
            
            return {
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'confidence': 0.8,  # Found on website, so relatively high confidence
                'source': 'website'
            }
        except Exception as e:
            self.logger.error(f"Error parsing email info for {email}: {str(e)}")
            return {
                'email': email,
                'confidence': 0.7
            }
    
    def find_email(self, first_name=None, last_name=None, position=None, pattern=None):
        """
        Find a specific email address for a person at the domain.
        
        Args:
            first_name (str): First name
            last_name (str): Last name
            position (str): Position at the company (optional)
            pattern (str): Email pattern to use (optional)
            
        Returns:
            dict: Dictionary with email information or None if not found
        """
        if not first_name and not last_name:
            return None
        
        # Format names
        if first_name:
            first_name = first_name.lower().strip()
            first_initial = first_name[0] if first_name else ''
        else:
            first_name = ''
            first_initial = ''
        
        if last_name:
            last_name = last_name.lower().strip()
        else:
            last_name = ''
        
        # Determine pattern to use
        if not pattern:
            pattern = self.get_common_email_pattern()
        
        # Generate the email
        email = pattern.format(
            first=first_name,
            last=last_name,
            first_initial=first_initial,
            domain=self.domain
        )
        
        # Verify the email exists (MX check)
        if self.verify_email_exists(email):
            return {
                'email': email,
                'first_name': first_name.capitalize() if first_name else None,
                'last_name': last_name.capitalize() if last_name else None,
                'position': position,
                'confidence': 0.7,  # Generated email with pattern
                'source': 'pattern'
            }
        
        # If the first pattern failed, try other common patterns
        for alt_pattern in self.common_patterns:
            if alt_pattern == pattern:
                continue
                
            alt_email = alt_pattern.format(
                first=first_name,
                last=last_name,
                first_initial=first_initial,
                domain=self.domain
            )
            
            if self.verify_email_exists(alt_email):
                return {
                    'email': alt_email,
                    'first_name': first_name.capitalize() if first_name else None,
                    'last_name': last_name.capitalize() if last_name else None,
                    'position': position,
                    'confidence': 0.6,  # Alternative pattern, lower confidence
                    'source': 'pattern'
                }
        
        # If all patterns failed, try to search on the website
        try:
            # Try to find on website using more advanced techniques
            found_emails = self.find_bulk_emails()
            
            # Look for possible matches
            for email_info in found_emails:
                email_first = email_info.get('first_name', '').lower() if email_info.get('first_name') else ''
                email_last = email_info.get('last_name', '').lower() if email_info.get('last_name') else ''
                
                # Check for matches with name components
                if ((first_name and email_first and first_name in email_first) or 
                    (last_name and email_last and last_name in email_last)):
                    return email_info
            
        except Exception as e:
            self.logger.error(f"Error in advanced email search: {str(e)}")
        
        # If nothing worked, return the most likely email with low confidence
        return {
            'email': email,
            'first_name': first_name.capitalize() if first_name else None,
            'last_name': last_name.capitalize() if last_name else None,
            'position': position,
            'confidence': 0.3,  # Low confidence since we couldn't verify
            'source': 'guess'
        }
    
    def verify_email_exists(self, email):
        """
        Basic verification that an email might exist (MX record check).
        Not a full verification, just a preliminary check.
        
        Args:
            email (str): Email address to verify
            
        Returns:
            bool: True if the email might exist, False otherwise
        """
        try:
            domain = email.split('@')[1]
            
            # Check if MX records exist for the domain
            mx_records = dns.resolver.resolve(domain, 'MX')
            if mx_records:
                return True
            
            return False
        except Exception:
            return False