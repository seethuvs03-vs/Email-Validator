"""File extraction, DNS validation and exports for the Email Cleaner app."""
from __future__ import annotations

import csv
import re
import threading
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

import dns.exception
import dns.resolver
from email_validator import EmailNotValidError, validate_email
from openpyxl import Workbook, load_workbook

DISPOSABLE = {
    'mailinator.com', 'tempmail.com', 'temp-mail.org', '10minutemail.com',
    'guerrillamail.com', 'throwawaymail.com', 'yopmail.com', 'trashmail.com',
    'fakeinbox.com', 'getnada.com', 'sharklasers.com', 'maildrop.cc',
    'dispostable.com', 'mintemail.com', 'spamgourmet.com', 'mailnesia.com',
    'tempinbox.com', 'mytemp.email', 'emailondeck.com', 'moakt.com',
}
HEADERS = {'email', 'emails', 'emailaddress', 'emailaddresses', 'e-mail'}


@dataclass
class Candidate:
    email: str
    source: str


@dataclass
class Result:
    email: str
    status: str
    reason: str
    source: str
    original: str


class Cancelled(Exception):
    pass


def checkpoint(cancel):
    if cancel and cancel.is_set():
        raise Cancelled('Validation cancelled.')


def candidates(value, source, email_field=False):
    if value is None:
        return []
    value = str(value).strip()
    if not value:
        return []
    # Keep malformed tokens so they appear in the rejected report as well.
    if email_field:
        chunks = re.split(r'[;,\r\n]+', value)
        tokens = []
        for chunk in chunks:
            bracketed = re.findall(r'<([^<>]+)>', chunk)
            tokens.extend(bracketed or [chunk.strip()])
    else:
        tokens = re.findall(r'[^\s<>;,()\[\]"“”]+@[^\s<>;,()\[\]"“”]*', value)
        tokens = [s.rstrip('.:!?') for s in tokens]
    return [Candidate(s.strip(), source) for s in tokens if s.strip()]


