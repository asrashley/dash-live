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
import unittest

import flask

from dashlive.server import models
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
            jsonfile = self.FIXTURES_PATH / 'upload_v2.json'
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

    def test_populate_database_using_v1_json(self) -> None:
        self.check_populate_database('upload_v1.json', 1)

    def test_populate_database_using_v2_json(self) -> None:
        self.check_populate_database('upload_v2.json', 2)

    def check_populate_database(self, fixture_name: str, version: int) -> None:
        self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)
        tmpdir = self.create_upload_folder()
        with self.app.app_context():
            self.app.config['BLOB_FOLDER'] = tmpdir
        pd = PopulateDatabase(
            url=flask.url_for('home'),
            username=self.MEDIA_USER,
            password=self.MEDIA_PASSWORD,
            session=ClientHttpSession(self.client))
        jsonfile = self.FIXTURES_PATH / fixture_name
        self.assertTrue(jsonfile.exists())
        result = pd.populate_database(str(jsonfile))
        self.assertTrue(result)
        self.check_database_results(jsonfile, version)

    def check_database_results(self, jsonfilename: Path, version: int) -> None:
        with jsonfilename.open('rt', encoding='utf-8') as src:
            upload_js = json.load(src)
        if version == 1:
            self.check_database_for_v1_results(upload_js)
        else:
            self.check_database_for_v2_results(upload_js)

    def check_database_for_v1_results(self, upload_js: dict) -> None:
        for exp_stream in upload_js['streams']:
            todo = {Path(fname).stem for fname in upload_js['files']}
            with self.app.app_context():
                act_stream = models.Stream.get(directory=exp_stream['prefix'])
                self.assertIsNotNone(act_stream)
                for field in {'title', 'marlin_la_url', 'playready_la_url'}:
                    self.assertEqual(exp_stream.get(field), getattr(act_stream, field))
                for mf in act_stream.media_files:
                    self.assertIn(mf.name, todo)
                    todo.remove(mf.name)
            self.assertEqual(len(todo), 0)
            self.assertIsNone(act_stream.timing_reference)

    def check_database_for_v2_results(self, upload_js: dict) -> None:
        for exp_stream in upload_js['streams']:
            todo = {Path(fname).stem for fname in exp_stream['files']}
            with self.app.app_context():
                act_stream = models.Stream.get(directory=exp_stream['directory'])
                self.assertIsNotNone(act_stream)
                for field in {'title', 'marlin_la_url', 'playready_la_url'}:
                    self.assertEqual(exp_stream[field], getattr(act_stream, field))
                for mf in act_stream.media_files:
                    self.assertIn(mf.name, todo)
                    todo.remove(mf.name)
            self.assertEqual(len(todo), 0)
            self.assertIsNotNone(act_stream.timing_reference)
            self.assertEqual(
                Path(exp_stream['timing_ref']).stem,
                act_stream.timing_reference.media_name)

    def test_populate_database_using_command_line(self) -> None:
        jsonfile = self.FIXTURES_PATH / 'upload_v2.json'
        self.assertTrue(jsonfile.exists())
        args: list[str] = [
            '--username', self.MEDIA_USER,
            '--password', self.MEDIA_PASSWORD,
            '--host', flask.url_for('home'),
            '--silent',
            str(jsonfile),
        ]
        tmpdir = self.create_upload_folder()
        with self.app.app_context():
            self.app.config['BLOB_FOLDER'] = tmpdir
        with unittest.mock.patch('requests.Session') as mock:
            mock.return_value = ClientHttpSession(self.client)
            PopulateDatabase.main(args)
        self.check_database_results(jsonfile, 2)

    def test_translate_v1_json_with_streams(self) -> None:
        v1js = {
            "keys": [{
                "computed": False,
                "key": "533a583a843436a536fbe2a5821c4b6c",
                "kid": "c001de8e567b5fcfbc22c565ed5bda24"
            }, {
                "computed": True,
                "kid": "1ab45440532c439994dc5c5ad9584bac"
            }],
            "streams": [{
                "prefix": "bbb",
                "title": "Big Buck Bunny",
                "marlin_la_url": "ms3://ms3.test.expressplay.com:8443/hms/ms3/rights/?b=...",
                "playready_la_url": "https://test.playready.microsoft.com/service/rightsmanager.asmx?cfg={cfgs}",
            }, {
                "prefix": "tears",
                "title": "Tears of Steel",
            }],
            "files": [
                "bbb_a1.mp4", "bbb_a1_enc.mp4", "bbb_a2.mp4", "bbb_t1.mp4",
                "tears_a1.mp4", "tears_v2.mp4", "tears_v1.mp4", "tears_t1.mp4"
            ]
        }
        pd = PopulateDatabase(
            url=flask.url_for('home'),
            username=self.MEDIA_USER,
            password=self.MEDIA_PASSWORD,
            session=ClientHttpSession(self.client))
        result = pd.convert_v1_json_data(v1js)
        expected = {
            "keys": [{
                "computed": False,
                "key": "533a583a843436a536fbe2a5821c4b6c",
                "kid": "c001de8e567b5fcfbc22c565ed5bda24"
            }, {
                "computed": True,
                "kid": "1ab45440532c439994dc5c5ad9584bac"
            }],
            "streams": [{
                "directory": "bbb",
                "title": "Big Buck Bunny",
                "marlin_la_url": "ms3://ms3.test.expressplay.com:8443/hms/ms3/rights/?b=...",
                "playready_la_url": "https://test.playready.microsoft.com/service/rightsmanager.asmx?cfg={cfgs}",
                "timing_ref": None,
                "files": [
                    "bbb_a1.mp4", "bbb_a1_enc.mp4", "bbb_a2.mp4", "bbb_t1.mp4"
                ]
            }, {
                "directory": "tears",
                "title": "Tears of Steel",
                "timing_ref": None,
                "files": [
                    "tears_a1.mp4", "tears_t1.mp4", "tears_v1.mp4", "tears_v2.mp4"
                ]
            }]
        }
        self.maxDiff = None
        self.assertDictEqual(expected, result)

    def test_translate_v1_json_no_streams(self) -> None:
        v1js = {
            "keys": [{
                "computed": False,
                "key": "533a583a843436a536fbe2a5821c4b6c",
                "kid": "c001de8e567b5fcfbc22c565ed5bda24"
            }, {
                "computed": True,
                "kid": "1ab45440532c439994dc5c5ad9584bac"
            }],
            "files": [
                "bbb_a1.mp4", "bbb_a1_enc.mp4", "bbb_a2.mp4", "bbb_t1.mp4",
                "tears_a1.mp4", "tears_v2.mp4", "tears_v1.mp4", "tears_t1.mp4"
            ]
        }
        pd = PopulateDatabase(
            url=flask.url_for('home'),
            username=self.MEDIA_USER,
            password=self.MEDIA_PASSWORD,
            session=ClientHttpSession(self.client))
        result = pd.convert_v1_json_data(v1js)
        expected = {
            "keys": [{
                "computed": False,
                "key": "533a583a843436a536fbe2a5821c4b6c",
                "kid": "c001de8e567b5fcfbc22c565ed5bda24"
            }, {
                "computed": True,
                "kid": "1ab45440532c439994dc5c5ad9584bac"
            }],
            "streams": [{
                "directory": "bbb",
                "title": "bbb",
                "timing_ref": None,
                "files": [
                    "bbb_a1.mp4", "bbb_a1_enc.mp4", "bbb_a2.mp4", "bbb_t1.mp4"
                ]
            }, {
                "directory": "tears",
                "title": "tears",
                "timing_ref": None,
                "files": [
                    "tears_a1.mp4", "tears_t1.mp4", "tears_v1.mp4", "tears_v2.mp4"
                ]
            }]
        }
        self.maxDiff = None
        self.assertDictEqual(expected, result)

    def test_translate_v1_json_with_absolute_filenames(self) -> None:
        v1js = {
            "keys": [{
                "computed": False,
                "key": "533a583a843436a536fbe2a5821c4b6c",
                "kid": "c001de8e567b5fcfbc22c565ed5bda24"
            }],
            "streams": [{
                "prefix": "bbb",
                "title": "Big Buck Bunny"
            }],
            "files": [
                "media/bbb/2023-08-30T20-00-00Z/bbb_a1.mp4",
                "media/bbb/2023-08-30T20-00-00Z/bbb_a1_enc.mp4",
                "media/bbb/2023-08-30T20-00-00Z/bbb_a2.mp4",
                "media/bbb/2023-08-30T20-00-00Z/bbb_t1.mp4"
            ]
        }
        pd = PopulateDatabase(
            url=flask.url_for('home'),
            username=self.MEDIA_USER,
            password=self.MEDIA_PASSWORD,
            session=ClientHttpSession(self.client))
        result = pd.convert_v1_json_data(v1js)
        expected = {
            "keys": [{
                "computed": False,
                "key": "533a583a843436a536fbe2a5821c4b6c",
                "kid": "c001de8e567b5fcfbc22c565ed5bda24"
            }],
            "streams": [{
                "directory": "bbb",
                "title": "Big Buck Bunny",
                "timing_ref": None,
                "files": [
                    "media/bbb/2023-08-30T20-00-00Z/bbb_a1.mp4",
                    "media/bbb/2023-08-30T20-00-00Z/bbb_a1_enc.mp4",
                    "media/bbb/2023-08-30T20-00-00Z/bbb_a2.mp4",
                    "media/bbb/2023-08-30T20-00-00Z/bbb_t1.mp4"
                ]
            }]
        }
        self.maxDiff = None
        self.assertDictEqual(expected, result)


if __name__ == "__main__":
    mm_log = logging.getLogger('PopulateDatabase')
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s: %(funcName)s:%(lineno)d: %(message)s'))
    mm_log.addHandler(ch)
    # logging.getLogger().setLevel(logging.DEBUG)
    # mm_log.setLevel(logging.DEBUG)
    unittest.main()
