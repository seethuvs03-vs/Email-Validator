"""Create a GitHub-ready source archive from an explicit allowlist."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parent
files = [
    '.gitignore', '.dockerignore', '.env.example', 'README.md',
    'GITHUB_UPLOAD.md', 'WINDOWS_SERVER_SETUP.md', 'requirements.txt',
    'web_app.py', 'server.py', 'email_validator_tool.py', 'setup_server.py',
    'Setup_Server.bat', 'Start_Server.bat', 'Dockerfile', 'compose.yaml',
    'sample_contacts.csv', 'package_server.py', 'package_github.py',
    'app.py', 'Validate_Emails.bat',
]
for folder in ('static', 'templates', 'tests'):
    files.extend(str(p.relative_to(root)) for p in (root / folder).rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts)
output = root / 'dist' / 'Email-Cleaner-GitHub.zip'
output.parent.mkdir(exist_ok=True)
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for name in files:
        archive.write(root / name, name.replace('\\', '/'))
with ZipFile(output) as archive:
    assert archive.testzip() is None
    assert set(archive.namelist()) == {name.replace('\\', '/') for name in files}
print(f'{output}\nVerified {len(files)} source files.')
