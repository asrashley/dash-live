#############################################################################
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import unittest
import urllib.parse

import flask

from dashlive.utils.json_object import JsonObject
from dashlive.management.http import HttpSession, HttpResponse
from dashlive.management.base import LoginFailureException
from dashlive.management.download import DownloadDatabase

from .flask_base import FlaskTestBase
from .http_client import ClientHttpSession

class TestDownloadDatabase(FlaskTestBase):
    def test_login_failure(self) -> None:
        dd = DownloadDatabase(
            url=flask.url_for('home'),
            username='unknown',
            password='secret',
            session=ClientHttpSession(self.client))
        with self.assertRaises(LoginFailureException):
            dd.download_database(Path('/tmp'))

    def test_download_database(self) -> None:
        self.setup_media()
        self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)
        tmpdir = self.create_upload_folder()
        dd = DownloadDatabase(
            url=flask.url_for('home'),
            username=self.MEDIA_USER,
            password=self.MEDIA_PASSWORD,
            session=ClientHttpSession(self.client))
        result = dd.download_database(Path(tmpdir))
        self.assertTrue(result)
        jsonfile = Path(tmpdir) / dd.OUTPUT_NAME
        self.assertTrue(jsonfile.exists(), msg=f'{jsonfile} does not exist')
        with jsonfile.open('rt', encoding='utf-8') as src:
            js = json.load(src)
        jsonfile = Path(tmpdir) / 'fixtures' / 'fixtures.json'
        self.assertTrue(jsonfile.exists(), msg=f'{jsonfile} does not exist')
        with jsonfile.open('rt', encoding='utf-8') as src:
            js = json.load(src)

if __name__ == "__main__":
    mm_log = logging.getLogger('DownloadDatabase')
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s: %(funcName)s:%(lineno)d: %(message)s'))
    mm_log.addHandler(ch)
    # logging.getLogger().setLevel(logging.DEBUG)
    # mm_log.setLevel(logging.DEBUG)
    unittest.main()
