import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    # Configure host/port via environment variables
    # HOST defaults to 127.0.0.1; set to 0.0.0.0 to bind all interfaces
    host = os.environ.get('HOST', '127.0.0.1')
    # PORT defaults to 5000
    port = int(os.environ.get('PORT', '3003'))
    # DEBUG can be controlled via FLASK_DEBUG=1/0 (default: 1 for dev)
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(host=host, port=port, debug=debug)
