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
import shutil
import unittest
from unittest.mock import patch

import flask

import dashlive.upload
from dashlive.server import models
from dashlive.management.populate import PopulateDatabase
from dashlive.management.backend_db import BackendDatabaseAccess
from dashlive.management.frontend_db import FrontendDatabaseAccess

from .mixins.flask_base import FlaskTestBase
from .mixins.stream_fixtures import BBB_FIXTURE
from .http_client import ClientHttpSession

class TestPopulateDatabase(FlaskTestBase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.log_context:
            dash_log = logging.getLogger('DashValidator')
            dash_log.removeFilter(cls.log_context)
            cls.log_context = None
        logging.disable(logging.NOTSET)
        super().tearDownClass()

    def test_login_failure(self) -> None:
        fda = FrontendDatabaseAccess(
            url=flask.url_for('home'),
            username='unknown',
            password='secret',
            session=ClientHttpSession(self.client))
        self.assertFalse(fda.login())
        pd = PopulateDatabase(fda)
        jsonfile = self.fixtures_folder / 'bbb' / 'upload_v2.json'
        self.assertFalse(pd.populate_database(str(jsonfile)))

    def test_file_not_found(self) -> None:
        self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)
        fda = FrontendDatabaseAccess(
            url=flask.url_for('home'),
            username=self.MEDIA_USER,
            password=self.MEDIA_PASSWORD,
            session=ClientHttpSession(self.client))
        pd = PopulateDatabase(fda)
        with self.assertRaises(FileNotFoundError):
            pd.populate_database('script.json')

    def test_populate_database_using_v1_json(self) -> None:
        self.check_populate_database('upload_v1.json', 1)

    def test_populate_database_using_v2_json(self) -> None:
        self.check_populate_database('upload_v2.json', 2)

    def check_populate_database(self, fixture_name: str, version: int) -> None:
        self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)
        da = FrontendDatabaseAccess(
            url=flask.url_for('home'),
            username=self.MEDIA_USER,
            password=self.MEDIA_PASSWORD,
            session=ClientHttpSession(self.client))
        pd = PopulateDatabase(da)
        jsonfile: Path = self.fixtures_folder / BBB_FIXTURE.name / fixture_name
        self.assertTrue(jsonfile.exists())
        result: bool = pd.populate_database(str(jsonfile))
        self.assertTrue(result, msg='populate_database() failed')
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
        jsonfile = self.fixtures_folder / BBB_FIXTURE.name / 'upload_v2.json'
        self.assertTrue(jsonfile.exists())
        args: list[str] = [
            '--username', self.MEDIA_USER,
            '--password', self.MEDIA_PASSWORD,
            '--host', flask.url_for('home'),
            '--silent',
            str(jsonfile),
        ]
        with patch('requests.Session') as mock:
            mock.return_value = ClientHttpSession(self.client)
            dashlive.upload.main(args)
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
        fda = FrontendDatabaseAccess(
            url=flask.url_for('home'),
            username=self.MEDIA_USER,
            password=self.MEDIA_PASSWORD,
            session=ClientHttpSession(self.client))
        pd = PopulateDatabase(fda)
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
        fda = FrontendDatabaseAccess(
            url=flask.url_for('home'),
            username=self.MEDIA_USER,
            password=self.MEDIA_PASSWORD,
            session=ClientHttpSession(self.client))
        pd = PopulateDatabase(fda)
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
        fda = FrontendDatabaseAccess(
            url=flask.url_for('home'),
            username=self.MEDIA_USER,
            password=self.MEDIA_PASSWORD,
            session=ClientHttpSession(self.client))
        pd = PopulateDatabase(fda)
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

    def test_populate_database_using_backend(self) -> None:
        # add a temporary route, so that BackendDatabaseAccess has its correct
        # Flask context (e.g. current_user being the logged in user)
        @self.app.route("/test-populate")
        def populate_db():
            da = BackendDatabaseAccess()
            pd = PopulateDatabase(da)
            self.assertTrue(jsonfile.exists())
            result = pd.populate_database(str(jsonfile))
            self.assertTrue(result, msg='populate_database() failed')
            return flask.make_response('done')
        jsonfile = self.fixtures_folder / BBB_FIXTURE.name / 'upload_v2.json'
        upload = Path(self.app.config['UPLOAD_FOLDER'])
        subdir: Path = upload / 'verifier-dest'
        subdir.mkdir()
        js_dest: Path = subdir / 'script.json'
        shutil.copyfile(str(jsonfile), js_dest)
        with open(jsonfile) as js:
            config = json.load(js)
        for stream in config['streams']:
            for fname in stream['files']:
                shutil.copyfile(
                    self.fixtures_folder / BBB_FIXTURE.name / fname,
                    subdir / fname)
        jsonfile = js_dest
        self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)
        response = self.client.get("/test-populate")
        self.assertEqual(response.status_code, 200)
        self.check_database_results(jsonfile, 2)


if __name__ == "__main__":
    format = r"%(asctime)s %(levelname)-8s:%(filename)s@%(lineno)d: %(message)s"
    logging.basicConfig(format=format)
    # logging.getLogger().setLevel(logging.INFO)
    # logging.getLogger('management').setLevel(logging.DEBUG)
    unittest.main()
