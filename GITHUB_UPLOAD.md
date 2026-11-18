# Upload this application to GitHub

1. Extract `Email-Cleaner-GitHub.zip`.
2. Create or open your GitHub repository.
3. Select **Add file → Upload files**.
4. Upload the extracted files and the `static`, `templates`, and `tests` folders, preserving their structure. Include `.gitignore`, `.dockerignore`, and `.env.example`; enable hidden-file display if necessary.
5. Commit the upload. Do not upload only the ZIP if you want GitHub to display and track the source files.

The archive includes the web application, validation engine, Windows setup/start scripts, Docker configuration, tests, sample file, documentation and packaging scripts. The earlier optional desktop version is included as `app.py` and `Validate_Emails.bat`.

Passwords, signing secrets, server configuration, uploaded contacts, validation results, logs and Python environments are excluded. New server installations ask you to choose a team password during setup. Existing `server-config.json` files retain their current password.

To update the running Windows Server, stop the application, copy the updated source files into its installation folder, preserve `server-config.json`, rerun setup if dependencies changed, and restart on the configured port. For the port used in this installation:

```bat
set "PORT=18765"
Start_Server.bat
```

GitHub stores source code. Uploading this repository does not deploy or restart your server, and GitHub Pages cannot run this Python backend. Use the Windows Server instructions in `WINDOWS_SERVER_SETUP.md` for hosting.

To regenerate the source archive:

```bat
python package_github.py
```
