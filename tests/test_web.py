import io
import re
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from email_validator_tool import Result
from web_app import create_app


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'test-secret', 'APP_PASSWORD': 'test-password', 'DATA_DIR': self.tmp.name})
        self.client = self.app.test_client()
        self.csrf = self.token(self.client)

    def tearDown(self):
        self.app.extensions['job_pool'].shutdown(wait=True)
        self.tmp.cleanup()

    def token(self, client):
        html = client.get('/').get_data(as_text=True)
        return re.search('name="csrf-token" content="([^"]+)"', html).group(1)

    def login(self, client=None, token=None):
        response = (client or self.client).post('/api/login', json={'password':'test-password'}, headers={'X-CSRF-Token': token or self.csrf})
        self.assertEqual(response.status_code, 200)

    def upload(self, filename='input.csv', content=b'Email\na@gmail.com\n'):
        return self.client.post('/api/jobs', data={'file': (io.BytesIO(content), filename)}, headers={'X-CSRF-Token':self.csrf})

    def test_authentication_and_csrf(self):
        self.assertEqual(self.client.get('/api/jobs/missing').status_code, 401)
        self.assertEqual(self.client.post('/api/login', json={'password':'test-password'}).status_code, 403)
        self.assertEqual(self.client.post('/api/login', json={'password':'wrong'}, headers={'X-CSRF-Token':self.csrf}).status_code, 401)
        self.login()

    def test_upload_validation(self):
        self.login()
        self.assertEqual(self.upload('bad.exe').status_code, 400)
        self.assertEqual(self.upload('broken.docx').status_code, 400)
        self.app.config['MAX_CONTENT_LENGTH'] = 1024
        self.assertEqual(self.upload(content=b'x'*2048).status_code, 413)

    def test_job_results_download_isolation_and_expiry(self):
        self.login()
        with patch('web_app.validate_candidates', return_value=[Result('a@gmail.com', 'clean', 'Passed', 'row 1', 'a@gmail.com')]):
            response = self.upload()
            self.assertEqual(response.status_code, 202)
            key = response.json['id']
            deadline = time.monotonic()+5
            while time.monotonic() < deadline:
                result = self.client.get('/api/jobs/'+key).json
                if result['state'] != 'working':
                    break
                time.sleep(.02)
            self.assertEqual(result['state'], 'done')
            self.assertEqual(result['counts']['clean'], 1)
            self.assertEqual(self.client.get(f'/api/jobs/{key}?status=rejected').json['matched'], 0)
            clean = self.client.get(f'/api/jobs/{key}/download/clean')
            self.assertEqual(clean.status_code, 200)
            self.assertIn(b'a@gmail.com', clean.data)
            self.assertEqual(self.client.get(f'/api/jobs/{key}/download/excel').data[:2], b'PK')
            self.assertEqual(self.client.get(f'/api/jobs/{key}/download/all').data[:2], b'PK')
            second = self.app.test_client()
            self.login(second, self.token(second))
            self.assertEqual(second.get('/api/jobs/'+key).status_code, 404)
            self.assertEqual(second.get(f'/api/jobs/{key}/download/clean').status_code, 404)
            self.app.extensions['jobs'][key]['finished'] = time.time()-4000
            self.assertEqual(self.client.get('/api/jobs/'+key).status_code, 404)
            self.assertEqual(list(Path(self.tmp.name).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
