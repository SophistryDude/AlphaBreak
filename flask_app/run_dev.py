"""Quick dev launcher - sets env vars and runs wsgi.py"""
import os
import sys

os.environ['FLASK_ENV'] = 'development'
os.environ['PORT'] = os.environ.get('PORT', '5001')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

config_name = 'development'
app = create_app(config_name)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f"Starting Flask development server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)
