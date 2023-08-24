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

from dashlive.management.base import LoginFailureException
from dashlive.management.download import DownloadDatabase
from dashlive.server import models

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
        with self.app.app_context():
            stream = models.Stream(directory='abc', title='Test Stream 2')
            stream.add()
            ky = models.Key(hkid='c001de8e567b5fcfbc22c565ed5bda24',
                            hkey='533a583a843436a536fbe2a5821c4b6c',
                            computed=False)
            ky.add()
            models.db.session.commit()
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
        self.assertIn('keys', js)
        self.assertEqual(len(js['keys']), 2)
        self.assertIn('streams', js)
        self.assertEqual(len(js['streams']), 2)
        todo = set()
        with self.app.app_context():
            for st in models.Stream.all():
                todo.add(st.directory)
        for dirname in ['fixtures', 'abc']:
            self.assertIn(dirname, todo)
            todo.remove(dirname)
            self.check_json_file(Path(tmpdir), dirname)

    def check_json_file(self, tmpdir: Path, dirname: str) -> None:
        jsonfile = tmpdir / dirname / f'{dirname}.json'
        self.assertTrue(jsonfile.exists(), msg=f'{jsonfile} does not exist')
        with jsonfile.open('rt', encoding='utf-8') as src:
            js = json.load(src)
        expected = {
            'keys': [],
            'streams': [],
        }
        with self.app.app_context():
            for kp in models.Key.all(order_by=[models.Key.hkid]):
                expected['keys'].append({
                    'alg': kp.ALG,
                    'key': kp.KEY.hex,
                    'kid': kp.KID.hex,
                    'computed': kp.computed,
                })
            stream = models.Stream.get(directory=dirname)
            self.assertIsNotNone(stream)
            st = stream.to_dict(only={
                'directory', 'marlin_la_url', 'playready_la_url', 'title', 'timing_ref'})
            st['files'] = [f'{mf.name}.mp4' for mf in stream.media_files]
            st['files'].sort()
            if st['timing_ref']:
                st['timing_ref'] = st['timing_ref']['media_name']
            expected['streams'] = [st]
        self.maxDiff = None
        self.assertDictEqual(expected, js)


if __name__ == "__main__":
    mm_log = logging.getLogger('DownloadDatabase')
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s: %(funcName)s:%(lineno)d: %(message)s'))
    mm_log.addHandler(ch)
    # logging.getLogger().setLevel(logging.DEBUG)
    # mm_log.setLevel(logging.DEBUG)
    unittest.main()
