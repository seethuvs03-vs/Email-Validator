import json
import os
from pathlib import Path

from waitress import serve
from web_app import create_app

if __name__ == '__main__':
    config_path = Path(__file__).parent / 'server-config.json'
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    # Explicit environment values take precedence over the generated local config.
    for name in ('SECRET_KEY', 'APP_PASSWORD', 'DATA_DIR'):
        if os.getenv(name):
            config[name] = os.environ[name]
    if 'COOKIE_SECURE' in os.environ:
        config['SESSION_COOKIE_SECURE'] = os.environ['COOKIE_SECURE'] == '1'
    app = create_app(config)
    host, port = os.getenv('HOST', '0.0.0.0'), int(os.getenv('PORT', '8080'))
    print(f'Email Cleaner is running on port {port}. Open http://localhost:{port}', flush=True)
    serve(app, host=host, port=port, threads=8, max_request_body_size=20*1024*1024)
