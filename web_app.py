"""Single-process, multi-user web service for company-hosted email validation."""
import hmac
import os
import secrets
import shutil
import tempfile
import threading
import time
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file, session
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

from email_validator_tool import read_emails, validate_candidates, export_results


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=os.getenv('SECRET_KEY'), APP_PASSWORD=os.getenv('APP_PASSWORD'),
                      MAX_CONTENT_LENGTH=20 * 1024 * 1024, SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE') == '1',
                      JOB_TTL=3600, MAX_JOBS=20, MAX_ACTIVE=2,
                      DATA_DIR=os.getenv('DATA_DIR', str(Path(__file__).parent / 'server-data')))
    if config:
        app.config.update(config)
    if not app.config['SECRET_KEY'] or not app.config['APP_PASSWORD']:
        raise RuntimeError('Set SECRET_KEY and APP_PASSWORD, or run Setup_Server.bat first.')
    root = Path(app.config['DATA_DIR']).resolve()
    root.mkdir(parents=True, exist_ok=True)
    jobs, failures = {}, {}
    lock = threading.RLock()
    pool = ThreadPoolExecutor(max_workers=app.config['MAX_ACTIVE'], thread_name_prefix='validation')
    app.extensions['jobs'] = jobs
    app.extensions['job_pool'] = pool

    def cleanup():
        now = time.time()
        with lock:
            for key, job in list(jobs.items()):
                if job['state'] in {'done', 'error'} and now - job['finished'] > app.config['JOB_TTL']:
                    shutil.rmtree(job['folder'], ignore_errors=True)
                    del jobs[key]
            # Also remove abandoned directories from a previous server process.
            active_dirs = {str(j['folder']) for j in jobs.values()}
            for folder in root.glob('job-*'):
                if str(folder) not in active_dirs and folder.is_dir() and now - folder.stat().st_mtime > app.config['JOB_TTL']:
                    shutil.rmtree(folder, ignore_errors=True)
            for ip, (_, until) in list(failures.items()):
                if until < now:
                    del failures[ip]

    def janitor():
        while True:
            time.sleep(60)
            cleanup()
    if not app.testing:
        threading.Thread(target=janitor, daemon=True).start()

    @app.before_request
    def guard():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_urlsafe(32)
        if request.path.startswith('/api/'):
            if request.method == 'POST' and not hmac.compare_digest(request.headers.get('X-CSRF-Token', ''), session['csrf']):
                return jsonify(error='Your session expired. Refresh the page and try again.'), 403
            if request.path != '/api/login' and not session.get('owner'):
                return jsonify(error='Please sign in to continue.'), 401

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify(error='File too large. Maximum upload size is 20 MB.' if exc.code == 413 else exc.description), exc.code

    @app.get('/')
    def index():
        return render_template('index.html', signed_in=bool(session.get('owner')), csrf=session['csrf'])

    @app.get('/health')
    def health():
        return jsonify(status='ok')

    @app.post('/api/login')
    def login():
        ip = request.remote_addr or 'unknown'
        with lock:
            count, until = failures.get(ip, (0, 0))
            if time.time() > until:
                count = 0
            if count >= 10:
                return jsonify(error='Too many attempts. Try again in 15 minutes.'), 429
            payload = request.get_json(silent=True)
            password = payload.get('password', '') if isinstance(payload, dict) else ''
            if not isinstance(password, str) or not hmac.compare_digest(password.encode(), app.config['APP_PASSWORD'].encode()):
                failures[ip] = (count + 1, time.time() + 900)
                return jsonify(error='The password is incorrect.'), 401
            failures.pop(ip, None)
        session['owner'] = secrets.token_urlsafe(32)
        return jsonify(ok=True)

    @app.post('/api/logout')
    def logout():
        session.clear()
        return jsonify(ok=True)

    def run_job(key, path):
        job = jobs[key]
        try:
            items = read_emails(path, max_candidates=50000)
            if len(items) > 50000:
                raise ValueError('This file contains over 50,000 candidates. Split it into smaller files.')
            with lock:
                job.update(total=len(items), stage='Checking email domains')
            def progress(n, total):
                with lock:
                    job.update(progress=round(n / max(total, 1) * 90), stage=f'Checked {n:,} of {total:,} domains')
            results = validate_candidates(items, progress=progress)
            with lock:
                job.update(stage='Preparing downloads', progress=95)
            output = export_results(results, job['folder'], job['name'])
            with zipfile.ZipFile(job['folder'] / 'all_results.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
                for file in output.iterdir():
                    archive.write(file, file.name)
            with lock:
                job.update(state='done', finished=time.time(), progress=100, stage='Validation complete',
                           results=[asdict(r) for r in results], counts=dict(Counter(r.status for r in results)), output=output)
        except (ValueError, zipfile.BadZipFile, KeyError):
            with lock:
                job.update(state='error', finished=time.time(), error='Could not read this file. Check that it is a valid, unencrypted document with no more than 50,000 email candidates.')
        except Exception:
            app.logger.exception('Validation job failed: %s', key)
            with lock:
                job.update(state='error', finished=time.time(), error='Validation failed. Try again or contact your server administrator.')
        finally:
            path.unlink(missing_ok=True)
            with lock:
                job['finished'] = time.time()

    @app.post('/api/jobs')
    def upload():
        cleanup()
        file = request.files.get('file')
        if not file or not file.filename:
            return jsonify(error='Choose a file first.'), 400
        name = secure_filename(file.filename) or 'upload'
        suffix = Path(name).suffix.lower()
        if suffix not in {'.xlsx', '.xls', '.docx', '.csv', '.tsv', '.txt'}:
            return jsonify(error='Use Excel, Word .docx, CSV, TSV or text. Save .doc files as .docx first.'), 400
        with lock:
            if len(jobs) >= app.config['MAX_JOBS'] or sum(j['state'] == 'working' for j in jobs.values()) >= app.config['MAX_ACTIVE']:
                return jsonify(error='The server is busy. Please try again shortly.'), 429
            key = secrets.token_urlsafe(24)
            folder = Path(tempfile.mkdtemp(prefix='job-', dir=root))
            path = folder / ('input' + suffix)
            try:
                file.save(path)
                if suffix in {'.xlsx', '.docx'}:
                    with zipfile.ZipFile(path) as z:
                        entries = z.infolist()
                        if len(entries) > 10000 or sum(e.file_size for e in entries) > 100 * 1024 * 1024:
                            raise ValueError('Document expands beyond the 100 MB limit. Split it into smaller files.')
            except (ValueError, zipfile.BadZipFile):
                shutil.rmtree(folder, ignore_errors=True)
                return jsonify(error='Invalid or oversized document. Use an unencrypted file that expands to less than 100 MB.'), 400
            except OSError:
                shutil.rmtree(folder, ignore_errors=True)
                app.logger.exception('Cannot save uploaded file')
                return jsonify(error='The server cannot save uploads. Ask IT to check the server-data folder permissions and free disk space.'), 503
            jobs[key] = dict(owner=session['owner'], folder=folder, name=name, state='working', progress=0,
                             stage='Reading your file', total=0, finished=0)
            pool.submit(run_job, key, path)
        return jsonify(id=key), 202

    def owned_job(key):
        from flask import abort
        cleanup()
        job = jobs.get(key)
        if not job or job['owner'] != session['owner']:
            abort(404, description='Results are unavailable or have expired. Upload your file again.')
        return job

    @app.get('/api/jobs/<key>')
    def status(key):
        with lock:
            job = owned_job(key)
            data = {k: job[k] for k in ('name', 'state', 'progress', 'stage', 'total')}
            if job['state'] == 'error':
                data['error'] = job['error']
            if job['state'] == 'done':
                category = request.args.get('status', 'all')
                try:
                    page = max(1, int(request.args.get('page', '1')))
                except ValueError:
                    return jsonify(error='Invalid page.'), 400
                rows = [r for r in job['results'] if category == 'all' or r['status'] == category]
                data.update(counts=job['counts'], rows=rows[(page-1)*50:page*50], matched=len(rows), page=page)
            return jsonify(data)

    @app.get('/api/jobs/<key>/download/<kind>')
    def download(key, kind):
        with lock:
            job = owned_job(key)
            if job['state'] != 'done':
                return jsonify(error='Results are not ready yet.'), 409
            names = {'clean': 'clean_emails.csv', 'excel': 'validation_results.xlsx', 'all': 'all_results.zip'}
            if kind not in names:
                return jsonify(error='Unknown download.'), 404
            path = (job['folder'] if kind == 'all' else job['output']) / names[kind]
            # Copy into memory so expiry cleanup cannot interrupt an open download on Windows.
            import io
            return send_file(io.BytesIO(path.read_bytes()), as_attachment=True, download_name=names[kind])

    return app
