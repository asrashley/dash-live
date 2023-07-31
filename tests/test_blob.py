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

import datetime
from pathlib import Path
import unittest

from dashlive.server.models import Blob

from .flask_base import FlaskTestBase

class TestBlobModel(FlaskTestBase):

    def test_to_json(self):
        with self.app.app_context():
            blob = Blob(
                filename='filename.mp4',
                size=123,
                created=datetime.datetime(2023, 6, 20, 3, 4, 5),
                sha1_hash='609c4d156f961c4768e5a26d641cd1fdc439f7f5',
                content_type='video/mp4',
                auto_delete=True)
            blob.add(commit=True)
            actual = blob.toJSON(pure=False)
            expected = {
                'pk': blob.pk,
                'filename': 'filename.mp4',
                'size': 123,
                'created': datetime.datetime(2023, 6, 20, 3, 4, 5),
                'sha1_hash': '609c4d156f961c4768e5a26d641cd1fdc439f7f5',
                'content_type': 'video/mp4',
                'auto_delete': True
            }
            self.assertDictEqual(expected, actual)
            actual = blob.toJSON(pure=True)
            expected['created'] = '2023-06-20T03:04:05Z'
            self.assertDictEqual(expected, actual)

    def test_open_file(self) -> None:
        tmpdir, filename = self.create_temp_file()
        with self.app.app_context():
            blob = Blob.get_one(filename=filename.name)
            self.assertIsNotNone(blob)
            with blob.open_file(tmpdir, start=None, buffer_size=4096) as src:
                data = src.read()
            self.assertEqual(b'a blob file', data)
            with blob.open_file(tmpdir, start=6, buffer_size=4096) as src:
                data = src.read()
            self.assertEqual(b' file', data)

    def test_delete_file(self) -> None:
        tmpdir, filename = self.create_temp_file()
        with self.app.app_context():
            blob = Blob.get_one(filename=filename.name)
            self.assertIsNotNone(blob)
            blob.delete_file(tmpdir)
        self.assertFalse(filename.exists())

    def test_doesnt_delete_non_auto_file(self) -> None:
        tmpdir, filename = self.create_temp_file(auto_delete=False)
        with self.app.app_context():
            blob = Blob.get_one(filename=filename.name)
            self.assertIsNotNone(blob)
            blob.delete_file(tmpdir)
        self.assertTrue(filename.exists())

    def create_temp_file(self, auto_delete: bool = True) -> tuple[Path, Path]:
        filename = 'filename.mp4'
        tmpdir = Path(self.create_upload_folder())
        with self.app.app_context():
            blob = Blob(
                filename=filename,
                size=123,
                created=datetime.datetime(2023, 6, 20, 3, 4, 5),
                sha1_hash='609c4d156f961c4768e5a26d641cd1fdc439f7f5',
                content_type='video/mp4',
                auto_delete=auto_delete)
            blob.add(commit=True)
        tmp_filename = tmpdir / filename
        with tmp_filename.open('w') as dest:
            dest.write('a blob file')
        self.assertTrue(tmp_filename.exists())
        return (tmpdir, tmp_filename)


if __name__ == '__main__':
    unittest.main()
