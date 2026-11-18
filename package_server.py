"""Produce a portable source/setup ZIP without credentials or uploaded data."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parent
output = root / 'dist' / 'Email-Cleaner-Windows-Server.zip'
output.parent.mkdir(exist_ok=True)
files = ['web_app.py', 'server.py', 'setup_server.py', 'email_validator_tool.py',
         'requirements.txt', 'Setup_Server.bat', 'Start_Server.bat',
         'WINDOWS_SERVER_SETUP.md', 'Dockerfile', 'compose.yaml', '.env.example',
         '.dockerignore', 'sample_contacts.csv']
files += [str(p.relative_to(root)) for folder in ['templates', 'static', 'tests']
          for p in (root / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for name in files:
        archive.write(root / name, 'Email-Cleaner/' + name.replace('\\', '/'))
print(output)
