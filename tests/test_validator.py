import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

import dns.exception
import dns.resolver
from openpyxl import Workbook, load_workbook

from email_validator_tool import Candidate, Cancelled, Result, check_domain, export_results, read_emails, validate_candidates


class Resolver:
    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def resolve(self, domain, kind, lifetime):
        self.calls.append(kind)
        value = self.answers[kind]
        if isinstance(value, Exception):
            raise value
        return value


class ValidatorTests(unittest.TestCase):
    def test_dns_null_mx_and_timeout_do_not_fall_back(self):
        for answer, expected in [([SimpleNamespace(exchange='.')], 'rejected'), (dns.exception.Timeout(), 'review')]:
            resolver = Resolver({'MX': answer})
            self.assertEqual(check_domain('test.com', resolver)[0], expected)
            self.assertEqual(resolver.calls, ['MX'])

    def test_ipv6_fallback(self):
        resolver = Resolver({'MX': dns.resolver.NoAnswer(), 'A': dns.resolver.NoAnswer(), 'AAAA': ['::1']})
        self.assertEqual(check_domain('test.com', resolver)[0], 'clean')

    def test_nonexistent_and_no_records(self):
        self.assertEqual(check_domain('test.com', Resolver({'MX': dns.resolver.NXDOMAIN()}))[0], 'rejected')
        self.assertEqual(check_domain('test.com', Resolver({k: dns.resolver.NoAnswer() for k in ['MX', 'A', 'AAAA']}))[0], 'rejected')

    def test_normalization_duplicates_disposable_and_dns_reuse(self):
        calls = []
        def check(domain):
            calls.append(domain)
            return 'clean', 'Passed'
        inputs = ['one@GMAIL.COM', 'one@gmail.com', 'two@gmail.com', 'not-an-email', 'x@mailinator.com', 'x@sub.mailinator.com']
        results = validate_candidates([Candidate(x, 'test') for x in inputs], domain_checker=check)
        self.assertCountEqual([r.status for r in results], ['clean', 'duplicate', 'clean', 'rejected', 'rejected', 'rejected'])
        self.assertEqual(calls, ['gmail.com'])

    def test_excel_all_sheets_and_invalid_column_values(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'input.xlsx'
            book = Workbook()
            book.active.append(['Name', 'Email Address'])
            book.active.append(['Test', 'not-an-email'])
            book.active.append(['Other', 'a@gmail.com; b@gmail.com'])
            book.create_sheet('Second').append(['Reach Person <c@gmail.com>'])
            book.save(path)
            values = read_emails(path)
            self.assertEqual([r.email for r in values], ['not-an-email', 'a@gmail.com', 'b@gmail.com', 'c@gmail.com'])
            self.assertIn('Second', values[-1].source)

    def test_word_split_runs_tables_headers_and_punctuation(self):
        xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Contact a@</w:t></w:r><w:r><w:t>gmail.com.</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>b@gmail.com</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>'
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'input.docx'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('word/document.xml', xml)
                z.writestr('word/header1.xml', xml.replace('a@', 'c@'))
            self.assertEqual([r.email for r in read_emails(path)], ['a@gmail.com', 'b@gmail.com', 'c@gmail.com', 'b@gmail.com'])

    def test_csv_utf16_and_empty(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'input.csv'
            path.write_text('Name;Email\nPerson;a@gmail.com\nOther;bad-address\n', encoding='utf-16')
            self.assertEqual([r.email for r in read_emails(path)], ['a@gmail.com', 'bad-address'])
            path.write_text('', encoding='utf-8')
            self.assertEqual(read_emails(path), [])

    def test_export_all_statuses_and_formula_protection(self):
        results = [Result('a@gmail.com', 'clean', 'Passed', 'row 1', 'a@gmail.com'), Result('=BAD()', 'rejected', 'Invalid', '@bad', '=BAD()'), Result('b@gmail.com', 'review', 'Timeout', 'row 3', 'b@gmail.com')]
        with tempfile.TemporaryDirectory() as d:
            folder = export_results(results, d, 'input.xlsx')
            other = export_results(results, d, 'input.xlsx')
            self.assertNotEqual(folder, other)
            book = load_workbook(folder / 'validation_results.xlsx')
            self.assertEqual(book['Clean'].max_row, 2)
            self.assertEqual(book['Review'].max_row, 2)
            self.assertEqual(book['Rejected']['A2'].data_type, 's')
            self.assertEqual(book['Rejected']['A2'].value, "'=BAD()")
            book.close()
            self.assertEqual((folder / 'clean_emails.csv').read_text(encoding='utf-8-sig').splitlines(), ['email', 'a@gmail.com'])

    def test_cancellation(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(Cancelled):
            validate_candidates([Candidate('a@gmail.com', 'row')], cancel=cancel)


if __name__ == '__main__':
    unittest.main()
