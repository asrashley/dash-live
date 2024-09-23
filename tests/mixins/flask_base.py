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

import binascii
import ctypes
import json
import logging
import multiprocessing
from pathlib import Path
import shutil
import tempfile
from typing import Any, ClassVar, Optional, Type

from bs4 import BeautifulSoup, element
import flask

from dashlive.drm.playready import PlayReady
from dashlive.mpeg import mp4
from dashlive.mpeg.dash.representation import Representation
from dashlive.server import models
from dashlive.server.app import create_app
from dashlive.utils.date_time import from_isodatetime

from .async_flask_testing import AsyncFlaskTestCase
from .context_filter import ContextFilter
from .mixin import TestCaseMixin

class FlaskTestBase(TestCaseMixin, AsyncFlaskTestCase):
    # duration of media in test/fixtures directory (in seconds)
    ADMIN_USER = 'admin'
    ADMIN_EMAIL = 'admin@dashlive.unit.test'
    ADMIN_PASSWORD = r'suuuperSecret!'
    ENABLE_WSS = False
    FIXTURES_PATH = Path(__file__).parent.parent / "fixtures"
    STD_USER = 'user'
    STD_EMAIL = 'user@dashlive.unit.test'
    STD_PASSWORD = r'pa55word'
    MEDIA_DURATION = 40
    MEDIA_USER = 'media'
    MEDIA_EMAIL = 'media@dashlive.unit.test'
    MEDIA_PASSWORD = r'm3d!a'
    SEGMENT_DURATION = 4
    STREAM_TITLE = 'Big Buck Bunny'

    LOG_LEVEL: ClassVar[Type[logging.WARNING]] = logging.WARNING
    log_context: ClassVar[Optional[ContextFilter]] = None
    checked_urls: ClassVar[set[str]]

    _temp_dir = multiprocessing.Array(ctypes.c_char, 1024)
    current_url: str | None = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.checked_urls = set()
        cls.log_context = ContextFilter({'url'})
        format = r"%(asctime)s %(levelname)-8s:%(filename)s@%(lineno)d: %(message)s"
        logging.basicConfig(level=cls.LOG_LEVEL, format=format,
                            datefmt='%d-%m-%y %H:%M:%S')
        formatter = logging.Formatter(format + r"\n%(url)s", defaults={"url": ""})
        console = logging.StreamHandler()
        console.setLevel(cls.LOG_LEVEL)
        console.setFormatter(formatter)
        dash_log = logging.getLogger('DashValidator')
        dash_log.addFilter(cls.log_context)
        dash_log.setLevel(cls.LOG_LEVEL)
        dash_log.addHandler(console)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.log_context:
            dash_log = logging.getLogger('DashValidator')
            dash_log.removeFilter(cls.log_context)
            cls.log_context = None
        logging.disable(logging.NOTSET)
        super().tearDownClass()

    def create_app(self) -> flask.Flask:
        config = {
            'BLOB_FOLDER': str(self.FIXTURES_PATH.parent),
            'DASH': {
                'ALLOWED_DOMAINS': '*',
                'CSRF_SECRET': 'test.csrf.secret',
                'DEFAULT_ADMIN_USERNAME': 'admin',
                'DEFAULT_ADMIN_PASSWORD': 'test.secret!',
            },
            'UPLOAD_FOLDER': '/dev/null',
            'SECRET_KEY': 'cookie.secret',
            'SQLALCHEMY_DATABASE_URI': "sqlite:///:memory:",
            'TESTING': True,
            'LOG_LEVEL': 'critical',
            'PREFERRED_URL_SCHEME': 'http',
        }
        app = create_app(config=config, create_default_user=False, wss=self.ENABLE_WSS)
        with app.app_context():
            admin = models.User(
                username=self.ADMIN_USER,
                email=self.ADMIN_EMAIL,
                password=models.User.hash_password(self.ADMIN_PASSWORD),
                groups_mask=models.Group.ADMIN,
                must_change=False,
            )
            models.db.session.add(admin)
            std_user = models.User(
                username=self.STD_USER,
                email=self.STD_EMAIL,
                password=models.User.hash_password(self.STD_PASSWORD),
                groups_mask=models.Group.USER,
                must_change=False,
            )
            models.db.session.add(std_user)
            media_user = models.User(
                username=self.MEDIA_USER,
                email=self.MEDIA_EMAIL,
                password=models.User.hash_password(self.MEDIA_PASSWORD),
                groups_mask=(models.Group.USER + models.Group.MEDIA),
                must_change=False,
            )
            models.db.session.add(media_user)
            models.db.session.commit()
        return app

    def setup_media(self, with_subs=False):
        bbb = models.Stream(
            title=self.STREAM_TITLE,
            directory=self.FIXTURES_PATH.name,
            marlin_la_url='ms3://localhost/marlin/bbb',
            playready_la_url=PlayReady.TEST_LA_URL
        )
        fixture_files = [
            "bbb_v6", "bbb_v6_enc", "bbb_v7", "bbb_v7_enc",
            "bbb_a1", "bbb_a1_enc", "bbb_a2", "bbb_a2_enc"]
        if with_subs:
            fixture_files.append("bbb_t1")
        media_files = []
        blobs = []
        for idx, rid in enumerate(fixture_files):
            filename = rid + ".mp4"
            src_file = self.FIXTURES_PATH / filename
            if '_v' in rid:
                content_type = 'video'
            elif '_a' in rid:
                content_type = 'audio'
            else:
                content_type = 'text'
            blob = models.Blob(
                filename=filename,
                created=from_isodatetime("2022-09-01T12:23:00Z"),
                size=src_file.stat().st_size,
                sha1_hash=str(src_file),
                content_type=content_type,
                auto_delete=False)
            blobs.append(blob)
            js_filename = self.FIXTURES_PATH / f'rep-{rid}.json'
            rep: Representation | None = None
            if js_filename.exists():
                with js_filename.open('rt', encoding='utf-8') as src:
                    rep_js = json.load(src)
                if rep_js['version'] == Representation.VERSION:
                    rep = Representation(**rep_js)
                else:
                    rep = None
            if rep is None:
                print(f'Creating Representation cache: {js_filename}')
                with src_file.open(mode="rb", buffering=16384) as src:
                    atoms = mp4.Mp4Atom.load(src)
                rep = Representation.load(filename, atoms)
                rep_js = rep.toJSON(pure=True)
                with js_filename.open('wt', encoding='utf-8') as dest:
                    json.dump(rep_js, dest, indent=2)
            self.assertIsNotNone(rep)
            self.assertIsInstance(rep, Representation)
            encrypted = rid.endswith('_enc')
            self.assertEqual(encrypted, rep.encrypted)
            self.assertAlmostEqual(
                rep.mediaDuration,
                self.MEDIA_DURATION * rep.timescale,
                delta=(rep.timescale / 5.0),
                msg='Invalid duration for {}. Expected {} got {}'.format(
                    filename, self.MEDIA_DURATION * rep.timescale,
                    rep.mediaDuration))
            mf = models.MediaFile(
                name=rid,
                stream=bbb,
                bitrate=rep.bitrate,
                content_type=rep.content_type,
                codec_fourcc=rep.codecs.split('.')[0],
                track_id=rep.track_id,
                encrypted=rep.encrypted,
                blob=blob)
            mf.set_representation(rep)
            media_files.append(mf)
            if idx == 0:
                bbb.set_timing_reference(mf.as_stream_timing_reference())
        with self.app.app_context():
            models.db.session.add(bbb)
            for blob in blobs:
                models.db.session.add(blob)
            for mf in media_files:
                models.db.session.add(mf)
            models.db.session.commit()

        with self.app.app_context():
            kids = set()
            self.assertGreaterThan(models.MediaFile.count(), 0)
            for mf in models.MediaFile.all():
                r = mf.representation
                self.assertIsNotNone(
                    r, f'Failed to get Representation for MediaFile {mf.name}')
                if not r.encrypted:
                    continue
                for kid in r.kids:
                    if kid.raw in kids:
                        continue
                    key = binascii.b2a_hex(PlayReady.generate_content_key(kid.raw))
                    keypair = models.Key(hkid=kid.hex, hkey=key, computed=True)
                    models.db.session.add(keypair)
                    kids.add(kid.raw)
            models.db.session.commit()

    def create_upload_folder(self) -> str:
        with self.app.app_context():
            tmpdir = tempfile.mkdtemp()
            self._temp_dir.value = bytes(tmpdir, 'utf-8')
            self.app.config['UPLOAD_FOLDER'] = tmpdir
        return tmpdir

    def change_track_id(self, name: str, track_id: int) -> None:
        with self.app.app_context():
            mf = models.MediaFile.get(name='bbb_t1')
            if mf is None:
                print(f'Failed to find MediaFile(name={name})')
                return
            if mf.representation.track_id != track_id:
                new_filename = self.FIXTURES_PATH / f'{name}_{track_id}.mp4'
                print('Creating new track', new_filename)
                mf.modify_media_file(
                    new_filename=new_filename,
                    modify_atoms=lambda atom: models.MediaFile._set_track_id(
                        atom, track_id))

    def tearDown(self):
        self.logout_user()
        if hasattr(TestCaseMixin, "_orig_assert_true"):
            TestCaseMixin._assert_true = TestCaseMixin._orig_assert_true
            del TestCaseMixin._orig_assert_true
        if self._temp_dir.value:
            shutil.rmtree(self._temp_dir.value, ignore_errors=True)
        models.db.session.remove()
        models.db.drop_all()

    def login_user(self, username: str | None = None,
                   password: str | None = None,
                   is_admin: bool = False,
                   rememberme: bool = False,
                   ajax: bool = True):
        if is_admin:
            if username is None:
                username = self.ADMIN_USER
                password = self.ADMIN_PASSWORD
        else:
            if username is None:
                username = self.STD_USER
                password = self.STD_PASSWORD
        login_url = flask.url_for('login')
        if ajax:
            login_url += '?ajax=1'
        resp = self.client.get(login_url)
        self.assertEqual(resp.status_code, 200)
        if ajax:
            csrf_token = resp.json['csrf_token']
            return self.client.post(
                login_url,
                json={
                    'username': username,
                    'password': password,
                    'rememberme': rememberme,
                    'csrf_token': csrf_token
                },
                content_type='application/json')
        html = BeautifulSoup(resp.text, 'lxml')
        csrf_token = html.find(name='csrf_token')['value']
        return self.client.post(
            login_url,
            data={
                'username': username,
                'password': password,
                'rememberme': rememberme,
                'csrf_token': csrf_token
            })

    def logout_user(self):
        logout_url = flask.url_for('logout')
        return self.client.get(logout_url)

    def assertNotAuthorized(self, response, ajax: int) -> None:
        if ajax:
            self.assertEqual(response.status_code, 401)
            return
        self.assertEqual(response.status_code, 200)
        self.assertIn('This page requires you to log in', response.text)

    def check_form(self, form: element.Tag, expected: dict[str, Any]) -> str | None:
        """
        Check that the supplied HTML form has the expected fields and values
        """
        csrf_token: str | None = None
        for input_field in form.find_all('input'):
            name = input_field.get('name')
            if name == 'csrf_token':
                self.assertEqual(
                    input_field.get('type'),
                    'hidden')
                csrf_token = input_field.get('value')
                continue
            if isinstance(expected[name], bool):
                if expected[name] is True:
                    msg = f'Expected "{name}" field to be checked'
                    self.assertIsNotNone(input_field.get('checked'), msg=msg)
                else:
                    msg = f'Expected "{name}" field to not be checked'
                    self.assertIsNone(input_field.get('checked'), msg=msg)
            else:
                self.assertEqual(expected[name], input_field.get('value'))
        return csrf_token
