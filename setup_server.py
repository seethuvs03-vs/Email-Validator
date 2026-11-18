import json
import secrets
from getpass import getpass
from pathlib import Path

path = Path(__file__).parent / 'server-config.json'
if not path.exists():
    password = getpass('Choose the team login password: ')
    if not password:
        raise SystemExit('Password cannot be empty. Run setup again.')
    if password != getpass('Confirm the team login password: '):
        raise SystemExit('Passwords do not match. Run setup again.')
    path.write_text(json.dumps({'SECRET_KEY': secrets.token_hex(32), 'APP_PASSWORD': password}, indent=2))
    print('\nServer setup complete. The team password has been saved locally.')
    print('\nKeep it private. You can change APP_PASSWORD in server-config.json.\n')
else:
    print('Existing server configuration preserved.')
