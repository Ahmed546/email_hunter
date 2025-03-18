import os
from app import create_app

# Get environment from environment variable or default to development
env = os.environ.get('FLASK_ENV', 'development')
app = create_app(env)

if __name__ == '__main__':
    app.run(host='0.0.0.0')