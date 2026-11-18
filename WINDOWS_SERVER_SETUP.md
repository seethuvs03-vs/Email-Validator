# Email Cleaner — Windows Server setup

This is a self-hosted browser application. Install it once on the company server; staff open its link from their computers. No Python or desktop app is required on staff computers.

## 1. Install and start

1. Install **Python 3.10 or newer** on the Windows Server, with the `python` command available. Python 3.13 or 3.14 is recommended for this package.
2. Extract `Email-Cleaner-Windows-Server.zip` to a permanent folder, for example `C:\Apps\EmailCleaner`. Do not run from inside the ZIP.
3. Double-click **Setup_Server.bat**. It installs dependencies into `.web-venv` and generates `server-config.json`. The first setup needs internet access to the Python package index.
4. When prompted, choose and confirm the **team login password**. Typing is hidden. It is saved in `server-config.json`; existing configurations are preserved. Share it only with the intended staff. IT can replace `APP_PASSWORD` in that file and restart the app to change it.
5. Double-click **Start_Server.bat**. Keep this window open while testing.
6. On the server, open **http://localhost:8080** and sign in.

Staff link: **http://SERVER-NAME:8080** or **http://SERVER-IP:8080**. Replace SERVER-NAME / SERVER-IP with the actual server address. This is an example pattern, not a published link. The server must be reachable from staff computers.

IT should allow inbound TCP port 8080 from the intended company network only. The server needs outbound DNS to its configured resolver for validation; it does not need SMTP access. If port 8080 is occupied, set the `PORT` environment variable and use that port in the link and firewall rule.

## 2. Run automatically without a logged-in desktop

Use Windows Task Scheduler to keep the server process running:

- Create a task named **Email Cleaner** under a dedicated company service account.
- Select **Run whether user is logged on or not**.
- Trigger: **At startup**, with a 30-second delay.
- Action / program: `C:\Apps\EmailCleaner\.web-venv\Scripts\python.exe`
- Arguments: `"C:\Apps\EmailCleaner\server.py"`
- Start in: `C:\Apps\EmailCleaner`
- Settings: restart on failure every 1 minute; do not start another instance if already running; disable the default execution time limit.
- Grant that account read access to the application and config, and modify access to `server-data` and its contents. Restrict the config file to administrators and the service account.

Adjust these paths if installed elsewhere. Stop the manual Start_Server window before starting the task so both processes do not compete for port 8080. Run the task and confirm `/health` returns `{"status":"ok"}`. Only one application process should run: job state is held in memory.

## 3. Give it a company HTTPS address

For a normal company URL such as **https://email-cleaner.company-domain**, IT can put IIS in front of the app:

1. Create an internal DNS record pointing the chosen name to the Windows Server.
2. Install IIS URL Rewrite and Application Request Routing (ARR), enable ARR proxy functionality, and configure the site with the company's TLS certificate.
3. Reverse-proxy that site's requests to `http://127.0.0.1:8080`, preserving the path and query string. Serve the app at the hostname root, not a subdirectory.
4. Set IIS request limits to at least 21 MB to allow multipart upload overhead; the app enforces a 20 MB request limit itself.
5. For the application process, set `HOST=127.0.0.1` and `COOKIE_SECURE=1`, then restart it. Alternatively, set `"SESSION_COOKIE_SECURE": true` in `server-config.json` and use the HOST environment variable. Staff should then use HTTPS only.
6. Allow HTTPS through the company firewall. Port 8080 need not be accessible to staff when IIS is the entry point.

Use a company-managed HTTPS connection for production login and uploads. The HTTP address is useful for an initial server/intranet test. No IIS changes, firewall rules, DNS records or remote deployment have been made by this package.

## Operation and limits

- Supports Excel `.xlsx` / `.xls`, Word `.docx`, CSV, TSV and text. Word `.doc` requires conversion to `.docx`. Images and scanned text are not extracted.
- 20 MB maximum request, 100 MB maximum expanded Office document, 50,000 candidates per file, two concurrent validation jobs and 20 retained jobs. Busy servers return a retry message.
- Each browser session can see only the jobs it submitted. The shared team password is not individual employee identity or SSO. Closing the session or signing out can make its results inaccessible.
- Raw uploads are removed when processing finishes. Results expire one hour after completion; the cleanup sweep runs every minute while the server is running. Data left by a stopped server is cleaned after it starts again. Restarting the process makes previous result links unavailable.
- Export options: clean CSV, full Excel report, or ZIP containing Excel and all result CSVs.
- Clean means syntax and mail-domain checks passed, not guaranteed mailbox existence. A small built-in disposable-domain list is used. This app does not send emails or probe SMTP servers.
- The web service uses Flask with Waitress, not Flask's development server. Run one instance. For substantially higher volume, a separate persistent job queue and worker service would be needed.
- Uploads and results live in `server-data`. Keep this folder on local protected storage, not a public web directory. Exclude it from routine backup if email lists must not be retained beyond the cleanup period.

## Troubleshooting

- **Python not found:** install Python and add it to PATH, then reopen setup.
- **Setup download error:** IT must permit package downloads or supply an approved offline package mirror.
- **Other computers cannot connect:** confirm the server address, app process, chosen port, company firewall and network routing.
- **Most addresses need review:** check server DNS connectivity. Network errors are intentionally not treated as invalid addresses.
- **Login loops after enabling secure cookies:** open the HTTPS company URL. Secure cookies do not work over normal remote HTTP.
- **Busy message:** wait for active jobs to finish. Completed jobs expire automatically after one hour.

## Optional Docker deployment

The package also contains Docker configuration for a Linux Docker host. Copy `.env.example` to `.env`, set a strong APP_PASSWORD and random SECRET_KEY, then run `docker compose up -d --build`. Set COOKIE_SECURE=1 when accessed through an HTTPS reverse proxy. The Windows Python installation above does not require Docker.
