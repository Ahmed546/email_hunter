import socket
import smtplib
import dns.resolver
import logging
import time
from email.utils import parseaddr
import re

class EmailVerifier:
    """Service for verifying if an email address exists and is valid."""
    
    def __init__(self, timeout=10):
        """
        Initialize the EmailVerifier.
        
        Args:
            timeout (int): Timeout in seconds for SMTP connections
        """
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
    
    def verify_format(self, email):
        """
        Verify that the email has a valid format.
        
        Args:
            email (str): Email address to verify
            
        Returns:
            bool: True if format is valid, False otherwise
        """
        # Basic format check
        if not email or '@' not in email:
            return False
        
        # Use email.utils to parse the email
        parsed_email = parseaddr(email)[1]
        if not parsed_email:
            return False
        
        # RFC 5322 format regex (simplified)
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, parsed_email):
            return False
        
        # Check length constraints
        if len(parsed_email) > 254:
            return False
        
        local_part = parsed_email.split('@')[0]
        if len(local_part) > 64:
            return False
        
        return True
    
    def verify_domain(self, domain):
        """
        Verify that the domain exists and has MX records.
        
        Args:
            domain (str): Domain to verify
            
        Returns:
            tuple: (bool, list) - Success status and list of MX servers if found
        """
        try:
            # Check if the domain exists (has MX records)
            mx_records = dns.resolver.resolve(domain, 'MX')
            mx_hosts = [record.exchange.to_text().strip('.') for record in mx_records]
            
            # If no MX records, try checking for A records
            if not mx_hosts:
                a_records = dns.resolver.resolve(domain, 'A')
                if a_records:
                    mx_hosts = [domain]
                    return True, mx_hosts
                return False, []
            
            return True, mx_hosts
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            return False, []
        except Exception as e:
            self.logger.error(f"Error verifying domain {domain}: {str(e)}")
            return False, []
    
    def verify_mailbox(self, email, mx_hosts):
        """
        Verify that the mailbox exists by connecting to the mail server.
        
        Args:
            email (str): Email address to verify
            mx_hosts (list): List of MX servers to try
            
        Returns:
            bool: True if mailbox exists, False otherwise
        """
        domain = email.split('@')[1]
        sender_domain = "gmail.com"  # Use a common domain for the test email
        sender = f"verify@{sender_domain}"
        
        for mx_host in mx_hosts:
            try:
                # Connect to the mail server
                smtp = smtplib.SMTP(timeout=self.timeout)
                smtp.connect(mx_host)
                
                # Say hello to the server
                smtp.ehlo_or_helo_if_needed()
                
                # Start TLS if supported
                if smtp.has_extn('STARTTLS'):
                    smtp.starttls()
                    smtp.ehlo()
                
                # Send test messages
                smtp.mail(sender)
                code, message = smtp.rcpt(email)
                smtp.quit()
                
                # Return code 250 means the mailbox exists
                if code == 250:
                    return True
                
            except smtplib.SMTPServerDisconnected:
                continue
            except smtplib.SMTPConnectError:
                continue
            except socket.timeout:
                continue
            except Exception as e:
                self.logger.error(f"Error verifying mailbox {email} on {mx_host}: {str(e)}")
                continue
        
        # If we reach here, we couldn't verify the mailbox
        return False
    
    def verify_email(self, email):
        """
        Verify an email address by checking format, domain, and mailbox.
        
        Args:
            email (str): Email address to verify
            
        Returns:
            bool: True if the email is valid, False otherwise
        """
        if not self.verify_format(email):
            self.logger.info(f"Email {email} has invalid format")
            return False
        
        domain = email.split('@')[1]
        domain_valid, mx_hosts = self.verify_domain(domain)
        
        if not domain_valid:
            self.logger.info(f"Domain {domain} is invalid")
            return False
        
        # In a production environment, you might want to be cautious with mailbox verification
        # as it can get your IP blacklisted if done too aggressively
        # For this implementation, we'll just check the format and domain
        
        # Uncomment the following for full verification:
        # return self.verify_mailbox(email, mx_hosts)
        
        # For now, just assume it's valid if the domain is valid
        return True