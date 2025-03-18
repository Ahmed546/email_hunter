
# Email Hunter

Email Hunter is a web application that helps you find and verify email addresses associated with domains and specific people, similar to Hunter.io. This project provides a self-hosted solution for email discovery and verification.

## Features

- **Domain Search**: Find all email addresses associated with a domain
- **Email Finder**: Discover email addresses of specific people at a company
- **Email Verification**: Verify the validity of email addresses
- **User Dashboard**: Track search history and saved results
- **API Access**: Programmatic access to all features

## Technology Stack

- **Backend**: Python, Flask
- **Database**: SQLAlchemy (supports SQLite, PostgreSQL, etc.)
- **Frontend**: HTML, CSS, JavaScript, Bootstrap 5
- **Email Verification**: DNS checks, SMTP verification
- **Web Scraping**: BeautifulSoup, Selenium

## Installation

### Prerequisites

- Python 3.8+
- pip
- Virtual environment (recommended)

### Setup

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/email-hunter.git
   cd email-hunter
   ```

2. Create and activate virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use: venv\Scripts\activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Create environment variables file
   ```bash
   cp .env.example .env
   ```
   Edit the `.env` file and set your configuration values.

5. Initialize the database
   ```bash
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

6. Run the application
   ```bash
   python run.py
   ```

   The application will be available at http://localhost:5000

## Configuration

The application can be configured through environment variables or the `.env` file:

- `FLASK_ENV`: Environment (`development`, `testing`, `production`)
- `FLASK_APP`: Application entry point (`run.py`)
- `SECRET_KEY`: Secret key for session security
- `DATABASE_URL`: Database connection URL
- `SMTP_TIMEOUT`: Timeout for SMTP connections in seconds
- `MAX_REQUESTS_PER_DAY`: API rate limit per user

## API Usage

The API provides endpoints for all major features with authentication via API key:

### Authentication

Include your API key in the request header:
```
X-API-Key: your_api_key
```

### Endpoints

- `GET /api/v1/status`: Check API status
- `GET /api/v1/domain/search?domain=example.com`: Find emails for a domain
- `GET /api/v1/email/find?domain=example.com&first_name=John&last_name=Smith`: Find specific email
- `GET /api/v1/email/verify?email=example@example.com`: Verify an email address

## Project Structure

```
email_hunter/
├── app/
│   ├── __init__.py
│   ├── models.py          # Database models
│   ├── routes/            # Route handlers
│   ├── services/          # Business logic services
│   ├── static/            # CSS, JS, images
│   └── templates/         # HTML templates
├── config.py              # Configuration file
├── requirements.txt       # Dependencies
├── run.py                 # Application entry point
└── README.md              # Project documentation
```

## Development

### Adding New Features

1. Create or modify models in `app/models.py`
2. Run database migrations
   ```bash
   flask db migrate -m "Description of changes"
   flask db upgrade
   ```
3. Implement business logic in `app/services/`
4. Add routes in `app/routes/`
5. Create/update templates in `app/templates/`

### Testing

Run the test suite:
```bash
pytest
```

## Security Considerations

- The application hashes user passwords with bcrypt
- API keys are generated using UUIDs
- CSRF protection is enabled for all forms
- Rate limiting is implemented for API endpoints

## Limitations

- Email verification is performed using basic checks and may not be 100% accurate
- The accuracy of email finding depends on the availability of data
- Aggressive scraping may lead to IP blocks from certain websites

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- Hunter.io for the inspiration
- Flask and related libraries for making web development in Python enjoyable
- Bootstrap for the responsive UI components