def decode(data):
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16')
    for encoding in ('utf-8-sig', 'cp1252', 'latin1'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass


def read_emails(path, cancel=None, max_candidates=None):
    path = Path(path)
    found = []

    def add(values):
        found.extend(values)
        if max_candidates is not None and len(found) > max_candidates:
            raise ValueError(f'Too many email candidates; limit is {max_candidates:,}.')

    def rows_to_candidates(rows, sheet):
        email_columns = set()
        for number, row in enumerate(rows, 1):
            checkpoint(cancel)
            for col, value in enumerate(row):
                if value is None:
                    continue
                label = re.sub(r'[\s_]+', '', str(value).lower())
                if label in HEADERS:
                    email_columns.add(col)
                    continue
                add(candidates(value, f'{sheet}: row {number}, column {col + 1}', col in email_columns))

    ext = path.suffix.lower()
    if ext == '.xlsx':
        book = load_workbook(path, read_only=True, data_only=True)
        try:
            for sheet in book:
                rows_to_candidates(sheet.iter_rows(values_only=True), sheet.title)
        finally:
            book.close()
    elif ext == '.xls':
        import xlrd
        book = xlrd.open_workbook(str(path), on_demand=True)
        try:
            for sheet in book.sheets():
                rows_to_candidates((sheet.row_values(i) for i in range(sheet.nrows)), sheet.name)
        finally:
            book.release_resources()
    elif ext in {'.csv', '.tsv'}:
        content = decode(path.read_bytes())
        import io
        try:
            dialect = csv.Sniffer().sniff(content[:8192], delimiters=',;\t')
        except csv.Error:
            dialect = csv.excel_tab if ext == '.tsv' else csv.excel
        rows_to_candidates(csv.reader(io.StringIO(content), dialect), path.name)
    elif ext == '.docx':
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        with zipfile.ZipFile(path) as archive:
            parts = [n for n in archive.namelist() if re.fullmatch(r'word/(document|header\d+|footer\d+|footnotes|endnotes)\.xml', n)]
            if 'word/document.xml' not in parts:
                raise ValueError('This file is not a valid Word document.')
            for part in sorted(parts):
                checkpoint(cancel)
                root = ElementTree.fromstring(archive.read(part))
                for i, paragraph in enumerate(root.findall('.//w:p', ns), 1):
                    text = ''.join((' ' if el.tag.rsplit('}', 1)[-1] in {'tab', 'br'} else el.text or '')
                                   for el in paragraph.iter() if el.tag.rsplit('}', 1)[-1] in {'t', 'tab', 'br'})
                    add(candidates(text, f'{Path(part).stem}: paragraph {i}'))
    elif ext == '.txt':
        for i, line in enumerate(decode(path.read_bytes()).splitlines(), 1):
            checkpoint(cancel)
            add(candidates(line, f'Line {i}', email_field=True))
    elif ext == '.doc':
        raise ValueError('Please open this legacy Word file in Word and Save As .docx first.')
    else:
        raise ValueError('Choose an .xlsx, .xls, .docx, .csv, .tsv or .txt file.')
    return found


def check_domain(domain, resolver=None):
    resolver = resolver or dns.resolver.Resolver()
    def resolve(kind):
        return resolver.resolve(domain, kind, lifetime=4)
    try:
        try:
            mx = resolve('MX')
            usable = [r for r in mx if str(r.exchange).rstrip('.')]
            if not usable:
                return 'rejected', 'Domain explicitly refuses email (null MX).'
            return 'clean', 'Syntax and mail-domain checks passed.'
        except dns.resolver.NoAnswer:
            # RFC fallback only when MX is absent, never on a timeout.
            for kind in ('A', 'AAAA'):
                try:
                    if resolve(kind):
                        return 'clean', 'Syntax passed; domain has a fallback mail address record.'
                except dns.resolver.NoAnswer:
                    continue
            return 'rejected', 'No MX, A or AAAA mail-routing record.'
    except dns.resolver.NXDOMAIN:
        return 'rejected', 'Domain does not exist.'
    except (dns.exception.DNSException, OSError):
        return 'review', 'DNS check unavailable or timed out. Retry later.'
    return 'review', 'DNS check returned no usable result.'


def validate_candidates(items, progress=None, cancel=None, extra_domains=(), domain_checker=check_domain):
    results = []
    pending = []
    seen = set()
    blocked = DISPOSABLE | {s.strip().lower().rstrip('.') for s in extra_domains if s.strip() and not s.startswith('#')}
    for item in items:
        checkpoint(cancel)
        original = item.email
        try:
            parsed = validate_email(original, check_deliverability=False)
            normalized, domain = parsed.normalized, parsed.ascii_domain
        except EmailNotValidError as exc:
            results.append(Result(original, 'rejected', str(exc), item.source, original))
            continue
        # Domain casing is insensitive; local-part casing is preserved.
        if normalized in seen:
            results.append(Result(normalized, 'duplicate', 'Duplicate normalized address.', item.source, original))
            continue
        seen.add(normalized)
        if any(domain == d or domain.endswith('.' + d) for d in blocked):
            results.append(Result(normalized, 'rejected', 'Known disposable email domain.', item.source, original))
        else:
            pending.append((item, normalized, domain))
    domains = sorted({domain for _, _, domain in pending})
    checks = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = {pool.submit(domain_checker, d): d for d in domains}
        for future in as_completed(jobs):
            if cancel and cancel.is_set():
                for job in jobs:
                    job.cancel()
                raise Cancelled()
            checks[jobs[future]] = future.result()
            if progress:
                progress(len(checks), len(domains))
    for item, normalized, domain in pending:
        status, reason = checks[domain]
        results.append(Result(normalized, status, reason, item.source, item.email))
    return results


def export_results(results, destination, source):
    """Create a new result folder; never overwrite another run."""
    folder = Path(destination) / ('Email results ' + datetime.now().strftime('%Y-%m-%d %H%M%S_%f'))
    folder.mkdir(parents=True, exist_ok=False)
    headers = ['email', 'status', 'reason', 'source', 'original']
    def safe(value):
        text = str(value)
        return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text
    book = Workbook()
    summary = book.active
    summary.title = 'Summary'
    counts = Counter(r.status for r in results)
    for row in [('Input file', str(source)), ('Candidates found', len(results)), *[(s.title(), counts[s]) for s in ('clean', 'rejected', 'review', 'duplicate')],
                ('Scope', 'Clean means syntax and domain checks passed; mailbox existence is not verified.')]:
        summary.append([safe(v) for v in row])
    for status in ('clean', 'rejected', 'review', 'duplicate'):
        rows = [[getattr(r, h) for h in headers] for r in results if r.status == status]
        sheet = book.create_sheet(status.title())
        sheet.append(headers)
        for row in rows:
            sheet.append([safe(v) for v in row])
        with (folder / f'{status}_emails.csv').open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['email'] if status == 'clean' else headers)
            writer.writerows([[safe(row[0])] if status == 'clean' else [safe(v) for v in row] for row in rows])
    from openpyxl.styles import Font, PatternFill
    for sheet in book:
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(color='FFFFFF', bold=True)
            cell.fill = PatternFill('solid', fgColor='183D4A')
        for col, width in [('A', 42), ('B', 24), ('C', 70), ('D', 48), ('E', 42)]:
            sheet.column_dimensions[col].width = width
    book.save(folder / 'validation_results.xlsx')
    return folder


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Validate addresses from Excel, Word, CSV or text.')
    parser.add_argument('input')
    parser.add_argument('--outdir', default='.')
    args = parser.parse_args()
    output = export_results(validate_candidates(read_emails(args.input)), args.outdir, args.input)
    print(f'Results saved to {output}')
