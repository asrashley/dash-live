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

import logging
import unittest

import flask

from dashlive.management.base import LoginFailureException
from dashlive.management.populate import PopulateDatabase

from .flask_base import FlaskTestBase
from .http_client import ClientHttpSession

class TestPopulateDatabase(FlaskTestBase):
    def test_login_failure(self) -> None:
        pd = PopulateDatabase(
            url=flask.url_for('home'),
            username='unknown',
            password='secret',
            session=ClientHttpSession(self.client))
        with self.assertRaises(LoginFailureException):
            jsonfile = self.FIXTURES_PATH / 'upload.json'
            pd.populate_database(str(jsonfile))

    def test_file_not_found(self) -> None:
        self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)
        pd = PopulateDatabase(
            url=flask.url_for('home'),
            username=self.MEDIA_USER,
            password=self.MEDIA_PASSWORD,
            session=ClientHttpSession(self.client))
        with self.assertRaises(FileNotFoundError):
            pd.populate_database('script.json')

    def test_populate_database(self) -> None:
        self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)
        tmpdir = self.create_upload_folder()
        with self.app.app_context():
            self.app.config['BLOB_FOLDER'] = tmpdir
        pd = PopulateDatabase(
            url=flask.url_for('home'),
            username=self.MEDIA_USER,
            password=self.MEDIA_PASSWORD,
            session=ClientHttpSession(self.client))
        jsonfile = self.FIXTURES_PATH / 'upload.json'
        result = pd.populate_database(str(jsonfile))
        self.assertTrue(result)


if __name__ == "__main__":
    mm_log = logging.getLogger('PopulateDatabase')
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s: %(funcName)s:%(lineno)d: %(message)s'))
    mm_log.addHandler(ch)
    # logging.getLogger().setLevel(logging.DEBUG)
    # mm_log.setLevel(logging.DEBUG)
    unittest.main()
