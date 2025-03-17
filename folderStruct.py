import os

# Create directories
os.makedirs('app', exist_ok=True)
os.makedirs('app/routes', exist_ok=True)
os.makedirs('app/services', exist_ok=True)
os.makedirs('app/static', exist_ok=True)
os.makedirs('app/templates', exist_ok=True)

# Create files
with open('app/__init__.py', 'w') as f:
    pass

with open('app/models.py', 'w') as f:
    pass

with open('app/routes/__init__.py', 'w') as f:
    pass

with open('app/routes/auth.py', 'w') as f:
    pass

with open('app/routes/dashboard.py', 'w') as f:
    pass

with open('app/routes/search.py', 'w') as f:
    pass

with open('app/routes/api.py', 'w') as f:
    pass

with open('app/services/__init__.py', 'w') as f:
    pass

with open('app/services/email_finder.py', 'w') as f:
    pass

with open('app/services/email_verifier.py', 'w') as f:
    pass

with open('app/services/domain_analyzer.py', 'w') as f:
    pass

with open('config.py', 'w') as f:
    pass

with open('requirements.txt', 'w') as f:
    pass

with open('run.py', 'w') as f:
    pass


